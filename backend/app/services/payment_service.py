"""Stripe webhooks are the source of truth for payment status.

Never mark an invoice paid from the browser redirect alone; the customer could close the tab,
or someone could hit the success URL directly. Only a signature-verified event counts.
"""
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..integrations.stripe import InvalidSignature, StripeClient, StripeNotConfigured
from ..repository.invoice_repository import InvoiceRepository
from ..repository.models import Invoice, InvoiceStatus, Payment
from ..repository.models.base import utcnow
from ..repository.payment_repository import PaymentRepository
from ..repository.stripe_event_repository import StripeEventRepository
from ..schema.system import WebhookAck
from .exceptions import IntegrationUnavailable, InvalidWebhookSignature
from .invoice_status import ensure_transition

log = logging.getLogger(__name__)

# Stripe event type -> PaymentService method name. Unlisted events are acknowledged and ignored.
HANDLERS = {
    "checkout.session.completed": "handle_checkout_completed",
    "checkout.session.async_payment_succeeded": "handle_checkout_completed",
    "checkout.session.expired": "handle_checkout_expired",
}


class PaymentService:
    def __init__(
        self,
        db: Session,
        invoices: InvoiceRepository,
        payments: PaymentRepository,
        events: StripeEventRepository,
        stripe: StripeClient,
    ):
        self.db = db
        self.invoices = invoices
        self.payments = payments
        self.events = events
        self.stripe = stripe

    def handle_webhook(self, payload: bytes, signature: str) -> WebhookAck:
        try:
            event = self.stripe.parse_webhook(payload, signature)
        except StripeNotConfigured as e:
            raise IntegrationUnavailable(str(e)) from e
        except InvalidSignature as e:
            raise InvalidWebhookSignature("Invalid signature.") from e

        if self.events.exists(event.id):
            return WebhookAck(duplicate=True)

        handler_name = HANDLERS.get(event.type)
        if handler_name:
            getattr(self, handler_name)(event.data_object)
        # Record the event in the same transaction as its effects, so it's applied exactly once.
        self.events.add(event.id, event.type)
        try:
            self.db.commit()
        except IntegrityError:  # a concurrent delivery of the same event committed first
            self.db.rollback()
            return WebhookAck(duplicate=True)
        return WebhookAck()

    def _find_invoice(self, session: dict) -> Invoice | None:
        invoice_id = (session.get("metadata") or {}).get("ledgerly_invoice_id")
        if invoice_id and invoice_id.isdigit():
            invoice = self.invoices.get_by_id_unscoped(int(invoice_id))
            if invoice:
                return invoice
        return self.invoices.get_by_checkout_session_id(session.get("id"))

    def handle_checkout_completed(self, session: dict) -> None:
        if session.get("payment_status") != "paid":
            return  # e.g. delayed payment methods; wait for async_payment_succeeded
        invoice = self._find_invoice(session)
        if not invoice:
            log.warning("Checkout session %s has no matching invoice", session.get("id"))
            return
        if invoice.status == InvoiceStatus.PAID:
            return
        if invoice.status == InvoiceStatus.VOID:
            log.warning("Invoice %s was void but Stripe reports it paid; recording the payment", invoice.id)
        ensure_transition(invoice.status, InvoiceStatus.PAID)

        payment_intent_id = session.get("payment_intent")
        gross = int(session.get("amount_total") or invoice.amount_cents)
        fee = self.stripe.get_fee_cents(payment_intent_id) if payment_intent_id else 0
        paid_at = utcnow()

        invoice.status, invoice.paid_at, invoice.stripe_payment_intent_id = InvoiceStatus.PAID, paid_at, payment_intent_id
        self.payments.add(Payment(
            user_id=invoice.user_id,
            invoice_id=invoice.id,
            gross_cents=gross,
            fee_cents=fee,
            net_cents=gross - fee,
            currency=session.get("currency") or invoice.currency,
            paid_at=paid_at,
        ))

    def handle_checkout_expired(self, session: dict) -> None:
        invoice = self._find_invoice(session)
        if invoice and invoice.status == InvoiceStatus.OPEN and invoice.stripe_checkout_session_id == session.get("id"):
            ensure_transition(invoice.status, InvoiceStatus.EXPIRED)
            invoice.status, invoice.checkout_url = InvoiceStatus.EXPIRED, None
