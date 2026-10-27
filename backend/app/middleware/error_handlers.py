"""Map domain exceptions to HTTP responses with the same {"detail": "..."} body as HTTPException."""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..services.exceptions import (
    BadInputError,
    ConflictError,
    DomainError,
    IntegrationFailed,
    IntegrationUnavailable,
    InvalidCredentials,
    InvalidWebhookSignature,
    NotAuthenticated,
    NotFoundError,
)

log = logging.getLogger(__name__)

# Checked in order, so subclasses (InvalidStatusTransition → ConflictError) resolve correctly.
STATUS_CODES: list[tuple[type[DomainError], int]] = [
    (NotFoundError, 404),
    (ConflictError, 409),
    (NotAuthenticated, 401),
    (InvalidCredentials, 401),
    (BadInputError, 400),
    (InvalidWebhookSignature, 400),
    (IntegrationUnavailable, 503),
    (IntegrationFailed, 502),
]


def status_for(exc: DomainError) -> int:
    for exc_type, status in STATUS_CODES:
        if isinstance(exc, exc_type):
            return status
    return 400


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = status_for(exc)
    if status >= 500:
        log.warning("%s on %s %s: %s", type(exc).__name__, request.method, request.url.path, exc.message)
    return JSONResponse(status_code=status, content={"detail": exc.message})


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
