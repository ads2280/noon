from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import httpx


API_BASE_URL = "https://www.googleapis.com/calendar/v3"


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


@dataclass
class GoogleCalendarHttpClient:
    """
    Thin wrapper around httpx.AsyncClient for Google Calendar API requests.
    """

    timeout: float = 15.0

    def __post_init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GoogleCalendarHttpClient":
        self._client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
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
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        response = await self.client.request(
            method,
            path,
            headers=headers,
            params=params,
        )
        if response.status_code >= 400:
            raise GoogleCalendarAPIError(
                f"Google Calendar API request failed with status {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )
        return response.json()

    async def get_event(
        self,
        *,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
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
            if isinstance(items, Iterable):
                events.extend(item for item in items if isinstance(item, dict))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return events

    async def list_calendars(
        self,
        *,
        access_token: str,
    ) -> List[Dict[str, Any]]:
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
            if isinstance(items, Iterable):
                calendars.extend(item for item in items if isinstance(item, dict))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return calendars


def _encode_path_segment(segment: str) -> str:
    return quote(segment, safe="")


def _safe_json(response: httpx.Response) -> Any:  # pragma: no cover - defensive
    try:
        return response.json()
    except ValueError:
        return response.text
