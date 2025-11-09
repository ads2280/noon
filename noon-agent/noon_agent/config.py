"""Configuration helpers for the Noon LangGraph agent."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Project level configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    """Cached settings accessor so we only hit the filesystem once."""

    return AgentSettings()
