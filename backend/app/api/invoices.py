from fastapi import APIRouter, Depends

from ..schema.auth import CurrentUser
from ..schema.invoice import InvoiceCreate, InvoiceOut
from ..services.invoice_service import InvoiceService
from .deps import get_current_user, get_invoice_service

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    invoices: InvoiceService = Depends(get_invoice_service),
):
    return invoices.list(user.id, status)


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    body: InvoiceCreate,
    user: CurrentUser = Depends(get_current_user),
    invoices: InvoiceService = Depends(get_invoice_service),
):
    return invoices.create(user.id, body)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    user: CurrentUser = Depends(get_current_user),
    invoices: InvoiceService = Depends(get_invoice_service),
):
    return invoices.get(user.id, invoice_id)


@router.post("/{invoice_id}/payment-link", response_model=InvoiceOut)
def create_payment_link(
    invoice_id: int,
    user: CurrentUser = Depends(get_current_user),
    invoices: InvoiceService = Depends(get_invoice_service),
):
    """Create (or recreate, if expired) a Stripe Checkout page for this invoice."""
    return invoices.create_payment_link(user.id, invoice_id)


@router.post("/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(
    invoice_id: int,
    user: CurrentUser = Depends(get_current_user),
    invoices: InvoiceService = Depends(get_invoice_service),
):
    return invoices.void(user.id, invoice_id)
