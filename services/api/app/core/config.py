from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@postgres:5432/aesthetica")
    supabase_database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "captures"
    supabase_store_catalog_input: bool = True
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440

    default_top_k: int = 30
    base_dashboard_url: str = "http://localhost:5173"

    poke_api_key: str = ""
    poke_webhook_url: str = "https://poke.com/api/v1/inbound/api-message"

    web_search_enabled: bool = True
    web_search_provider: str = "serpapi"
    web_search_top_k: int = 5
    web_search_country: str = "us"
    web_search_language: str = "en"
    web_search_enable_lens: bool = True
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search.json"

    dev_auth_email: str = "demo@aesthetica.dev"
    dev_auth_password: str = "demo123"

    @model_validator(mode="after")
    def _apply_supabase_db_override(self) -> "Settings":
        # Allow `SUPABASE_DATABASE_URL` to override `DATABASE_URL` when provided.
        # Treat empty string as "not set".
        if self.supabase_database_url:
            self.database_url = self.supabase_database_url
        return self


settings = Settings()
