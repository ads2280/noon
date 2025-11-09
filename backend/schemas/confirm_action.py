from __future__ import annotations

from typing import Any, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict

from schemas.agent_response import (
    EventPayload,
    ShowEventMetadata,
    UpdateEventMetadata,
)


class CreateEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request: Literal["create-event"]
    metadata: EventPayload


class UpdateEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request: Literal["update-event"]
    metadata: UpdateEventMetadata


class DeleteEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request: Literal["delete-event"]
    metadata: ShowEventMetadata


ConfirmActionRequest = Union[
    CreateEventRequest,
    UpdateEventRequest,
    DeleteEventRequest,
]


class ScheduleDateRangeRequest(BaseModel):
    """Request schema for getting all calendar events across all user calendars."""

    start_date: str  # ISO format datetime string
    end_date: str  # ISO format datetime string


__all__ = [
    "ConfirmActionRequest",
    "CreateEventRequest",
    "DeleteEventRequest",
    "ScheduleDateRangeRequest",
    "UpdateEventRequest",
]

