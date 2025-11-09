"""High-level calendar tools that LLMs can call, with multi-calendar overlay support."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .gcal_api import (
    create_event_api,
    delete_event_api,
    get_event_details_api,
    get_freebusy_api,
    list_events_api,
    update_event_api,
)


def create_event(
    service,
    calendar_id: str,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Create a new calendar event.

    This is a direct wrapper around create_event_api for now,
    but can be extended with additional logic.
    """
    return create_event_api(
        service=service,
        calendar_id=calendar_id,
        summary=summary,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        description=description,
        attendees=attendees,
        timezone=timezone,
    )


def update_event(
    service,
    calendar_id: str,
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """Update an existing calendar event."""
    return update_event_api(
        service=service,
        calendar_id=calendar_id,
        event_id=event_id,
        summary=summary,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        description=description,
        attendees=attendees,
        timezone=timezone,
    )


def delete_event(service, calendar_id: str, event_id: str) -> Dict[str, Any]:
    """Delete a calendar event."""
    return delete_event_api(service=service, calendar_id=calendar_id, event_id=event_id)


def search_events(
    service,
    calendar_ids: List[str],
    query: str,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results_per_calendar: int = 25,
) -> Dict[str, Any]:
    """
    Search for events across multiple calendars using text matching.

    This demonstrates the overlay capability - we query multiple calendars
    and combine the results.

    Args:
        service: Google Calendar API service
        calendar_ids: List of calendar IDs to search
        query: Search query string
        time_min: ISO 8601 datetime (optional)
        time_max: ISO 8601 datetime (optional)
        max_results_per_calendar: Max results per calendar

    Returns:
        {
            "events": [...],  # Combined events from all calendars
            "count": int,
            "calendars_searched": [...]
        }
    """
    all_events = []

    for cal_id in calendar_ids:
        result = list_events_api(
            service=service,
            calendar_id=cal_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results_per_calendar,
            query=query,
        )

        if "events" in result:
            all_events.extend(result["events"])

    # Sort by start time
    all_events.sort(key=lambda e: e.get("start", ""))

    return {
        "events": all_events,
        "count": len(all_events),
        "calendars_searched": calendar_ids,
    }


def get_event_details(service, calendar_id: str, event_id: str) -> Dict[str, Any]:
    """Get full details of a specific event."""
    return get_event_details_api(service=service, calendar_id=calendar_id, event_id=event_id)


def get_schedule(
    service,
    calendar_ids: List[str],
    time_min: str,
    time_max: str,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Get all events across multiple calendars in a time range (overlay view).

    This provides a unified view of the user's schedule across all their calendars.

    Args:
        service: Google Calendar API service
        calendar_ids: List of calendar IDs to include
        time_min: ISO 8601 datetime
        time_max: ISO 8601 datetime
        timezone: Timezone string

    Returns:
        {
            "events": [...],  # All events sorted by start time
            "timezone": str,
            "date_range": {...},
            "calendars_included": [...]
        }
    """
    all_events = []

    for cal_id in calendar_ids:
        result = list_events_api(
            service=service,
            calendar_id=cal_id,
            time_min=time_min,
            time_max=time_max,
            max_results=250,
        )

        if "events" in result:
            all_events.extend(result["events"])

    # Sort by start time
    all_events.sort(key=lambda e: e.get("start", ""))

    return {
        "events": all_events,
        "timezone": timezone,
        "date_range": {"start": time_min, "end": time_max},
        "calendars_included": calendar_ids,
    }


def check_availability(
    service,
    calendar_ids: List[str],
    time_min: str,
    time_max: str,
    duration_minutes: int = 60,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Find free time slots across all of the user's calendars.

    This considers events from ALL calendars to determine when the user is truly free.

    Args:
        service: Google Calendar API service
        calendar_ids: List of calendar IDs to check
        time_min: ISO 8601 datetime
        time_max: ISO 8601 datetime
        duration_minutes: Minimum slot duration
        timezone: Timezone string

    Returns:
        {
            "free_slots": [...],
            "busy_slots": [...],
            "calendars_checked": [...]
        }
    """
    # Get free/busy info for all calendars
    freebusy_result = get_freebusy_api(
        service=service,
        calendar_ids=calendar_ids,
        time_min=time_min,
        time_max=time_max,
        timezone=timezone,
    )

    calendars_data = freebusy_result.get("calendars", {})

    # Collect all busy periods from all calendars
    all_busy_periods = []
    for cal_id in calendar_ids:
        if cal_id in calendars_data:
            busy = calendars_data[cal_id].get("busy", [])
            all_busy_periods.extend(busy)

    # Merge overlapping busy periods
    merged_busy = _merge_busy_periods(all_busy_periods)

    # Calculate free slots
    free_slots = _calculate_free_slots(
        time_min=time_min,
        time_max=time_max,
        busy_periods=merged_busy,
        duration_minutes=duration_minutes,
    )

    return {
        "free_slots": free_slots[:20],  # Limit to 20 slots
        "busy_slots": merged_busy,
        "calendars_checked": calendar_ids,
    }


def find_overlap(
    service,
    calendar_ids: List[str],
    time_min: str,
    time_max: str,
    duration_minutes: int = 60,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """
    Find mutual free time across multiple people's calendars.

    This is useful for scheduling meetings - finds times when everyone is available.

    Args:
        service: Google Calendar API service
        calendar_ids: List of calendar IDs (can include friend calendars)
        time_min: ISO 8601 datetime
        time_max: ISO 8601 datetime
        duration_minutes: Minimum slot duration
        timezone: Timezone string

    Returns:
        {
            "common_free_slots": [...],
            "participants": [...],
            "conflict_summary": {...}
        }
    """
    # Get free/busy info for all calendars
    freebusy_result = get_freebusy_api(
        service=service,
        calendar_ids=calendar_ids,
        time_min=time_min,
        time_max=time_max,
        timezone=timezone,
    )

    calendars_data = freebusy_result.get("calendars", {})

    # Collect all busy periods from all calendars
    all_busy_periods = []
    for cal_id in calendar_ids:
        if cal_id in calendars_data:
            busy = calendars_data[cal_id].get("busy", [])
            all_busy_periods.extend(busy)

    # Merge overlapping busy periods
    merged_busy = _merge_busy_periods(all_busy_periods)

    # Calculate free slots when ALL calendars are free
    free_slots = _calculate_free_slots(
        time_min=time_min,
        time_max=time_max,
        busy_periods=merged_busy,
        duration_minutes=duration_minutes,
    )

    return {
        "common_free_slots": free_slots[:20],
        "participants": calendar_ids,
        "conflict_summary": {"total_conflicts": len(merged_busy)},
    }


def _merge_busy_periods(busy_periods: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Merge overlapping busy periods.

    Args:
        busy_periods: List of {"start": ..., "end": ...} dicts

    Returns:
        Merged list of non-overlapping busy periods
    """
    if not busy_periods:
        return []

    # Sort by start time
    sorted_periods = sorted(busy_periods, key=lambda p: p["start"])

    merged = [sorted_periods[0]]

    for current in sorted_periods[1:]:
        last = merged[-1]

        # Parse timestamps
        last_end = datetime.fromisoformat(last["end"].replace("Z", "+00:00"))
        current_start = datetime.fromisoformat(current["start"].replace("Z", "+00:00"))
        current_end = datetime.fromisoformat(current["end"].replace("Z", "+00:00"))

        # If overlapping, merge
        if current_start <= last_end:
            last_end_dt = datetime.fromisoformat(last["end"].replace("Z", "+00:00"))
            merged[-1]["end"] = max(last_end_dt, current_end).isoformat()
        else:
            merged.append(current)

    return merged


def _calculate_free_slots(
    time_min: str,
    time_max: str,
    busy_periods: List[Dict[str, str]],
    duration_minutes: int,
) -> List[Dict[str, Any]]:
    """
    Calculate free time slots given busy periods.

    Args:
        time_min: ISO 8601 datetime
        time_max: ISO 8601 datetime
        busy_periods: List of busy periods
        duration_minutes: Minimum slot duration

    Returns:
        List of free slots
    """
    free_slots = []

    current_time = datetime.fromisoformat(time_min.replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(time_max.replace("Z", "+00:00"))

    # Check in 30-minute increments
    increment = timedelta(minutes=30)
    min_duration = timedelta(minutes=duration_minutes)

    while current_time < end_time:
        slot_end = current_time + min_duration

        if slot_end > end_time:
            break

        # Check if this slot overlaps with any busy period
        is_free = True
        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            # Check for overlap
            if not (slot_end <= busy_start or current_time >= busy_end):
                is_free = False
                break

        if is_free:
            free_slots.append(
                {
                    "start": current_time.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration_minutes": duration_minutes,
                }
            )

        current_time += increment

    return free_slots
