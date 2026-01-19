from __future__ import annotations

from datetime import date as date_type, datetime
from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, Discriminator


class AgentResponseType(StrEnum):
    SHOW_EVENT = "show-event"
    SHOW_SCHEDULE = "show-schedule"
    CREATE_EVENT = "create-event"
    UPDATE_EVENT = "update-event"
    DELETE_EVENT = "delete-event"
    NO_ACTION = "no-action"


class DateTimeDict(BaseModel):
    """Represents either a datetime (for timed events) or a date (for all-day events)."""
    dateTime: Optional[datetime] = None
    date: Optional[date_type] = None
    
    @model_validator(mode='after')
    def validate_exactly_one_field(self):
        """Ensure exactly one of dateTime or date is provided."""
        has_datetime = self.dateTime is not None
        has_date = self.date is not None
        
        if not has_datetime and not has_date:
            raise ValueError("Exactly one of 'dateTime' or 'date' must be provided")
        if has_datetime and has_date:
            raise ValueError("Cannot provide both 'dateTime' and 'date' - use dateTime for timed events, date for all-day events")
        return self


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
