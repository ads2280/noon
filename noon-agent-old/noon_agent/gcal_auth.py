"""Compatibility imports for the shared Google Calendar auth helpers."""

from __future__ import annotations

from ._backend_loader import ensure_backend_on_path as _ensure_backend_on_path

_ensure_backend_on_path()

from services.calendar_client.auth import (  # noqa: E402
    CalendarService,
    get_calendar_service,
    get_calendar_service_from_file,
)

__all__ = [
    "CalendarService",
    "get_calendar_service",
    "get_calendar_service_from_file",
]
