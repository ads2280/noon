"""Google Calendar API wrapper that takes OAuth credentials and credentials.json."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import get_settings

# Scopes required for Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass
class GoogleCalendarCredentials:
    """OAuth credentials for Google Calendar API."""

    access_token: str
    refresh_token: str
    credentials_json_path: Optional[str] = None

    def to_google_credentials(self) -> Credentials:
        """Convert to google.oauth2.credentials.Credentials object."""
        settings = get_settings()
        creds = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )
        return creds

    def refresh_if_needed(self) -> None:
        """Refresh the access token if it's expired."""
        creds = self.to_google_credentials()
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.access_token = creds.token
            if creds.refresh_token:
                self.refresh_token = creds.refresh_token


class GoogleCalendarAPIError(RuntimeError):
    """Raised when the Google Calendar REST API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload

    @classmethod
    def from_http_error(cls, error: HttpError) -> "GoogleCalendarAPIError":
        """Create a GoogleCalendarAPIError from a googleapiclient.errors.HttpError."""
        status_code = error.resp.status if hasattr(error, "resp") else 500
        try:
            payload = json.loads(error.content.decode()) if hasattr(error, "content") else None
        except (ValueError, AttributeError):
            payload = str(error)
        return cls(
            message=str(error),
            status_code=status_code,
            payload=payload,
        )


class GoogleCalendarWrapper:
    """
    Wrapper for Google Calendar API that takes OAuth credentials.
    
    This service handles authentication and makes requests to the Google Calendar API
    using the official Google Calendar API Python client library.
    """

    def __init__(
        self,
        credentials: GoogleCalendarCredentials,
        *,
        credentials_json_path: Optional[str] = None,
    ) -> None:
        self.credentials = credentials
        self.credentials_json_path = credentials_json_path or credentials.credentials_json_path
        self._service = None

    def _get_service(self):
        """Get or create the Google Calendar API service."""
        if self._service is None:
            creds = self.credentials.to_google_credentials()
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.credentials.access_token = creds.token
                if creds.refresh_token:
                    self.credentials.refresh_token = creds.refresh_token
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    async def _execute_request(self, request):
        """Execute a Google API request asynchronously."""
        try:
            # Run the synchronous API call in a thread pool
            return await asyncio.to_thread(request.execute)
        except HttpError as error:
            raise GoogleCalendarAPIError.from_http_error(error) from error

    async def get_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
        """Get a single event from a calendar."""
        service = self._get_service()
        request = service.events().get(calendarId=calendar_id, eventId=event_id)
        return await self._execute_request(request)

    async def list_events(
        self,
        *,
        calendar_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List events from a calendar."""
        service = self._get_service()
        request = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
        )
        return await self._execute_request(request)

    async def create_event(
        self,
        *,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new event in a calendar."""
        service = self._get_service()
        request = service.events().insert(calendarId=calendar_id, body=event_data)
        return await self._execute_request(request)

    async def update_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing event in a calendar."""
        service = self._get_service()
        request = service.events().update(
            calendarId=calendar_id, eventId=event_id, body=event_data
        )
        return await self._execute_request(request)

    async def patch_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Partially update an existing event in a calendar."""
        service = self._get_service()
        request = service.events().patch(
            calendarId=calendar_id, eventId=event_id, body=event_data
        )
        return await self._execute_request(request)

    async def delete_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """Delete an event from a calendar."""
        service = self._get_service()
        request = service.events().delete(calendarId=calendar_id, eventId=event_id)
        await self._execute_request(request)

    async def list_calendars(
        self,
        *,
        min_access_role: str = "reader",
    ) -> List[Dict[str, Any]]:
        """List calendars for the authenticated user."""
        service = self._get_service()
        calendars: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            request = service.calendarList().list(
                minAccessRole=min_access_role, pageToken=page_token
            )
            result = await self._execute_request(request)
            items = result.get("items", [])
            if isinstance(items, list):
                calendars.extend(items)
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return calendars

