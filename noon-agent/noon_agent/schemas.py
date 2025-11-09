"""Shared type definitions used across the graph."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class ParsedIntent(BaseModel):
    action: Literal["create", "delete", "update", "read"]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    people: Optional[List[str]] = None
    name: Optional[str] = None
    auth_provider: Optional[str] = None
    auth_token: Optional[str] = None
    summary: Optional[str] = None

    model_config = ConfigDict(extra="forbid")
