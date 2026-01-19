from __future__ import annotations

from datetime import date as date_type, datetime
from enum import StrEnum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Discriminator, Field, field_validator, model_validator, ConfigDict


class AgentResponseType(StrEnum):
    SHOW_EVENT = "show-event"
    SHOW_SCHEDULE = "show-schedule"
    CREATE_EVENT = "create-event"
    UPDATE_EVENT = "update-event"
    DELETE_EVENT = "delete-event"
    NO_ACTION = "no-action"


class TimedDateTime(BaseModel):
    """Represents a timed event with specific start/end times."""
    type: Literal["timed"] = "timed"
    dateTime: datetime
    
    class Config:
        populate_by_name = True


class AllDayDateTime(BaseModel):
    """Represents an all-day event with date only."""
    type: Literal["all_day"] = "all_day"
    date: date_type
    
    class Config:
        populate_by_name = True


# Discriminated union for DateTimeDict
DateTimeDict = Annotated[
    Union[TimedDateTime, AllDayDateTime],
    Discriminator("type"),
]


class ShowEventMetadata(BaseModel):
    event_id: str
    calendar_id: str


class ShowEventResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.SHOW_EVENT
    metadata: ShowEventMetadata
    query: str = ""


class ShowScheduleMetadata(BaseModel):
    start_date: datetime
    end_date: datetime


class ShowScheduleResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.SHOW_SCHEDULE
    metadata: ShowScheduleMetadata
    query: str = ""


class CreateEventMetadata(BaseModel):
    summary: str
    start: DateTimeDict
    end: DateTimeDict
    calendar_id: str
    description: Optional[str] = None
    location: Optional[str] = None


class CreateEventResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.CREATE_EVENT
    metadata: CreateEventMetadata
    query: str = ""


class UpdateEventMetadata(BaseModel):
    event_id: str
    calendar_id: str
    summary: Optional[str] = None
    start: Optional[DateTimeDict] = None
    end: Optional[DateTimeDict] = None
    description: Optional[str] = None
    location: Optional[str] = None


class UpdateEventResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.UPDATE_EVENT
    metadata: UpdateEventMetadata
    query: str = ""


class DeleteEventMetadata(BaseModel):
    event_id: str
    calendar_id: str


class DeleteEventResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.DELETE_EVENT
    metadata: DeleteEventMetadata
    query: str = ""


class NoActionMetadata(BaseModel):
    reason: str


class NoActionResponse(BaseModel):
    success: bool = True
    type: AgentResponseType = AgentResponseType.NO_ACTION
    metadata: NoActionMetadata
    query: str = ""


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    query: Optional[str] = None


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
    "AgentResponseType",
    "CreateEventResponse",
    "CreateEventMetadata",
    "DeleteEventResponse",
    "DeleteEventMetadata",
    "ErrorResponse",
    "NoActionResponse",
    "NoActionMetadata",
    "ShowEventMetadata",
    "ShowEventResponse",
    "ShowScheduleMetadata",
    "ShowScheduleResponse",
    "UpdateEventResponse",
    "UpdateEventMetadata",
]
