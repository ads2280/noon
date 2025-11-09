"""State definitions for calendar operations in the LangGraph workflow."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from typing_extensions import TypedDict


class Friend(TypedDict):
    """Friend information for calendar operations."""

    name: str
    email: str
    calendar_id: str


class CalendarEvent(TypedDict):
    """Simplified event structure."""

    event_id: str
    calendar_id: str  # Required with event_id (event IDs are unique per calendar)
    summary: str
    start: str  # ISO 8601 format
    end: str
    attendees: Optional[List[str]]


class UserContext(TypedDict):
    """User's calendar context."""

    user_id: str
    timezone: str
    primary_calendar_id: str
    all_calendar_ids: List[str]  # All calendars user has access to
    friends: List[Friend]
    upcoming_events: List[CalendarEvent]  # Next 7 days, cached
    access_token: str  # Google Calendar OAuth token


class Action(TypedDict):
    """Represents a completed action."""

    action_id: str
    type: str  # create, update, delete, read
    event_id: Optional[str]
    calendar_id: Optional[str]  # Required with event_id (event IDs are unique per calendar)
    details: Dict[str, Any]
    status: str  # success, failed
    error: Optional[str]


class CalendarAgentState(TypedDict):
    """Main state that flows through the calendar graph."""

    # User input
    input: str

    # Current timestamp (for reference like "today", "tomorrow")
    current_time: datetime

    # User context (includes auth token)
    user_context: UserContext

    # LLM's parsed intent and parameters (set by routing node)
    intent: Optional[str]  # "create_event", "find_availability", "search_events", etc.
    parameters: Optional[Dict[str, Any]]  # Extracted parameters from input

    # Tool execution result
    result: Optional[Dict[str, Any]]

    # For clarifications
    needs_clarification: bool
    clarification_message: Optional[str]
    clarification_options: Optional[List[str]]

    # Error handling
    error: Optional[str]

    # Final response to user
    response: Optional[str]
