from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./ledgerly.db"
    frontend_url: str = "http://localhost:5173"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    default_currency: str = "usd"

    anthropic_api_key: str = ""
    claude_fast_model: str = "claude-haiku-5-5"
    claude_smart_model: str = "claude-sonnet-5-5"

    @property
    def stripe_enabled(self) -> bool:
        return self.stripe_secret_key.startswith(("sk_test_", "sk_live_", "rk_"))

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key) and not self.anthropic_api_key.endswith("xxx")


@lru_cache
def get_settings() -> Settings:
    return Settings()
