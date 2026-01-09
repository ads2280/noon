"""Calendar domain schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


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


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: HttpUrl
    state: str = Field(..., min_length=10)
    state_expires_at: datetime


# Calendar event schemas
class EventSurroundingScheduleRequest(BaseModel):
    event_id: str = Field(..., min_length=1)
    calendar_id: str = Field(..., min_length=1)
    timezone: str = Field(default="UTC", min_length=1)


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


class EventDetail(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    calendar_id: Optional[str] = None
    calendar_name: Optional[str] = None
    account_id: Optional[str] = None
    account_email: Optional[str] = None


class ScheduleResponse(BaseModel):
    window: EventWindowInfo
    events: List[CalendarEvent]


class EventSurroundingScheduleResponse(BaseModel):
    event: EventDetail
    schedule: ScheduleResponse
