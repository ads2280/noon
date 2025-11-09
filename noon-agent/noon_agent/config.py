"""Configuration helpers for the Noon LangGraph agent."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILES = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parents[1] / "noon-backend" / ".env",
    Path(__file__).resolve().parents[2] / ".env",
]


class AgentSettings(BaseSettings):
    """Project level configuration."""

    model_config = SettingsConfigDict(
        env_file=[str(path) for path in _ENV_FILES],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = Field(
        default="gpt-4o-mini",
        description="Default chat model used by the graph.",
    )
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_retries: int = Field(default=2, ge=0)
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing when configured.",
    )
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase project URL used by the agent when fetching context.",
    )
    supabase_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
        description="Supabase anon or service role key for agent data access.",
    )


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    """Cached settings accessor so we only hit the filesystem once."""

    return AgentSettings()
