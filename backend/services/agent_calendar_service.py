"""Service for handling agent calendar operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from domains.calendars.repository import CalendarRepository
from domains.calendars.providers.google import (
    GoogleCalendarAPIError,
    GoogleCalendarCredentials,
    GoogleCalendarWrapper,
)

logger = logging.getLogger(__name__)


def get_calendar_wrapper_for_user(user_id: str) -> GoogleCalendarWrapper:
    """Get a GoogleCalendarWrapper instance for the user's first Google account."""
    repository = CalendarRepository()
    accounts = repository.get_accounts(user_id)
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="No Google account linked. Please connect a Google account first."
        )
    
    account = accounts[0]
    access_token = account.get("access_token")
    refresh_token = account.get("refresh_token")
    
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Google account missing access or refresh token."
        )
    
    credentials = GoogleCalendarCredentials(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return GoogleCalendarWrapper(credentials)


async def search_events_for_user(
    user_id: str,
    query: str,
    calendar_id: Optional[str] = None,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 250,
) -> Dict[str, Any]:
    """
    Search for events using a query string across all user calendars.
    
    If calendar_id is specified, searches only that calendar.
    Otherwise, searches across all calendars the user has access to.
    
    Args:
        user_id: User ID to search events for
        query: Free text search query to match against event fields
        calendar_id: Optional calendar ID to search in (if None, searches all calendars)
        time_min: Minimum time for events (ISO 8601 format, optional)
        time_max: Maximum time for events (ISO 8601 format, optional)
        max_results: Maximum number of events to return across all calendars
        
    Returns:
        Dictionary containing search results with events list from all calendars
    """
    wrapper = get_calendar_wrapper_for_user(user_id)
    
    # Get user's calendars from Supabase (with hidden calendars filtered out)
    repository = CalendarRepository()
    user_calendars = repository.get_calendars(user_id)  # Default include_hidden=False filters hidden calendars
    visible_calendar_ids = {cal["google_calendar_id"] for cal in user_calendars}
    
    try:
        # If a specific calendar is requested, verify it's not hidden
        if calendar_id:
            if calendar_id not in visible_calendar_ids:
                return {
                    "status": "error",
                    "error": f"Calendar {calendar_id} not found or is hidden.",
                    "count": 0,
                    "events": [],
                }
            calendars_to_search = [{"id": calendar_id}]
        else:
            # Get all calendars from Google API, but filter to only visible ones
            all_calendars = await wrapper.list_calendars(min_access_role="reader")
            # Filter to only calendars that are visible (not hidden) in Supabase
            calendars_to_search = [
                cal for cal in all_calendars
                if cal.get("id") in visible_calendar_ids
            ]
        
        # Search across all calendars
        all_formatted_events = []
        errors = []
        
        # Distribute max_results across calendars (roughly equal per calendar)
        # But ensure we don't exceed the total max_results
        per_calendar_max = max(10, max_results // max(1, len(calendars_to_search)))
        
        for calendar in calendars_to_search:
            cal_id = calendar.get("id")
            if not cal_id:
                continue
                
            try:
                result = await wrapper.search_events(
                    query=query,
                    calendar_id=cal_id,
                    time_min=time_min,
                    time_max=time_max,
                    max_results=per_calendar_max,
                )
                
                # Format the response to include event details
                events = result.get("items", [])
                calendar_name = calendar.get("summary", cal_id)
                
                for event in events:
                    all_formatted_events.append({
                        "event_id": event.get("id"),
                        "calendar_id": cal_id,
                        "calendar_name": calendar_name,
                        "summary": event.get("summary", "No title"),
                        "description": event.get("description", ""),
                        "location": event.get("location", ""),
                        "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                        "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                        "attendees": [
                            {
                                "email": att.get("email"),
                                "displayName": att.get("displayName"),
                            }
                            for att in event.get("attendees", [])
                        ],
                        "organizer": {
                            "email": event.get("organizer", {}).get("email"),
                            "displayName": event.get("organizer", {}).get("displayName"),
                        } if event.get("organizer") else None,
                    })
                    
            except GoogleCalendarAPIError as e:
                # Log error but continue searching other calendars
                error_msg = f"Error searching calendar {cal_id}: {str(e)}"
                logger.warning(f"Calendar search error user_id={user_id} calendar={cal_id}: {str(e)}")
                errors.append(error_msg)
                continue
        
        # Sort events by start time (earliest first)
        all_formatted_events.sort(
            key=lambda x: x.get("start", ""),
            reverse=False
        )
        
        # Limit to max_results
        if len(all_formatted_events) > max_results:
            all_formatted_events = all_formatted_events[:max_results]
        
        response = {
            "status": "success",
            "count": len(all_formatted_events),
            "events": all_formatted_events,
            "calendars_searched": len(calendars_to_search),
        }
        
        # Include errors if any occurred (but search was still partially successful)
        if errors:
            response["warnings"] = errors
            
        return response
        
    except GoogleCalendarAPIError as e:
        logger.error(f"Failed to search events user_id={user_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "count": 0,
            "events": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error searching events user_id={user_id}: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error": f"Unexpected error: {str(e)}",
            "count": 0,
            "events": [],
        }

