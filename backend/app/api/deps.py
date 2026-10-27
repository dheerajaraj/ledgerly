"""FastAPI dependencies: DB session, services, and the signed-in user."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..schema.auth import CurrentUser
from ..services import factory
from ..services.analytics import AnalyticsService
from ..services.auth_service import AuthService
from ..services.client_service import ClientService
from ..services.expense_service import ExpenseService
from ..services.insights_service import InsightsService
from ..services.invoice_service import InvoiceService
from ..services.payment_service import PaymentService
from ..services.system_service import SystemService

bearer = HTTPBearer(auto_error=False)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return factory.build_auth_service(db)


def get_client_service(db: Session = Depends(get_db)) -> ClientService:
    return factory.build_client_service(db)


def get_invoice_service(db: Session = Depends(get_db)) -> InvoiceService:
    return factory.build_invoice_service(db)


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return factory.build_payment_service(db)


def get_expense_service(db: Session = Depends(get_db)) -> ExpenseService:
    return factory.build_expense_service(db)


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return factory.build_analytics_service(db)


def get_insights_service(db: Session = Depends(get_db)) -> InsightsService:
    return factory.build_insights_service(db)


def get_system_service() -> SystemService:
    return factory.build_system_service()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    auth: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    """Raises NotAuthenticated (401) if the bearer token is missing, invalid, or for a deleted user."""
    return auth.user_from_token(creds.credentials if creds else None)
