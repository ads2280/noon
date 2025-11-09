"""Abstraction layer for Google Calendar operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .auth import get_calendar_service, get_calendar_service_from_file
from .gcal_wrapper import (
    create_calendar_event,
    delete_calendar_event,
    read_calendar_events,
    search_calendar_events,
    update_calendar_event,
)

logger = logging.getLogger(__name__)


class CalendarServiceError(Exception):
    """Raised for invalid requests to the calendar service."""


class CalendarService:
    """Encapsulates Google Calendar API interactions for the Noon agent."""

    def __init__(
        self,
        service_factory=get_calendar_service,
        *,
        use_token_file: bool = True,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
    ):
        self._service_factory = service_factory
        self._use_token_file = use_token_file
        self._credentials_path = credentials_path
        self._token_path = token_path

    def _build_service(self, auth_token: Optional[str]):
        if auth_token:
            logger.debug("CALENDAR_SERVICE: Building Google client with request token")
            return self._service_factory(auth_token)
        if self._use_token_file:
            logger.debug(
                "CALENDAR_SERVICE: Building Google client from token file %s",
                self._token_path,
            )
            return get_calendar_service_from_file(
                self._credentials_path, self._token_path
            )
        raise CalendarServiceError("No authentication token provided")

    @staticmethod
    def _resolve_calendar_id(
        explicit_calendar_id: Optional[str], context: Optional[Dict[str, Any]]
    ) -> str:
        if explicit_calendar_id:
            return explicit_calendar_id
        if context:
            return context.get("primary_calendar_id", "primary")
        return "primary"

    @staticmethod
    def _resolve_timezone(context: Optional[Dict[str, Any]]) -> str:
        if context:
            return context.get("timezone", "UTC")
        return "UTC"

    def create_event(
        self,
        *,
        auth_token: Optional[str],
        summary: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not start_time or not end_time:
            raise CalendarServiceError(
                "start_time and end_time are required to create an event"
            )

        service = self._build_service(auth_token)
        resolved_calendar_id = self._resolve_calendar_id(calendar_id, context)
        timezone = self._resolve_timezone(context)

        logger.info(
            "CALENDAR_SERVICE: Creating event '%s' on calendar '%s'",
            summary,
            resolved_calendar_id,
        )
        return create_calendar_event(
            service=service,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description,
            attendees=attendees,
            calendar_id=resolved_calendar_id,
            timezone=timezone,
        )

    def read_events(
        self,
        *,
        auth_token: Optional[str],
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        query: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        service = self._build_service(auth_token)
        resolved_calendar_id = self._resolve_calendar_id(calendar_id, context)

        logger.info(
            "CALENDAR_SERVICE: Reading events on calendar '%s' (query=%s)",
            resolved_calendar_id,
            query,
        )
        return read_calendar_events(
            service=service,
            calendar_id=resolved_calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            query=query,
        )

    def get_schedule(
        self,
        *,
        auth_token: Optional[str],
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> Dict[str, Any]:
        if not start_time or not end_time:
            raise CalendarServiceError(
                "start_time and end_time are required to retrieve a schedule view"
            )

        return self.read_events(
            auth_token=auth_token,
            calendar_id=calendar_id,
            context=context,
            time_min=start_time,
            time_max=end_time,
            max_results=500,
            query=None,
        )

    def update_event(
        self,
        *,
        auth_token: Optional[str],
        event_id: Optional[str],
        summary: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not event_id:
            raise CalendarServiceError("event_id is required to update an event")

        service = self._build_service(auth_token)
        resolved_calendar_id = self._resolve_calendar_id(calendar_id, context)
        timezone = self._resolve_timezone(context)

        logger.info(
            "CALENDAR_SERVICE: Updating event '%s' on calendar '%s'",
            event_id,
            resolved_calendar_id,
        )
        return update_calendar_event(
            service=service,
            event_id=event_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description,
            calendar_id=resolved_calendar_id,
            timezone=timezone,
        )

    def delete_event(
        self,
        *,
        auth_token: Optional[str],
        event_id: Optional[str],
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not event_id:
            raise CalendarServiceError("event_id is required to delete an event")

        service = self._build_service(auth_token)
        resolved_calendar_id = self._resolve_calendar_id(calendar_id, context)

        logger.info(
            "CALENDAR_SERVICE: Deleting event '%s' from calendar '%s'",
            event_id,
            resolved_calendar_id,
        )
        return delete_calendar_event(
            service=service,
            event_id=event_id,
            calendar_id=resolved_calendar_id,
        )

    def search_events(
        self,
        *,
        auth_token: Optional[str],
        query: Optional[str],
        calendar_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        if not query:
            raise CalendarServiceError("query is required to search events")

        service = self._build_service(auth_token)
        resolved_calendar_id = self._resolve_calendar_id(calendar_id, context)

        logger.info(
            "CALENDAR_SERVICE: Searching events on calendar '%s' for query '%s'",
            resolved_calendar_id,
            query,
        )
        return search_calendar_events(
            service=service,
            query=query,
            calendar_id=resolved_calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
