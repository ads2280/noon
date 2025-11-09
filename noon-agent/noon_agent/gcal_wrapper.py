"""Simple Google Calendar API wrapper for noon-agent."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service(
    credentials_path: str = "credentials.json", token_path: str = "token.json"
):
    """
    Create Google Calendar service using local credentials file.

    Args:
        credentials_path: Path to credentials.json file
        token_path: Path to token.json file

    Returns:
        Google Calendar API service object
    """
    creds = None

    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            # Use port 8000 - make sure this is configured in Google Cloud Console
            # as http://localhost:8000/ in Authorized redirect URIs
            creds = flow.run_local_server(port=8000, open_browser=True)

        # Save credentials for next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def create_calendar_event(
    service,
    summary: str,
    start_time: datetime,
    end_time: datetime,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    calendar_id: str = "primary",
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Create a new calendar event.

    Args:
        service: Google Calendar API service
        summary: Event title
        start_time: Event start datetime
        end_time: Event end datetime
        description: Event description (optional)
        attendees: List of attendee email addresses (optional)
        calendar_id: Calendar ID (default: "primary")
        timezone: Timezone string (default: "UTC")

    Returns:
        Dictionary with event details and status
    """
    try:
        logger.info(f"GCAL_WRAPPER: Building event body for '{summary}'")
        event_body = {
            "summary": summary,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone,
            },
        }

        if description:
            event_body["description"] = description
            logger.info(f"GCAL_WRAPPER: Added description: {description}")

        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]
            logger.info(f"GCAL_WRAPPER: Added {len(attendees)} attendees: {attendees}")

        logger.info(f"GCAL_WRAPPER: Inserting event into calendar '{calendar_id}'...")
        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        logger.info(f"GCAL_WRAPPER: Event created successfully with ID: {event['id']}")

        return {
            "status": "success",
            "event_id": event["id"],
            "summary": event["summary"],
            "start": event["start"]["dateTime"],
            "end": event["end"]["dateTime"],
            "link": event.get("htmlLink"),
        }

    except HttpError as error:
        logger.error(f"GCAL_WRAPPER: HttpError occurred: {str(error)}")
        return {
            "status": "error",
            "error": str(error),
        }


def read_calendar_events(
    service,
    calendar_id: str = "primary",
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    max_results: int = 10,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read/list calendar events.

    Args:
        service: Google Calendar API service
        calendar_id: Calendar ID (default: "primary")
        time_min: Minimum time (default: now)
        time_max: Maximum time (default: 7 days from now)
        max_results: Maximum number of events to return
        query: Free text search query (optional)

    Returns:
        Dictionary with list of events
    """
    try:
        # Default time range: now to 7 days from now
        if not time_min:
            time_min = datetime.utcnow()
        if not time_max:
            time_max = datetime.utcnow() + timedelta(days=7)

        params = {
            "calendarId": calendar_id,
            "timeMin": time_min.isoformat() + "Z",
            "timeMax": time_max.isoformat() + "Z",
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        # Add search query if provided
        if query:
            params["q"] = query

        events_result = service.events().list(**params).execute()

        events = events_result.get("items", [])

        formatted_events = []
        for event in events:
            formatted_events.append(
                {
                    "event_id": event["id"],
                    "summary": event.get("summary", "No title"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "description": event.get("description", ""),
                }
            )

        return {
            "status": "success",
            "count": len(formatted_events),
            "events": formatted_events,
        }

    except HttpError as error:
        return {
            "status": "error",
            "error": str(error),
            "events": [],
        }


def search_calendar_events(
    service,
    query: str,
    calendar_id: str = "primary",
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    max_results: int = 10,
) -> Dict[str, Any]:
    """
    Search calendar events using free text query.

    The q parameter searches all event fields including:
    - Summary (title)
    - Description
    - Location
    - Attendee names and emails

    Args:
        service: Google Calendar API service
        query: Free text search term
        calendar_id: Calendar ID (default: "primary")
        time_min: Minimum time (optional)
        time_max: Maximum time (optional)
        max_results: Maximum number of events to return

    Returns:
        Dictionary with list of matching events
    """
    return read_calendar_events(
        service=service,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        query=query,
    )


def update_calendar_event(
    service,
    event_id: str,
    summary: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Update an existing calendar event.

    Args:
        service: Google Calendar API service
        event_id: ID of the event to update
        summary: New event title (optional)
        start_time: New start datetime (optional)
        end_time: New end datetime (optional)
        description: New description (optional)
        calendar_id: Calendar ID (default: "primary")
        timezone: Timezone string (default: "UTC")

    Returns:
        Dictionary with updated event details and status
    """
    try:
        # Get existing event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Update fields
        if summary:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if start_time:
            event["start"] = {"dateTime": start_time.isoformat(), "timeZone": timezone}
        if end_time:
            event["end"] = {"dateTime": end_time.isoformat(), "timeZone": timezone}

        # Update the event
        updated_event = (
            service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        )

        return {
            "status": "success",
            "event_id": updated_event["id"],
            "summary": updated_event["summary"],
            "start": updated_event["start"].get("dateTime"),
            "end": updated_event["end"].get("dateTime"),
            "link": updated_event.get("htmlLink"),
        }

    except HttpError as error:
        return {
            "status": "error",
            "error": str(error),
        }


def delete_calendar_event(service, event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """
    Delete a calendar event.

    Args:
        service: Google Calendar API service
        event_id: ID of the event to delete
        calendar_id: Calendar ID (default: "primary")

    Returns:
        Dictionary with deletion status
    """
    try:
        # Get event details before deleting
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        event_summary = event.get("summary", "Untitled event")

        # Delete the event
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "status": "success",
            "event_id": event_id,
            "summary": event_summary,
            "message": f"Deleted event: {event_summary}",
        }

    except HttpError as error:
        return {
            "status": "error",
            "error": str(error),
        }
