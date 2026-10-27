"""Builds services with their repositories and integration clients, so the api layer never imports
repositories or integrations. Tests swap providers by monkeypatching stripe_client / claude_client.
"""
from sqlalchemy.orm import Session

from ..config import get_settings
from ..integrations.anthropic import ClaudeClient
from ..integrations.stripe import StripeClient
from ..repository.client_repository import ClientRepository
from ..repository.expense_repository import ExpenseRepository
from ..repository.invoice_repository import InvoiceRepository
from ..repository.payment_repository import PaymentRepository
from ..repository.stripe_event_repository import StripeEventRepository
from ..repository.user_repository import UserRepository
from .analytics import AnalyticsService
from .auth_service import AuthService
from .categorization import CategorizationService
from .client_service import ClientService
from .expense_service import ExpenseService
from .insights_service import InsightsService
from .invoice_service import InvoiceService
from .payment_service import PaymentService
from .system_service import SystemService


def stripe_client() -> StripeClient:
    return StripeClient(get_settings())


def claude_client() -> ClaudeClient:
    return ClaudeClient(get_settings())


def build_auth_service(db: Session) -> AuthService:
    return AuthService(db, UserRepository(db), get_settings())


def build_client_service(db: Session) -> ClientService:
    return ClientService(db, ClientRepository(db))


def build_invoice_service(db: Session) -> InvoiceService:
    return InvoiceService(db, InvoiceRepository(db), ClientRepository(db), stripe_client(), get_settings())


def build_payment_service(db: Session) -> PaymentService:
    return PaymentService(db, InvoiceRepository(db), PaymentRepository(db), StripeEventRepository(db), stripe_client())


def build_expense_service(db: Session) -> ExpenseService:
    return ExpenseService(db, ExpenseRepository(db), CategorizationService(claude_client()))


def build_analytics_service(db: Session) -> AnalyticsService:
    return AnalyticsService(PaymentRepository(db), ExpenseRepository(db), InvoiceRepository(db))


def build_insights_service(db: Session) -> InsightsService:
    return InsightsService(build_analytics_service(db), InvoiceRepository(db), claude_client())


def build_system_service() -> SystemService:
    return SystemService(stripe_client(), claude_client())
