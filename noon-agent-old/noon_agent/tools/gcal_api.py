"""Low-level Google Calendar API operations for single calendars."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError


def create_event_api(
    service,
    calendar_id: str,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Create a new calendar event via Google Calendar API.

    Args:
        service: Google Calendar API service
        calendar_id: Calendar ID (usually 'primary')
        summary: Event title
        start_datetime: ISO 8601 datetime string
        end_datetime: ISO 8601 datetime string
        description: Event description
        attendees: List of email addresses
        timezone: Timezone string

    Returns:
        {
            "action_id": str,
            "event_id": str,
            "status": "success",
            "details": {...}
        }
    """
    try:
        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_datetime,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": timezone,
            },
        }

        if description:
            event_body["description"] = description

        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()

        return {
            "action_id": str(uuid.uuid4()),
            "event_id": event["id"],
            "calendar_id": calendar_id,  # Include calendar_id with event_id
            "status": "success",
            "details": {
                "summary": event["summary"],
                "start": event["start"]["dateTime"],
                "end": event["end"]["dateTime"],
                "event_link": event.get("htmlLink"),
            },
        }

    except HttpError as error:
        return {
            "action_id": str(uuid.uuid4()),
            "event_id": None,
            "status": "failed",
            "error": str(error),
        }


def update_event_api(
    service,
    calendar_id: str,
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """Update an existing calendar event."""
    try:
        # First get the existing event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Update fields
        if summary:
            event["summary"] = summary
        if description:
            event["description"] = description
        if start_datetime:
            event["start"] = {"dateTime": start_datetime, "timeZone": timezone}
        if end_datetime:
            event["end"] = {"dateTime": end_datetime, "timeZone": timezone}
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]

        # Update the event
        updated_event = (
            service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        )

        return {
            "action_id": str(uuid.uuid4()),
            "event_id": updated_event["id"],
            "calendar_id": calendar_id,  # Include calendar_id with event_id
            "status": "success",
            "details": {
                "summary": updated_event["summary"],
                "start": updated_event["start"].get("dateTime"),
                "end": updated_event["end"].get("dateTime"),
                "event_link": updated_event.get("htmlLink"),
            },
        }

    except HttpError as error:
        return {
            "action_id": str(uuid.uuid4()),
            "event_id": event_id,
            "status": "failed",
            "error": str(error),
        }


def delete_event_api(service, calendar_id: str, event_id: str) -> Dict[str, Any]:
    """Delete a calendar event."""
    try:
        # Get event details before deleting
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Delete the event
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "action_id": str(uuid.uuid4()),
            "event_id": event_id,
            "calendar_id": calendar_id,  # Include calendar_id with event_id
            "status": "success",
            "details": {
                "deleted_event": {
                    "summary": event.get("summary"),
                    "start": event["start"].get("dateTime"),
                }
            },
        }

    except HttpError as error:
        return {
            "action_id": str(uuid.uuid4()),
            "event_id": event_id,
            "status": "failed",
            "error": str(error),
        }


def list_events_api(
    service,
    calendar_id: str,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 250,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List events from a single calendar.

    Args:
        service: Google Calendar API service
        calendar_id: Calendar ID
        time_min: ISO 8601 datetime (optional)
        time_max: ISO 8601 datetime (optional)
        max_results: Maximum number of results
        query: Search query string (optional)

    Returns:
        {
            "events": [...],
            "calendar_id": str
        }
    """
    try:
        # Default time range: now to 7 days from now
        if not time_min:
            time_min = datetime.utcnow().isoformat() + "Z"
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

        params = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if query:
            params["q"] = query

        events_result = service.events().list(**params).execute()

        events = events_result.get("items", [])

        formatted_events = []
        for event in events:
            formatted_events.append(
                {
                    "event_id": event["id"],
                    "calendar_id": calendar_id,  # Include calendar_id with event_id
                    "summary": event.get("summary", "No title"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "attendees": [a["email"] for a in event.get("attendees", [])],
                }
            )

        return {"events": formatted_events, "calendar_id": calendar_id}

    except HttpError as error:
        return {"events": [], "calendar_id": calendar_id, "error": str(error)}


def get_event_details_api(service, calendar_id: str, event_id: str) -> Dict[str, Any]:
    """Get full details of a specific event."""
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "event_id": event["id"],
            "calendar_id": calendar_id,  # Include calendar_id with event_id
            "summary": event.get("summary", "No title"),
            "description": event.get("description", ""),
            "start": event["start"].get("dateTime", event["start"].get("date")),
            "end": event["end"].get("dateTime", event["end"].get("date")),
            "attendees": [
                {
                    "email": a["email"],
                    "displayName": a.get("displayName", ""),
                    "responseStatus": a.get("responseStatus", "needsAction"),
                }
                for a in event.get("attendees", [])
            ],
            "event_link": event.get("htmlLink"),
            "created": event.get("created"),
            "updated": event.get("updated"),
        }

    except HttpError as error:
        return {"error": str(error)}


def get_freebusy_api(
    service, calendar_ids: List[str], time_min: str, time_max: str, timezone: str = "UTC"
) -> Dict[str, Any]:
    """
    Get free/busy information for multiple calendars.

    Args:
        service: Google Calendar API service
        calendar_ids: List of calendar IDs
        time_min: ISO 8601 datetime
        time_max: ISO 8601 datetime
        timezone: Timezone string

    Returns:
        {
            "calendars": {
                "calendar_id": {
                    "busy": [{"start": ..., "end": ...}]
                }
            }
        }
    """
    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": timezone,
            "items": [{"id": cal_id} for cal_id in calendar_ids],
        }

        freebusy_result = service.freebusy().query(body=body).execute()

        return {"calendars": freebusy_result.get("calendars", {}), "timezone": timezone}

    except HttpError as error:
        return {"calendars": {}, "error": str(error)}
