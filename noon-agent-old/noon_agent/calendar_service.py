"""Compatibility wrapper that re-exports the shared calendar service."""

from __future__ import annotations

from ._backend_loader import ensure_backend_on_path as _ensure_backend_on_path

_ensure_backend_on_path()

from services.calendar_client import (  # noqa: E402  (import after path tweak)
    CalendarService,
    CalendarServiceError,
    get_calendar_service,
    get_calendar_service_from_file,
)
from services.calendar_client.gcal_wrapper import (  # noqa: E402
    create_calendar_event,
    delete_calendar_event,
    read_calendar_events,
    search_calendar_events,
    update_calendar_event,
)

__all__ = [
    "CalendarService",
    "CalendarServiceError",
    "get_calendar_service",
    "get_calendar_service_from_file",
    "create_calendar_event",
    "delete_calendar_event",
    "read_calendar_events",
    "search_calendar_events",
    "update_calendar_event",
]
