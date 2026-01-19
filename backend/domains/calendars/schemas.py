"""Calendar domain schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


# Google Account schemas
class GoogleAccountBase(BaseModel):
    google_user_id: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, object]] = None


class GoogleAccountCreate(GoogleAccountBase):
    pass


class GoogleAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, object]] = None


class GoogleAccountResponse(GoogleAccountBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    calendars: Optional[List[CalendarResponse]] = None


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: HttpUrl
    state: str = Field(..., min_length=10)
    state_expires_at: datetime


# Calendar schemas
class CalendarResponse(BaseModel):
    id: str
    google_calendar_id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    is_primary: bool = False
    google_account_id: str
    created_at: datetime
    updated_at: datetime


# Calendar event schemas
class ScheduleRequest(BaseModel):
    start_date: date
    end_date: date
    timezone: str = Field(default="UTC", min_length=1)


class EventWindowInfo(BaseModel):
    start: datetime
    end: datetime
    timezone: str
    start_date: date
    end_date: date


class CalendarEvent(BaseModel):
    id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start: Dict[str, Any] = Field(default_factory=dict)
    end: Dict[str, Any] = Field(default_factory=dict)
    html_link: Optional[str] = None
    hangout_link: Optional[str] = None
    updated: Optional[str] = None
    account_id: Optional[str] = None
    account_email: Optional[str] = None
    calendar_id: Optional[str] = None
    calendar_name: Optional[str] = None
    calendar_color: Optional[str] = None
    is_primary: Optional[bool] = None
    raw: Dict[str, Any] = Field(default_factory=dict)


class ScheduleResponse(BaseModel):
    window: EventWindowInfo
    events: List[CalendarEvent]


class CreateEventRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    calendar_id: str = Field(..., min_length=1)
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = Field(default="UTC", min_length=1)
    
    @model_validator(mode='after')
    def validate_date_fields(self):
        """Ensure exactly one of (start, end) or (start_date, end_date) is provided."""
        has_datetime = self.start is not None and self.end is not None
        has_date = self.start_date is not None and self.end_date is not None
        
        if not has_datetime and not has_date:
            raise ValueError("Either (start, end) for timed events or (start_date, end_date) for all-day events must be provided")
        if has_datetime and has_date:
            raise ValueError("Cannot provide both datetime and date fields. Use datetime for timed events, date for all-day events.")
        return self


class CreateEventResponse(BaseModel):
    event: CalendarEvent


class UpdateEventRequest(BaseModel):
    summary: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    calendar_id: str = Field(..., min_length=1)
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = Field(default="UTC", min_length=1)
    
    @model_validator(mode='after')
    def validate_date_fields(self):
        """Ensure datetime and date fields are not mixed."""
        has_datetime = self.start is not None or self.end is not None
        has_date = self.start_date is not None or self.end_date is not None
        
        if has_datetime and has_date:
            raise ValueError("Cannot provide both datetime and date fields. Use datetime for timed events, date for all-day events.")
        return self


class UpdateEventResponse(BaseModel):
    event: CalendarEvent
