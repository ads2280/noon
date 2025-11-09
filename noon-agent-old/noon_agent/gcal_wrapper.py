"""Compatibility imports for the shared Google Calendar API wrapper."""

from __future__ import annotations

from ._backend_loader import ensure_backend_on_path as _ensure_backend_on_path

_ensure_backend_on_path()

from services.calendar_client.gcal_wrapper import (  # noqa: E402
    SCOPES,
    create_calendar_event,
    delete_calendar_event,
    get_calendar_service,
    get_event_details,
    read_calendar_events,
    search_calendar_events,
    update_calendar_event,
)

__all__ = [
    "SCOPES",
    "create_calendar_event",
    "delete_calendar_event",
    "get_calendar_service",
    "get_event_details",
    "read_calendar_events",
    "search_calendar_events",
    "update_calendar_event",
]
