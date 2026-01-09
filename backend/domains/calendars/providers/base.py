"""Base calendar provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CalendarProvider(ABC):
    """Abstract base class for calendar providers."""

    @abstractmethod
    async def list_calendars(
        self, min_access_role: str = "reader"
    ) -> List[Dict[str, Any]]:
        """List all calendars available to the provider."""
        ...

    @abstractmethod
    async def list_events(
        self,
        calendar_id: str,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        """List events from a calendar."""
        ...

    @abstractmethod
    async def get_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
        """Get a single event from a calendar."""
        ...

    @abstractmethod
    async def create_event(
        self,
        calendar_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new event in a calendar."""
        ...

    @abstractmethod
    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update an existing event in a calendar."""
        ...

    @abstractmethod
    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """Delete an event from a calendar."""
        ...

    @abstractmethod
    async def search_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
    ) -> Dict[str, Any]:
        """Search for events using a query string."""
        ...
