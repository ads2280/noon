"""Context management and user preference tools."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from .gcal_api import list_events_api


def load_user_context(
    service, user_id: str, timezone: str = "America/Los_Angeles"
) -> Dict[str, Any]:
    """
    Load user's calendar context.

    In production, this would load friends and preferences from a database.
    For now, we return a structure with the calendar data from the API.

    Args:
        service: Google Calendar API service
        user_id: User identifier
        timezone: User's timezone

    Returns:
        UserContext dict
    """
    # Get user's calendars
    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])

    primary_cal = None
    all_cal_ids = []

    for calendar in calendars:
        all_cal_ids.append(calendar["id"])
        if calendar.get("primary"):
            primary_cal = calendar["id"]

    # Get upcoming events (next 7 days)
    time_min = datetime.utcnow().isoformat() + "Z"
    time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

    upcoming_events = []

    if primary_cal:
        events_result = list_events_api(
            service=service,
            calendar_id=primary_cal,
            time_min=time_min,
            time_max=time_max,
            max_results=20,
        )

        for event in events_result.get("events", []):
            upcoming_events.append(
                {
                    "event_id": event["event_id"],
                    "calendar_id": event.get(
                        "calendar_id", primary_cal
                    ),  # Include calendar_id with event_id
                    "summary": event["summary"],
                    "start": event["start"],
                    "end": event["end"],
                    "attendees": event.get("attendees", []),
                }
            )

    return {
        "user_id": user_id,
        "timezone": timezone,
        "primary_calendar_id": primary_cal or "primary",
        "all_calendar_ids": all_cal_ids,
        "friends": [],  # Load from database in production
        "upcoming_events": upcoming_events,
        "access_token": "",  # This will be set from the request
    }


def acknowledge(message: str) -> Dict[str, Any]:
    """
    Simple acknowledgment for greetings/non-action messages.

    Args:
        message: User message

    Returns:
        {
            "acknowledged": True,
            "response": str
        }
    """
    return {"acknowledged": True, "response": "I'm here to help with your calendar!"}


def format_event_list(events: List[Dict[str, Any]], timezone: str = "UTC") -> str:
    """
    Format a list of events into a human-readable string.

    Args:
        events: List of event dicts
        timezone: Timezone for display

    Returns:
        Formatted string
    """
    if not events:
        return "No events found."

    lines = []
    for i, event in enumerate(events, 1):
        summary = event.get("summary", "No title")
        start = event.get("start", "")

        # Simple formatting - could be improved with proper datetime parsing
        lines.append(f"{i}. {summary} - {start}")

    return "\n".join(lines)


def parse_relative_time(
    relative_expr: str, current_time: datetime, timezone: str = "UTC"
) -> Dict[str, str]:
    """
    Parse relative time expressions like "tomorrow", "next week", "in 2 hours".

    This is a simplified version - in production you'd want a more robust parser.

    Args:
        relative_expr: Expression like "tomorrow", "next week"
        current_time: Current timestamp
        timezone: Timezone

    Returns:
        {
            "start": ISO 8601 datetime,
            "end": ISO 8601 datetime (optional)
        }
    """
    expr_lower = relative_expr.lower().strip()

    # Simple cases
    if expr_lower in ["today", "tonight"]:
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif expr_lower == "tomorrow":
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        end = start + timedelta(days=1)
    elif expr_lower in ["this week", "week"]:
        # Start of week (Monday)
        days_since_monday = current_time.weekday()
        start = current_time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=days_since_monday
        )
        end = start + timedelta(days=7)
    elif expr_lower in ["next week"]:
        days_since_monday = current_time.weekday()
        start = (
            current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=days_since_monday)
            + timedelta(days=7)
        )
        end = start + timedelta(days=7)
    else:
        # Default to next 7 days
        start = current_time
        end = current_time + timedelta(days=7)

    return {
        "start": start.isoformat() + "Z" if not start.tzinfo else start.isoformat(),
        "end": end.isoformat() + "Z" if not end.tzinfo else end.isoformat(),
    }
