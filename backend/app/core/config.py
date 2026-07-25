from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TrustGuard AI"
    env: str = "development"

    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Used from Day 3 onward (agents).
    # "gemini-flash-latest" is Google's alias that always points to their
    # current recommended free-tier Flash model — it gets hot-swapped by
    # Google as they release/deprecate specific versions (this project
    # originally pinned gemini-2.5-flash directly, which stopped being
    # available to new API keys within weeks — the alias exists exactly
    # to avoid that kind of breakage).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
