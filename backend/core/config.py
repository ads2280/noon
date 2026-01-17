"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory (two levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Backend base URL (used to construct OAuth redirect URIs)
    backend_url: str = "http://localhost:8000"

    # Supabase configuration
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str | None = None

    # Google OAuth configuration
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    # Full redirect URI override (if set, takes precedence over constructed URI)
    google_oauth_redirect_uri: str | None = None
    # Redirect path (used with backend_url to construct redirect URI if google_oauth_redirect_uri is not set)
    google_oauth_redirect_path: str = "/api/v1/calendars/accounts/oauth/callback"
    google_oauth_app_redirect_uri: str | None = None
    google_oauth_scopes: list[str] = [
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar",
    ]

    @property
    def google_oauth_redirect_uri_resolved(self) -> str:
        """Get the Google OAuth redirect URI.
        
        Priority:
        1. If google_oauth_redirect_uri is set, use it (full override)
        2. Otherwise, construct from backend_url + google_oauth_redirect_path
        """
        if self.google_oauth_redirect_uri:
            return self.google_oauth_redirect_uri
        # Construct from backend_url + redirect_path
        base = self.backend_url.rstrip("/")
        path = self.google_oauth_redirect_path.lstrip("/")
        return f"{base}/{path}"

    # LangGraph Agent configuration
    langgraph_agent_url: str = "http://localhost:8000"
    langgraph_api_key: str | None = None
    langsmith_api_key: str | None = None

    # Deepgram transcription configuration
    deepgram_api_key: str | None = None

    # Performance debugging
    enable_timing_logger: bool = False  # Enable detailed timing logs (default: off for production)

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),  # Load from project root .env file
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
