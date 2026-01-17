"""Google Calendar provider implementation."""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import httpx
import jwt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import get_settings
from core.timing_logger import log_step, log_start
from domains.calendars.providers.base import CalendarProvider
from utils.errors import (
    GoogleCalendarAPIError,
    GoogleCalendarAuthError,
    GoogleOAuthError,
    GoogleStateError,
)

# Scopes required for Google Calendar API
SCOPES = ["https://www.googleapis.com/auth/calendar"]

STATE_AUDIENCE = "google-oauth-state"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
CALENDAR_LIST_ENDPOINT = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
API_BASE_URL = "https://www.googleapis.com/calendar/v3"


@dataclass(frozen=True)
class GoogleTokens:
    """Google OAuth tokens."""

    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str
    token_type: str
    id_token: str | None

    def expires_at(self, issued_at: datetime | None = None) -> datetime | None:
        """Calculate expiration time."""
        if self.expires_in is None:
            return None
        base = issued_at or datetime.now(timezone.utc)
        return base + timedelta(seconds=self.expires_in)

    @property
    def scopes(self) -> List[str]:
        """Get scopes as list."""
        if not self.scope:
            return []
        return [segment for segment in self.scope.split() if segment]


@dataclass(frozen=True)
class GoogleProfile:
    """Google user profile."""

    id: str
    email: str
    name: str | None
    picture: str | None


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
            payload = (
                error.content.decode() if hasattr(error, "content") else None
            )
            if payload:
                import json
                payload = json.loads(payload)
        except (ValueError, AttributeError):
            payload = str(error)
        return cls(
            message=str(error),
            status_code=status_code,
            payload=payload,
        )


