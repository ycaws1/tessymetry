from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = Field(..., description="Project URL, e.g. https://xxxx.supabase.co")

    # Hosted Supabase: use a Secret key (sb_secret_...) from Project Settings → API Keys.
    # Legacy JWT service_role keys still work. Do not use the Publishable key here—that is
    # the low-privilege client key (like anon); it cannot bypass RLS for backend inserts.
    supabase_secret_key: str = Field(
        ...,
        validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )

    webhook_secret: str | None = Field(
        default=None,
        description="If set, require Authorization: Bearer <secret> on POST /webhook/teslemetry",
    )

    cors_origins: str = Field(
        default="*",
        description="Comma-separated origins for CORS, or *",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
