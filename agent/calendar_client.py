"""Calendar client abstraction for agent tools.

Provides a unified interface for calendar operations that can use either
mock data or real backend API calls based on environment configuration.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class CalendarClient(ABC):
    """Abstract base class for calendar clients."""

    @abstractmethod
    async def read_schedule(
        self,
        start_time: str,
        end_time: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read events from the schedule within a time window.
        
        Args:
            start_time: Timezone-aware ISO format datetime string with offset
            end_time: Timezone-aware ISO format datetime string with offset
            auth: Optional authentication dict with user_id and supabase_access_token
            
        Returns:
            List of events with id, summary, start, end, calendar_id (required fields)
        """
        pass

    @abstractmethod
    async def search_events(
        self,
        keywords: str,
        start_time: str,
        end_time: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for events matching keywords within a time window.
        
        Args:
            keywords: Space-separated keywords to search for
            start_time: Timezone-aware ISO format datetime string with offset
            end_time: Timezone-aware ISO format datetime string with offset
            auth: Optional authentication dict with user_id and supabase_access_token
            
        Returns:
            List of matching events with id, summary, start, end, calendar_id (required fields)
        """
        pass

    @abstractmethod
    async def read_event(
        self,
        event_id: str,
        calendar_id: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Read detailed information about a specific event.
        
        Args:
            event_id: The ID of the event to read
            calendar_id: The ID of the calendar containing the event
            auth: Optional authentication dict with user_id and supabase_access_token
            
        Returns:
            Detailed event information with id and calendar_id (required fields)
        """
        pass

    @abstractmethod
    async def list_calendars(
        self,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all available calendars.
        
        Args:
            auth: Optional authentication dict with user_id and supabase_access_token
            
        Returns:
            List of calendars with their details
        """
        pass


def create_calendar_client() -> CalendarClient:
    """
    Factory function to create appropriate calendar client based on environment.
    
    Uses USE_MOCK_CALENDAR environment variable:
    - If "true" or "1", returns MockClient
    - Otherwise, returns BackendClient
    
    Returns:
        CalendarClient instance (either MockClient or BackendClient)
    """
    use_mock = os.getenv("USE_MOCK_CALENDAR", "").lower() in ("true", "1")
    
    if use_mock:
        # Import mock client only when needed (for easy deletion later)
        from agent.mock_client import MockClient
        return MockClient()
    else:
        # Import backend client only when needed
        from agent.backend_client import BackendClient
        return BackendClient()
