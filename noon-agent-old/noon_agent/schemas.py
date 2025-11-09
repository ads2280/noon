"""Shared type definitions used across the graph."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class AgentQuery(BaseModel):
    """Inbound payload for the single agent endpoint."""

    query: str
    auth_token: Optional[str] = None
    calendar_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="forbid")


class ShowEventPayload(BaseModel):
    tool: Literal["show"]
    id: str
    calendar: Optional[str] = None
    event: Optional[Dict[str, Any]] = None  # Optional detailed payload

    model_config = ConfigDict(extra="allow")


class ShowSchedulePayload(BaseModel):
    tool: Literal["show-schedule"]
    start_day: str
    end_day: str
    events: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(extra="forbid")


class CreateEventPayload(BaseModel):
    tool: Literal["create"]
    id: Optional[str] = None
    calendar: Optional[str] = None
    summary: str
    description: Optional[str] = None
    start_time: str
    end_time: str
    attendees: Optional[List[str]] = None
    location: Optional[str] = None
    conference_link: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class UpdateEventPayload(BaseModel):
    tool: Literal["update"]
    id: str
    calendar: Optional[str] = None
    changes: Dict[str, Any]

    model_config = ConfigDict(extra="allow")


class DeleteEventPayload(BaseModel):
    tool: Literal["delete"]
    id: str
    calendar: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


AgentResponse = Annotated[
    Union[
        ShowEventPayload,
        ShowSchedulePayload,
        CreateEventPayload,
        UpdateEventPayload,
        DeleteEventPayload,
    ],
    Field(discriminator="tool"),
]


class ParsedIntent(BaseModel):
    action: Literal["create", "delete", "update", "read", "search", "schedule"]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    people: Optional[List[str]] = None
    name: Optional[str] = None
    auth_provider: Optional[str] = None
    auth_token: Optional[str] = None
    summary: Optional[str] = None
    event_id: Optional[str] = None  # Required for update/delete actions
    calendar_id: Optional[str] = None  # Required with event_id for update/delete

    model_config = ConfigDict(extra="forbid")
