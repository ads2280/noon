from __future__ import annotations

from typing import Any, Dict, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class ShowEventMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    event_id: str = Field(alias="event-id")
    calendar_id: str = Field(alias="calendar-id")


class ShowScheduleMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    start_date: str = Field(alias="start-date")
    end_date: str = Field(alias="end-date")


EventPayload = Dict[str, Any]


class ShowEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["show-event"]
    metadata: ShowEventMetadata


class ShowScheduleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["show-schedule"]
    metadata: ShowScheduleMetadata


class CreateEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["create-event"]
    metadata: EventPayload


class UpdateEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["update-event"]
    metadata: "UpdateEventMetadata"


class DeleteEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["delete-event"]
    metadata: ShowEventMetadata


class UpdateEventMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    event_id: str = Field(alias="event-id")
    calendar_id: str = Field(alias="calendar-id")


class NoActionResponseMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: str


class NoActionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["true"]
    request: Literal["no-action"]
    metadata: NoActionResponseMetadata


class ErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    success: Literal["false"]
    message: str


AgentResponse = Union[
    ShowEventResponse,
    ShowScheduleResponse,
    CreateEventResponse,
    UpdateEventResponse,
    DeleteEventResponse,
    NoActionResponse,
    ErrorResponse,
]

__all__ = [
    "AgentResponse",
    "CreateEventResponse",
    "DeleteEventResponse",
    "ErrorResponse",
    "EventPayload",
    "NoActionResponse",
    "NoActionResponseMetadata",
    "ShowEventMetadata",
    "ShowEventResponse",
    "ShowScheduleMetadata",
    "ShowScheduleResponse",
    "UpdateEventResponse",
    "UpdateEventMetadata",
]
