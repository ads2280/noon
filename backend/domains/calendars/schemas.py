"""Calendar domain schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Discriminator, Field, HttpUrl, Tag, model_serializer, model_validator


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


# Event time discriminated union types
class TimedEventTime(BaseModel):
    """Represents a timed event with specific start/end times."""
    type: Literal["timed"] = "timed"
    date_time: datetime = Field(..., alias="dateTime")
    time_zone: Optional[str] = Field(None, alias="timeZone")
    
    class Config:
        populate_by_name = True


class AllDayEventTime(BaseModel):
    """Represents an all-day event with date only."""
    type: Literal["all_day"] = "all_day"
    date: date
    
    class Config:
        populate_by_name = True


# Discriminated union for event times
EventTime = Annotated[
    Union[TimedEventTime, AllDayEventTime],
    Discriminator("type"),
]


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
    start: Optional[EventTime] = None
    end: Optional[EventTime] = None
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
    
    @model_validator(mode='before')
    @classmethod
    def parse_event_times(cls, data: Any) -> Any:
        """Parse start/end from Google Calendar API format to EventTime union."""
        if isinstance(data, dict):
            # Parse start
            if "start" in data and isinstance(data["start"], dict) and "type" not in data["start"]:
                start_dict = data["start"]
                if "dateTime" in start_dict:
                    # Timed event - parse datetime string
                    date_time_str = start_dict["dateTime"]
                    # Parse ISO format datetime
                    if isinstance(date_time_str, str):
                        # Handle Z suffix and timezone
                        normalized = date_time_str.replace("Z", "+00:00")
                        date_time = datetime.fromisoformat(normalized)
                    else:
                        date_time = date_time_str
                    data["start"] = {
                        "type": "timed",
                        "date_time": date_time,  # Use snake_case field name (alias will handle "dateTime" in JSON)
                        "time_zone": start_dict.get("timeZone"),  # Use snake_case field name
                    }
                elif "date" in start_dict:
                    # All-day event - parse date string
                    date_str = start_dict["date"]
                    if isinstance(date_str, str):
                        date_value = date.fromisoformat(date_str)
                    else:
                        date_value = date_str
                    data["start"] = {
                        "type": "all_day",
                        "date": date_value,
                    }
            
            # Parse end
            if "end" in data and isinstance(data["end"], dict) and "type" not in data["end"]:
                end_dict = data["end"]
                if "dateTime" in end_dict:
                    # Timed event - parse datetime string
                    date_time_str = end_dict["dateTime"]
                    if isinstance(date_time_str, str):
                        normalized = date_time_str.replace("Z", "+00:00")
                        date_time = datetime.fromisoformat(normalized)
                    else:
                        date_time = date_time_str
                    data["end"] = {
                        "type": "timed",
                        "date_time": date_time,  # Use snake_case field name (alias will handle "dateTime" in JSON)
                        "time_zone": end_dict.get("timeZone"),  # Use snake_case field name
                    }
                elif "date" in end_dict:
                    # All-day event - parse date string
                    date_str = end_dict["date"]
                    if isinstance(date_str, str):
                        date_value = date.fromisoformat(date_str)
                    else:
                        date_value = date_str
                    data["end"] = {
                        "type": "all_day",
                        "date": date_value,
                    }
        return data
    
    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        """Serialize CalendarEvent with EventTime converted back to Google API format."""
        # Build data dict manually to avoid recursion
        data: Dict[str, Any] = {}
        
        if self.id is not None:
            data["id"] = self.id
        if self.summary is not None:
            data["summary"] = self.summary
        if self.description is not None:
            data["description"] = self.description
        if self.status is not None:
            data["status"] = self.status
        if self.html_link is not None:
            data["html_link"] = self.html_link
        if self.hangout_link is not None:
            data["hangout_link"] = self.hangout_link
        if self.updated is not None:
            data["updated"] = self.updated
        if self.account_id is not None:
            data["account_id"] = self.account_id
        if self.account_email is not None:
            data["account_email"] = self.account_email
        if self.calendar_id is not None:
            data["calendar_id"] = self.calendar_id
        if self.calendar_name is not None:
            data["calendar_name"] = self.calendar_name
        if self.calendar_color is not None:
            data["calendar_color"] = self.calendar_color
        if self.is_primary is not None:
            data["is_primary"] = self.is_primary
        if self.raw:
            data["raw"] = self.raw
        
        # Convert start EventTime back to Google API format (Dict)
        if self.start:
            if isinstance(self.start, TimedEventTime):
                data["start"] = {
                    "dateTime": self.start.date_time.isoformat(),
                    "timeZone": self.start.time_zone,
                }
            elif isinstance(self.start, AllDayEventTime):
                data["start"] = {
                    "date": self.start.date.isoformat(),
                }
        
        # Convert end EventTime back to Google API format (Dict)
        if self.end:
            if isinstance(self.end, TimedEventTime):
                data["end"] = {
                    "dateTime": self.end.date_time.isoformat(),
                    "timeZone": self.end.time_zone,
                }
            elif isinstance(self.end, AllDayEventTime):
                data["end"] = {
                    "date": self.end.date.isoformat(),
                }
        
        return data


class ScheduleResponse(BaseModel):
    window: EventWindowInfo
    events: List[CalendarEvent]


class CreateEventRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    start: EventTime
    end: EventTime
    calendar_id: str = Field(..., min_length=1)
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = Field(default="UTC", min_length=1)
    
    @model_validator(mode='after')
    def validate_event_times(self):
        """Ensure start and end are the same type (both timed or both all-day)."""
        if isinstance(self.start, TimedEventTime) != isinstance(self.end, TimedEventTime):
            raise ValueError("Start and end must both be timed or both be all-day events")
        return self


class CreateEventResponse(BaseModel):
    event: CalendarEvent


class UpdateEventRequest(BaseModel):
    summary: Optional[str] = None
    start: Optional[EventTime] = None
    end: Optional[EventTime] = None
    calendar_id: str = Field(..., min_length=1)
    description: Optional[str] = None
    location: Optional[str] = None
    timezone: str = Field(default="UTC", min_length=1)
    
    @model_validator(mode='after')
    def validate_event_times(self):
        """Ensure start and end are the same type if both provided."""
        if self.start is not None and self.end is not None:
            if isinstance(self.start, TimedEventTime) != isinstance(self.end, TimedEventTime):
                raise ValueError("Start and end must both be timed or both be all-day events")
        return self


class UpdateEventResponse(BaseModel):
    event: CalendarEvent
