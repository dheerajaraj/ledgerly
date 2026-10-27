from fastapi import APIRouter, Depends, Header, Request
from starlette.concurrency import run_in_threadpool

from ..schema.system import WebhookAck
from ..services.payment_service import PaymentService
from .deps import get_payment_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/stripe", response_model=WebhookAck, response_model_exclude_none=True)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    payments: PaymentService = Depends(get_payment_service),
):
    """Public: authenticated by the Stripe signature, not a user token."""
    payload = await request.body()  # raw bytes are needed to verify the signature
    return await run_in_threadpool(payments.handle_webhook, payload, stripe_signature)
