"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase configuration
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str | None = None

    # Google OAuth configuration
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_oauth_redirect_uri: str | None = None
    google_oauth_app_redirect_uri: str | None = None
    google_oauth_scopes: list[str] = [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    # LangGraph Agent configuration
    langgraph_agent_url: str = "http://localhost:8000"
    langgraph_api_key: str | None = None
    langsmith_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
