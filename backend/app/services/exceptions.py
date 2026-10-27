"""Domain exceptions raised by services. middleware/error_handlers.py maps them to HTTP responses.

The message is shown to the user, so write it for them.
"""


class DomainError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """The row doesn't exist or belongs to another user (indistinguishable on purpose)."""


class ConflictError(DomainError):
    """The request conflicts with current state, e.g. a duplicate email."""


class InvalidStatusTransition(ConflictError):
    """The invoice status machine doesn't allow this change."""


class NotAuthenticated(DomainError):
    """No valid session token."""


class InvalidCredentials(DomainError):
    """Email or password is wrong."""


class BadInputError(DomainError):
    """Input passed schema validation but can't be processed, e.g. a malformed CSV."""


class InvalidWebhookSignature(DomainError):
    """A webhook payload failed signature verification."""


class IntegrationUnavailable(DomainError):
    """A third-party provider isn't configured."""


class IntegrationFailed(DomainError):
    """A third-party provider call failed."""
