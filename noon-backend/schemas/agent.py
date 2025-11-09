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
