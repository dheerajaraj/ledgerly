from pydantic import BaseModel


class HealthOut(BaseModel):
    ok: bool
    stripe_configured: bool
    claude_configured: bool


class WebhookAck(BaseModel):
    received: bool = True
    duplicate: bool | None = None  # omitted from the response unless True
