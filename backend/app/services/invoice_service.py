from sqlalchemy.orm import Session

from ..config import Settings
from ..integrations.stripe import StripeClient, StripeNotConfigured, StripeRequestFailed
from ..repository.client_repository import ClientRepository
from ..repository.invoice_repository import InvoiceRepository
from ..repository.models import Invoice, InvoiceStatus
from ..schema.invoice import InvoiceCreate, InvoiceOut, PaymentOut
from .exceptions import IntegrationFailed, IntegrationUnavailable, NotFoundError
from .invoice_status import ensure_transition


def invoice_to_out(invoice: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        client_id=invoice.client_id,
        client_name=invoice.client.name,
        description=invoice.description,
        amount_cents=invoice.amount_cents,
        currency=invoice.currency,
        status=invoice.status,
        due_date=invoice.due_date,
        checkout_url=invoice.checkout_url,
        paid_at=invoice.paid_at,
        created_at=invoice.created_at,
        payment=PaymentOut.model_validate(invoice.payment) if invoice.payment else None,
    )


class InvoiceService:
    def __init__(
        self,
        db: Session,
        invoices: InvoiceRepository,
        clients: ClientRepository,
        stripe: StripeClient,
        settings: Settings,
    ):
        self.db = db
        self.invoices = invoices
        self.clients = clients
        self.stripe = stripe
        self.settings = settings

    def _get_owned(self, user_id: int, invoice_id: int) -> Invoice:
        invoice = self.invoices.get_for_user(user_id, invoice_id)
        if not invoice:
            raise NotFoundError("Invoice not found.")
        return invoice

    def list(self, user_id: int, status: str | None = None) -> list[InvoiceOut]:
        return [invoice_to_out(i) for i in self.invoices.list_for_user(user_id, status=status)]

    def get(self, user_id: int, invoice_id: int) -> InvoiceOut:
        return invoice_to_out(self._get_owned(user_id, invoice_id))

    def create(self, user_id: int, data: InvoiceCreate) -> InvoiceOut:
        client = self.clients.get_for_user(user_id, data.client_id)
        if not client:
            raise NotFoundError("Client not found.")
        invoice = self.invoices.add(Invoice(
            user_id=user_id,
            client_id=client.id,
            description=data.description,
            amount_cents=data.amount_cents,
            currency=self.settings.default_currency,
            due_date=data.due_date,
        ))
        self.db.commit()
        return self.get(user_id, invoice.id)

    def create_payment_link(self, user_id: int, invoice_id: int) -> InvoiceOut:
        """Create (or recreate, if expired) a Stripe Checkout page for this invoice."""
        invoice = self._get_owned(user_id, invoice_id)
        if invoice.status == InvoiceStatus.OPEN and invoice.checkout_url:
            return invoice_to_out(invoice)
        ensure_transition(invoice.status, InvoiceStatus.OPEN)

        client = invoice.client
        metadata = {"ledgerly_invoice_id": str(invoice.id), "ledgerly_user_id": str(invoice.user_id)}
        try:
            if not client.stripe_customer_id:
                client.stripe_customer_id = self.stripe.create_customer(
                    name=client.name,
                    email=client.email,
                    metadata={"ledgerly_client_id": str(client.id), "ledgerly_user_id": str(client.user_id)},
                )
                # Deliberate early commit: the customer now exists in Stripe whatever happens next,
                # so keep its ID even if checkout fails; otherwise a retry creates a duplicate customer.
                self.db.commit()
            session = self.stripe.create_checkout_session(
                customer_id=client.stripe_customer_id,
                amount_cents=invoice.amount_cents,
                currency=invoice.currency,
                description=invoice.description,
                metadata=metadata,
                success_url=f"{self.settings.frontend_url}/pay/success?invoice={invoice.id}",
                cancel_url=f"{self.settings.frontend_url}/pay/cancelled?invoice={invoice.id}",
            )
        except StripeNotConfigured as e:
            raise IntegrationUnavailable(str(e)) from e
        except StripeRequestFailed as e:
            raise IntegrationFailed(f"Stripe couldn't create the payment link: {e}") from e

        invoice.stripe_checkout_session_id, invoice.checkout_url = session.id, session.url
        invoice.status = InvoiceStatus.OPEN
        self.db.commit()
        return invoice_to_out(invoice)

    def void(self, user_id: int, invoice_id: int) -> InvoiceOut:
        invoice = self._get_owned(user_id, invoice_id)
        ensure_transition(invoice.status, InvoiceStatus.VOID)
        if invoice.status == InvoiceStatus.OPEN and invoice.stripe_checkout_session_id:
            try:
                self.stripe.expire_checkout_session(invoice.stripe_checkout_session_id)
            except StripeNotConfigured:
                pass
        invoice.status, invoice.checkout_url = InvoiceStatus.VOID, None
        self.db.commit()
        return invoice_to_out(invoice)
