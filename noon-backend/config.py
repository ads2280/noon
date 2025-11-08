from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str) -> Optional[str]:
    value = os.getenv(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    url = _get_env("SUPABASE_URL")
    service_key = _get_env("SUPABASE_SERVICE_ROLE_KEY")

    missing: list[str] = []
    if not url:
        missing.append("SUPABASE_URL")
    if not service_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        raise RuntimeError(
            "Missing required Supabase configuration: "
            + ", ".join(missing)
            + ". Set them in your environment or .env file."
        )

    return Settings(
        supabase_url=url,
        supabase_service_role_key=service_key,
        supabase_anon_key=_get_env("SUPABASE_ANON_KEY"),
        supabase_jwt_secret=_get_env("SUPABASE_JWT_SECRET"),
    )