@dataclass
class GoogleCalendarHttpClient:
    """Thin wrapper around httpx.AsyncClient for Google Calendar API requests."""

    timeout: float = 15.0
    _client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "GoogleCalendarHttpClient":
        self._client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "GoogleCalendarHttpClient must be used as an async context manager"
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request_start = time.time()
        log_start("backend.google_calendar_api.request", details=f"method={method} path={path}")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        network_start = time.time()
        response = await self.client.request(
            method,
            path,
            headers=headers,
            params=params,
        )
        network_duration = time.time() - network_start
        response_size = len(response.content) if hasattr(response, 'content') else 0
        log_step("backend.google_calendar_api.request.network", network_duration, details=f"status={response.status_code} size={response_size}")
        
        if response.status_code >= 400:
            raise GoogleCalendarAPIError(
                f"Google Calendar API request failed with status {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        
        parse_start = time.time()
        result = response.json()
        parse_duration = time.time() - parse_start
        log_step("backend.google_calendar_api.request.parse", parse_duration)
        
        request_duration = time.time() - request_start
        log_step(f"backend.google_calendar_api.request", request_duration, details=f"status={response.status_code}")
        return result

    async def get_event(
        self,
        *,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
        """Get a single event from a calendar."""
        path = f"/calendars/{_encode_path_segment(calendar_id)}/events/{_encode_path_segment(event_id)}"
        return await self._request("GET", path, access_token=access_token)

    async def list_events(
        self,
        *,
        access_token: str,
        calendar_id: str,
        time_min: str,
        time_max: str,
        max_results: int = 250,
    ) -> List[Dict[str, Any]]:
        """List events from a calendar."""
        method_start = time.time()
        log_start("backend.google_calendar_http_client.list_events", details=f"calendar_id={calendar_id}")
        
        path = f"/calendars/{_encode_path_segment(calendar_id)}/events"
        params: Dict[str, Any] = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        events: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        page_num = 0
        while True:
            if page_token:
                params["pageToken"] = page_token
            page_start = time.time()
            data = await self._request(
                "GET",
                path,
                access_token=access_token,
                params=params,
            )
            page_duration = time.time() - page_start
            items = data.get("items") or []
            if isinstance(items, list):
                events.extend(items)
            log_step(f"backend.google_calendar_http_client.list_events.page_{page_num}", page_duration, details=f"items={len(items)} total={len(events)}")
            page_num += 1
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        
        method_duration = time.time() - method_start
        log_step("backend.google_calendar_http_client.list_events", method_duration, details=f"calendar_id={calendar_id} total_events={len(events)} pages={page_num}")
        return events

    async def list_calendars(
        self,
        *,
        access_token: str,
    ) -> List[Dict[str, Any]]:
        """List calendars for the authenticated user."""
        path = "/users/me/calendarList"
        params: Dict[str, Any] = {"minAccessRole": "reader"}
        calendars: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            data = await self._request(
                "GET",
                path,
                access_token=access_token,
                params=params,
            )
            items = data.get("items") or []
            if isinstance(items, list):
                calendars.extend(items)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return calendars


def _encode_path_segment(segment: str) -> str:
    """Encode a URL path segment."""
    return quote(segment, safe="")


def _safe_json(response: httpx.Response) -> Any:
    """Safely parse JSON from response."""
    try:
        return response.json()
    except ValueError:
        return response.text


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar provider implementation."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        *,
        credentials_json_path: Optional[str] = None,
    ) -> None:
        """Initialize Google Calendar provider with credentials."""
        self._credentials = GoogleCalendarCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            credentials_json_path=credentials_json_path,
        )
        self._wrapper = None

    def _get_wrapper(self) -> "GoogleCalendarWrapper":
        """Get or create Google Calendar wrapper."""
        if self._wrapper is None:
            self._wrapper = GoogleCalendarWrapper(self._credentials)
        return self._wrapper

    async def list_calendars(
        self, min_access_role: str = "reader"
    ) -> List[Dict[str, Any]]:
        """List all calendars available to the provider."""
        wrapper = self._get_wrapper()
        return await wrapper.list_calendars(min_access_role=min_access_role)

    async def list_events(
        self,
        calendar_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        """List events from a calendar."""
        method_start = time.time()
        log_start("backend.google_calendar_provider.list_events", details=f"calendar_id={calendar_id}")
        
        wrapper_start = time.time()
        wrapper = self._get_wrapper()
        wrapper_duration = time.time() - wrapper_start
        log_step("backend.google_calendar_provider.list_events.get_wrapper", wrapper_duration)
        
        list_start = time.time()
        result = await wrapper.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
        list_duration = time.time() - list_start
        items_count = len(result) if isinstance(result, list) else len(result.get("items", [])) if isinstance(result, dict) else 0
        log_step("backend.google_calendar_provider.list_events.wrapper_call", list_duration, details=f"items={items_count}")
        
        method_duration = time.time() - method_start
        log_step("backend.google_calendar_provider.list_events", method_duration, details=f"calendar_id={calendar_id} items={items_count}")
        
        return {"items": result} if isinstance(result, list) else result

    async def get_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
        """Get a single event from a calendar."""
        wrapper = self._get_wrapper()
        return await wrapper.get_event(calendar_id=calendar_id, event_id=event_id)

    async def create_event(
        self,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new event in a calendar."""
        wrapper = self._get_wrapper()
        return await wrapper.create_event(calendar_id=calendar_id, event_data=event_data)

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing event in a calendar."""
        wrapper = self._get_wrapper()
        return await wrapper.update_event(
            calendar_id=calendar_id, event_id=event_id, event_data=event_data
        )

    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """Delete an event from a calendar."""
        wrapper = self._get_wrapper()
        await wrapper.delete_event(calendar_id=calendar_id, event_id=event_id)

    async def search_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        """Search for events using a query string."""
        wrapper = self._get_wrapper()
        return await wrapper.search_events(
            query=query,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )


class GoogleCalendarWrapper:
    """Wrapper for Google Calendar API using googleapiclient."""

    def __init__(
        self,
        credentials: GoogleCalendarCredentials,
        *,
        credentials_json_path: Optional[str] = None,
    ) -> None:
        self.credentials = credentials
        self.credentials_json_path = (
            credentials_json_path or credentials.credentials_json_path
        )
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
        execute_start = time.time()
        log_start("backend.google_calendar_wrapper._execute_request")
        try:
            result = await asyncio.to_thread(request.execute)
            execute_duration = time.time() - execute_start
            log_step("backend.google_calendar_wrapper._execute_request", execute_duration)
            return result
        except HttpError as error:
            execute_duration = time.time() - execute_start
            log_step("backend.google_calendar_wrapper._execute_request", execute_duration, details=f"ERROR: status={getattr(error, 'resp', {}).get('status', 'unknown')}")
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
    ) -> List[Dict[str, Any]]:
        """List events from a calendar."""
        method_start = time.time()
        log_start("backend.google_calendar_wrapper.list_events", details=f"calendar_id={calendar_id}")
        
        service_start = time.time()
        service = self._get_service()
        service_duration = time.time() - service_start
        log_step("backend.google_calendar_wrapper.list_events.get_service", service_duration)
        
        events: List[Dict[str, Any]] = []
        page_num = 0
        while True:
            request_start = time.time()
            request = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            request_duration = time.time() - request_start
            log_step(f"backend.google_calendar_wrapper.list_events.build_request.page_{page_num}", request_duration)
            
            execute_start = time.time()
            result = await self._execute_request(request)
            execute_duration = time.time() - execute_start
            items = result.get("items", [])
            if isinstance(items, list):
                events.extend(items)
            log_step(f"backend.google_calendar_wrapper.list_events.execute.page_{page_num}", execute_duration, details=f"items={len(items)} total_events={len(events)}")
            page_num += 1
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        
        method_duration = time.time() - method_start
        log_step("backend.google_calendar_wrapper.list_events", method_duration, details=f"calendar_id={calendar_id} total_events={len(events)} pages={page_num}")
        return events

    async def search_events(
        self,
        *,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        """Search for events using a free text query string."""
        service = self._get_service()
        params = {
            "calendarId": calendar_id,
            "q": query,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        request = service.events().list(**params)
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


# OAuth utility functions
def _state_secret() -> str:
    """Get state secret from settings."""
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET must be configured to sign Google OAuth state tokens."
        )
    return settings.supabase_jwt_secret


def create_state_token(user_id: str) -> str:
    """Create OAuth state token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": STATE_AUDIENCE,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def decode_state_token(state: str) -> Dict[str, Any]:
    """Decode OAuth state token."""
    try:
        decoded = jwt.decode(
            state,
            _state_secret(),
            algorithms=["HS256"],
            audience=STATE_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise GoogleStateError("Invalid or expired OAuth state token") from exc
    return decoded


def build_authorization_url(state: str) -> str:
    """Build Google OAuth authorization URL."""
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri_resolved,
        "response_type": "code",
        "scope": " ".join(settings.google_oauth_scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_code_for_tokens(code: str) -> GoogleTokens:
    """Exchange OAuth code for tokens."""
    settings = get_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_oauth_redirect_uri_resolved,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TOKEN_ENDPOINT, data=payload, headers={"Accept": "application/json"}
        )
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Token exchange failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleOAuthError(
            "Token exchange response did not include an access token."
        )

    return GoogleTokens(
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope", ""),
        token_type=data.get("token_type", ""),
        id_token=data.get("id_token"),
    )


async def refresh_access_token(refresh_token: str) -> GoogleTokens:
    """Refresh Google OAuth access token."""
    settings = get_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TOKEN_ENDPOINT, data=payload, headers={"Accept": "application/json"}
        )
    if response.status_code != httpx.codes.OK:
        # Parse error response to check for invalid_grant
        try:
            error_data = response.json()
            error_type = error_data.get("error")
            if error_type == "invalid_grant":
                # Refresh token is invalid/revoked - user needs to re-authenticate
                raise GoogleCalendarAuthError(
                    "Google account authentication expired. Please re-link your Google Calendar account."
                )
        except (ValueError, KeyError):
            # If we can't parse the error, fall through to generic error
            pass
        
        raise GoogleOAuthError(
            f"Token refresh failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleOAuthError(
            "Token refresh response did not include an access token."
        )

    return GoogleTokens(
        access_token=access_token,
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope", ""),
        token_type=data.get("token_type", ""),
        id_token=data.get("id_token"),
    )


async def fetch_profile(access_token: str) -> GoogleProfile:
    """Fetch Google user profile."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(USERINFO_ENDPOINT, headers=headers)
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Failed to load Google profile: {response.status_code} {response.text}"
        )
    data = response.json()
    profile_id = data.get("id") or data.get("sub")
    email = data.get("email")
    if not profile_id or not email:
        raise GoogleOAuthError("Google did not return a profile ID or email address.")

    return GoogleProfile(
        id=profile_id,
        email=email,
        name=data.get("name"),
        picture=data.get("picture"),
    )


async def fetch_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    """Fetch list of Google calendars."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {"minAccessRole": "reader"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            CALENDAR_LIST_ENDPOINT, headers=headers, params=params
        )
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Failed to load Google calendars: {response.status_code} {response.text}"
        )
    data = response.json()
    items = data.get("items") or []
    sanitized: List[Dict[str, Any]] = []
    for item in items:
        sanitized.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "access_role": item.get("accessRole"),
                "background_color": item.get("backgroundColor"),
                "foreground_color": item.get("foregroundColor"),
            }
        )
    return sanitized


def build_app_redirect_url(
    success: bool, state: str, message: str | None = None
) -> str:
    """Build app redirect URL for OAuth callback."""
    settings = get_settings()
    base = settings.google_oauth_app_redirect_uri
    params = {
        "result": "success" if success else "error",
        "state": state,
    }
    if message:
        params["message"] = message
    query = urlencode(params)
    if "?" in base:
        return f"{base}&{query}"
    return f"{base}?{query}"
