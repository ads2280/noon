"""Database models for Supabase tables.

These models use Pydantic for validation and match the Supabase table schemas.
They are used for type hints and validation when reading/writing to the database.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user fields."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    timezone: str = Field(
        default="UTC", description="User's timezone (e.g., 'America/Los_Angeles')"
    )


class UserCreate(UserBase):
    """Schema for creating a new user."""

    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_token_expiry: Optional[datetime] = None


class UserUpdate(BaseModel):
    """Schema for updating user fields."""

    full_name: Optional[str] = None
    timezone: Optional[str] = None
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_token_expiry: Optional[datetime] = None
    primary_calendar_id: Optional[str] = None


class User(UserBase):
    """Complete user model matching Supabase 'users' table."""

    id: UUID
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    timezone: str = "UTC"

    # Google OAuth tokens
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None
    google_token_expiry: Optional[datetime] = None

    # Primary calendar (one of the user's calendars)
    primary_calendar_id: Optional[str] = None

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GoogleAccount(BaseModel):
    """Google account linked to a user."""

    id: UUID
    user_id: UUID
    google_user_id: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarBase(BaseModel):
    """Base calendar fields."""

    google_calendar_id: str = Field(
        ..., description="Google Calendar ID (e.g., 'primary' or email)"
    )
    name: str = Field(..., description="Calendar name")
    description: Optional[str] = None
    color: Optional[str] = Field(None, description="Calendar color (hex code)")
    is_primary: bool = Field(
        default=False, description="Whether this is the user's primary calendar"
    )


class CalendarCreate(CalendarBase):
    """Schema for creating a new calendar."""

    user_id: UUID


class CalendarUpdate(BaseModel):
    """Schema for updating calendar fields."""

    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_primary: Optional[bool] = None


class Calendar(CalendarBase):
    """Complete calendar model matching Supabase 'calendars' table."""

    id: UUID
    user_id: UUID
    google_calendar_id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    is_primary: bool = False

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FriendBase(BaseModel):
    """Base friend fields."""

    name: str = Field(..., description="Friend's display name")
    email: EmailStr = Field(..., description="Friend's email address")
    google_calendar_id: Optional[str] = Field(
        None, description="Friend's Google Calendar ID (if shared)"
    )
    notes: Optional[str] = Field(None, description="Optional notes about the friend")


class FriendCreate(FriendBase):
    """Schema for creating a new friend."""

    user_id: UUID


class FriendUpdate(BaseModel):
    """Schema for updating friend fields."""

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    google_calendar_id: Optional[str] = None
    notes: Optional[str] = None


class Friend(FriendBase):
    """Complete friend model matching Supabase 'friends' table."""

    id: UUID
    user_id: UUID
    name: str
    email: EmailStr
    google_calendar_id: Optional[str] = None
    notes: Optional[str] = None

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarEventBase(BaseModel):
    """Base calendar event fields."""

    google_event_id: str = Field(..., description="Google Calendar event ID")
    calendar_id: UUID = Field(..., description="Calendar this event belongs to")
    summary: str = Field(..., description="Event title/summary")
    description: Optional[str] = None
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    location: Optional[str] = None
    attendees: List[str] = Field(default_factory=list, description="List of attendee emails")
    recurrence_rule: Optional[str] = Field(None, description="RRULE for recurring events")


class CalendarEventCreate(CalendarEventBase):
    """Schema for creating a new calendar event (cached in DB)."""

    pass


class CalendarEventUpdate(BaseModel):
    """Schema for updating calendar event fields."""

    summary: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    recurrence_rule: Optional[str] = None


class CalendarEvent(CalendarEventBase):
    """
    Complete calendar event model matching Supabase 'calendar_events' table.

    Note: This is a cached representation. The source of truth is Google Calendar.
    """

    id: UUID
    google_event_id: str
    calendar_id: UUID
    summary: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: List[str] = []
    recurrence_rule: Optional[str] = None

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserPreferencesBase(BaseModel):
    """Base user preferences fields."""

    default_meeting_duration: int = Field(
        default=60, description="Default meeting duration in minutes"
    )
    work_start_hour: int = Field(default=9, description="Work day start hour (0-23)")
    work_end_hour: int = Field(default=17, description="Work day end hour (0-23)")
    work_days: List[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5],
        description="Work days (1=Mon, 7=Sun)",
    )
    buffer_between_meetings: int = Field(
        default=0, description="Buffer time between meetings in minutes"
    )
    allow_overlapping_events: bool = Field(
        default=False, description="Allow creating overlapping events"
    )


class UserPreferencesCreate(UserPreferencesBase):
    """Schema for creating user preferences."""

    user_id: UUID


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences."""

    default_meeting_duration: Optional[int] = None
    work_start_hour: Optional[int] = None
    work_end_hour: Optional[int] = None
    work_days: Optional[List[int]] = None
    buffer_between_meetings: Optional[int] = None
    allow_overlapping_events: Optional[bool] = None


class UserPreferences(UserPreferencesBase):
    """Complete user preferences model matching Supabase 'user_preferences' table."""

    id: UUID
    user_id: UUID
    default_meeting_duration: int = 60
    work_start_hour: int = 9
    work_end_hour: int = 17
    work_days: List[int] = [1, 2, 3, 4, 5]
    buffer_between_meetings: int = 0
    allow_overlapping_events: bool = False

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Export all models
__all__ = [
    "User",
    "UserCreate",
    "UserUpdate",
    "Calendar",
    "CalendarCreate",
    "CalendarUpdate",
    "Friend",
    "FriendCreate",
    "FriendUpdate",
    "CalendarEvent",
    "CalendarEventCreate",
    "CalendarEventUpdate",
    "UserPreferences",
    "UserPreferencesCreate",
    "UserPreferencesUpdate",
]
