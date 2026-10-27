from ..integrations.anthropic import ClaudeClient
from ..integrations.stripe import StripeClient
from ..schema.system import HealthOut


class SystemService:
    def __init__(self, stripe: StripeClient, claude: ClaudeClient):
        self.stripe = stripe
        self.claude = claude

    def status(self) -> HealthOut:
        return HealthOut(ok=True, stripe_configured=self.stripe.enabled, claude_configured=self.claude.enabled)
