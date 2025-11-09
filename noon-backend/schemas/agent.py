"""Schemas for agent endpoints."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    """Request schema for agent chat endpoint."""

    text: str


class AgentChatResponse(BaseModel):
    """Response schema for agent chat endpoint."""

    tool: str
    summary: str
    result: Optional[Dict[str, Any]] = None
    success: bool


class GetEventRequest(BaseModel):
    """Request schema for get event endpoint."""

    event_id: str
    calendar_id: str = "primary"


class GetEventResponse(BaseModel):
    """Response schema for get event endpoint."""

    event: Dict[str, Any]
    day_schedule: Dict[str, Any]
    success: bool
