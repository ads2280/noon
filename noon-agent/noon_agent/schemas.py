"""Shared type definitions used across the graph."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    action: Literal["create", "delete", "update", "read"]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    people: Optional[List[str]] = None
    name: Optional[str] = None
    auth: Dict[str, Any] = Field(default_factory=dict)
    summary: Optional[str] = None
