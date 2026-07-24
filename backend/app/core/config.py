from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TrustGuard AI"
    env: str = "development"

    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Unused until Day 3 (agents) — kept here now so config stays
    # centralized in one place instead of scattered across agent files.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
