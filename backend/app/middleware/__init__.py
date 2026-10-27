from fastapi import FastAPI

from ..config import Settings
from .cors import add_cors
from .error_handlers import register_error_handlers
from .logging import AccessLogMiddleware, configure_logging
from .request_id import RequestIdMiddleware

__all__ = ["configure_logging", "register_error_handlers", "register_middleware"]


def register_middleware(app: FastAPI, settings: Settings) -> None:
    """The last middleware added runs first. Order, outermost first:
    request ID (so everything below can log it) → access log → CORS → app.
    """
    add_cors(app, settings)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
