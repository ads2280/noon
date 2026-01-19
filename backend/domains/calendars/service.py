"""Service for calendar business logic."""

from __future__ import annotations

import asyncio
import logging
import time as time_module
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from domains.calendars.providers.base import CalendarProvider
from core.timing_logger import log_step, log_start
from domains.calendars.providers.google import (
    GoogleCalendarProvider,
    GoogleCalendarHttpClient,
    refresh_access_token,
)
from domains.calendars.repository import CalendarRepository
from domains.calendars.schemas import (
    AllDayEventTime,
    EventTime,
    TimedEventTime,
)
from utils.errors import (
    GoogleCalendarServiceError,
    GoogleCalendarUserError,
    GoogleCalendarAuthError,
    GoogleCalendarEventNotFoundError,
    GoogleCalendarAPIError,
    SupabaseStorageError,
)


TOKEN_REFRESH_LEEWAY = timedelta(minutes=5)

logger = logging.getLogger(__name__)


@dataclass
class AccountContext:
    """Context for a calendar account."""

    account: Dict[str, Any]
    access_token: str
    provider: CalendarProvider
    calendars: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def id(self) -> str | None:
        return self.account.get("id")

    @property
    def email(self) -> str | None:
        return self.account.get("email")

    @property
    def user_id(self) -> str | None:
        return self.account.get("user_id")


class CalendarService:
    """Service for calendar operations."""

    def __init__(
        self,
        repository: CalendarRepository | None = None,
    ) -> None:
        """Initialize calendar service with repository."""
        self.repository = repository or CalendarRepository()
    
    def _validate_calendar_id(self, calendar_id: str) -> None:
        """
        Validate calendar ID format.
        
        Google Calendar IDs must be in one of these formats:
        - Email address: "user@example.com" (primary calendar)
        - Special ID: "primary" 
        - Full calendar ID: "id@group.calendar.google.com" or "id@import.calendar.google.com"
        
        Args:
            calendar_id: Calendar ID to validate
            
        Raises:
            GoogleCalendarUserError: If calendar ID format is invalid
        """
        # Allow "primary" as a special case
        if calendar_id == "primary":
            return
        
        # Must be email format or have a calendar suffix
        if "@" not in calendar_id:
            raise GoogleCalendarUserError(
                f"Invalid calendar ID format: '{calendar_id}'. "
                "Calendar IDs must be full Google Calendar IDs (e.g., 'id@group.calendar.google.com') "
                "or email addresses for primary calendars. "
                "Did you truncate the ID? Check the 'id' field from list_calendars() or event responses."
            )

    async def events_for_date_range(
        self,
        *,
        user_id: str,
        start_date: date,
        end_date: date,
        timezone_name: str,
    ) -> Dict[str, Any]:
        """Get events for a date range."""
        method_start = time_module.time()
        log_start("backend.calendar_service.events_for_date_range", details=f"user_id={user_id} start={start_date} end={end_date}")
        
        prepare_start = time_module.time()
        contexts, calendars_by_id = await self._prepare_context(user_id)
        prepare_duration = time_module.time() - prepare_start
        log_step("backend.calendar_service.events_for_date_range.prepare_context", prepare_duration, details=f"contexts={len(contexts)} calendars={len(calendars_by_id)}")
        
        window = _window_from_dates(start_date, end_date, timezone_name)

        events_start = time_module.time()
        events = await self._events_for_window(
            contexts,
            calendars_by_id,
            timezone_name,
            window,
        )
        events_duration = time_module.time() - events_start
        log_step("backend.calendar_service.events_for_date_range.events_for_window", events_duration, details=f"event_count={len(events)}")

        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service.events_for_date_range", method_duration, details=f"event_count={len(events)}")
        
        return {
            "window": _window_to_response(window),
            "events": events,
        }

    async def get_event(
        self,
        *,
        user_id: str,
        calendar_id: str,
        event_id: str,
    ) -> Dict[str, Any]:
        """Get a single event."""
        contexts, calendars_by_id = await self._prepare_context(user_id)

        # Find the account context that has access to this calendar using Supabase data
        # Validate calendar ID format first
        self._validate_calendar_id(calendar_id)
        supabase_calendar = calendars_by_id.get(calendar_id)
        if not supabase_calendar:
            raise GoogleCalendarEventNotFoundError(
                f"Calendar {calendar_id} not found in any linked Google account."
            )
        
        account_id = supabase_calendar["google_account_id"]
        event_context = next((ctx for ctx in contexts if ctx.id == account_id), None)
        if not event_context:
            raise GoogleCalendarEventNotFoundError(
                f"Account for calendar {calendar_id} not found."
            )

        # Get the event via provider
        try:
            event_payload = await event_context.provider.get_event(
                calendar_id=calendar_id,
                event_id=event_id,
            )
        except GoogleCalendarAPIError as exc:
            if exc.status_code == 401:
                await self._handle_unauthorized(event_context)
                event_payload = await event_context.provider.get_event(
                    calendar_id=calendar_id,
                    event_id=event_id,
                )
            elif exc.status_code == 404:
                raise GoogleCalendarEventNotFoundError(
                    f"Event {event_id} not found in calendar {calendar_id}."
                ) from exc
            else:
                raise GoogleCalendarServiceError(
                    f"Failed to fetch event from Google Calendar: {str(exc)}"
                ) from exc

        # Convert Supabase calendar to Google format for _build_event_payload
        calendar_dict = {
            "id": supabase_calendar["google_calendar_id"],
            "summary": supabase_calendar.get("name") or supabase_calendar["google_calendar_id"],
            "backgroundColor": supabase_calendar.get("color"),
            "primary": supabase_calendar.get("is_primary", False),
            "accessRole": supabase_calendar.get("access_role"),
        }

        return _build_event_payload(
            event_payload,
            calendar_dict,
            event_context,
            supabase_calendar,
        )

    async def create_event(
        self,
        *,
        user_id: str,
        calendar_id: str,
        summary: str,
        start: EventTime,
        end: EventTime,
        description: str | None = None,
        location: str | None = None,
        timezone_name: str = "UTC",
    ) -> Dict[str, Any]:
        """Create a new event in Google Calendar.
        
        Args:
            user_id: User ID
            calendar_id: Calendar ID
            summary: Event summary/title
            start: Start time (TimedEventTime or AllDayEventTime)
            end: End time (TimedEventTime or AllDayEventTime)
            description: Optional description
            location: Optional location
            timezone_name: Timezone name (only used for timed events, defaults to UTC)
        """
        contexts, calendars_by_id = await self._prepare_context(user_id)

        # Find the account context that has access to this calendar using Supabase data
        # Validate calendar ID format first
        self._validate_calendar_id(calendar_id)
        supabase_calendar = calendars_by_id.get(calendar_id)
        if not supabase_calendar:
            raise GoogleCalendarUserError(
                f"Calendar {calendar_id} not found in any linked Google account."
            )
        
        account_id = supabase_calendar["google_account_id"]
        event_context = next((ctx for ctx in contexts if ctx.id == account_id), None)
        if not event_context:
            raise GoogleCalendarUserError(
                f"Account for calendar {calendar_id} not found."
            )

        # Format event data for Google Calendar API using pattern matching
        event_data: Dict[str, Any] = {
            "summary": summary,
        }
        
        if isinstance(start, AllDayEventTime) and isinstance(end, AllDayEventTime):
            # All-day event - use date fields (no timezone)
            event_data["start"] = {
                "date": start.date.isoformat(),  # Format: "YYYY-MM-DD"
            }
            event_data["end"] = {
                "date": end.date.isoformat(),  # Format: "YYYY-MM-DD" (exclusive)
            }
        elif isinstance(start, TimedEventTime) and isinstance(end, TimedEventTime):
            # Timed event - use dateTime fields with timezone
            tz_name = start.time_zone or timezone_name
            tz = ZoneInfo(tz_name)
            start_dt = start.date_time.replace(tzinfo=tz) if start.date_time.tzinfo is None else start.date_time.astimezone(tz)
            end_dt = end.date_time.replace(tzinfo=tz) if end.date_time.tzinfo is None else end.date_time.astimezone(tz)
            
            event_data["start"] = {
                "dateTime": start_dt.isoformat(),
                "timeZone": tz_name,
            }
            event_data["end"] = {
                "dateTime": end_dt.isoformat(),
                "timeZone": tz_name,
            }
        else:
            raise GoogleCalendarUserError(
                "Start and end must both be timed or both be all-day events"
            )

        if description:
            event_data["description"] = description
        if location:
            event_data["location"] = location

        # Create the event via provider
        try:
            created_event = await event_context.provider.create_event(
                calendar_id=calendar_id,
                event_data=event_data,
            )
        except GoogleCalendarAPIError as exc:
            if exc.status_code == 401:
                await self._handle_unauthorized(event_context)
                created_event = await event_context.provider.create_event(
                    calendar_id=calendar_id,
                    event_data=event_data,
                )
            elif exc.status_code == 403:
                # Preserve 403 errors so they can be handled properly in the endpoint
                # The endpoint has specific logic to return user-friendly messages for 403
                raise
            else:
                raise GoogleCalendarServiceError(
                    f"Failed to create event in Google Calendar: {str(exc)}"
                ) from exc

        # Convert Supabase calendar to Google format for _build_event_payload
        calendar_dict = {
            "id": supabase_calendar["google_calendar_id"],
            "summary": supabase_calendar.get("name") or supabase_calendar["google_calendar_id"],
            "backgroundColor": supabase_calendar.get("color"),
            "primary": supabase_calendar.get("is_primary", False),
            "accessRole": supabase_calendar.get("access_role"),
        }
        
        # Build response payload similar to _build_event_payload
        return _build_event_payload(
            created_event,
            calendar_dict,
            event_context,
            supabase_calendar,
        )

    async def update_event(
        self,
        *,
        user_id: str,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start: EventTime | None = None,
        end: EventTime | None = None,
        description: str | None = None,
        location: str | None = None,
        timezone_name: str = "UTC",
    ) -> Dict[str, Any]:
        """Update an existing event in Google Calendar.
        
        Args:
            user_id: User ID
            calendar_id: Calendar ID
            event_id: Event ID
            summary: Optional new summary/title
            start: Optional new start time (TimedEventTime or AllDayEventTime)
            end: Optional new end time (TimedEventTime or AllDayEventTime)
            description: Optional new description
            location: Optional new location
            timezone_name: Timezone name (only used for timed events, defaults to UTC)
        """
        contexts, calendars_by_id = await self._prepare_context(user_id)

        # Find the account context that has access to this calendar using Supabase data
        # Validate calendar ID format first
        self._validate_calendar_id(calendar_id)
        supabase_calendar = calendars_by_id.get(calendar_id)
        if not supabase_calendar:
            raise GoogleCalendarUserError(
                f"Calendar {calendar_id} not found in any linked Google account."
            )
        
        account_id = supabase_calendar["google_account_id"]
        event_context = next((ctx for ctx in contexts if ctx.id == account_id), None)
        if not event_context:
            raise GoogleCalendarUserError(
                f"Account for calendar {calendar_id} not found."
            )

        # Fetch the current event to preserve fields that aren't being updated.
        # Principle: Only update fields explicitly provided; leave everything else AS IS.
        try:
            current_event = await event_context.provider.get_event(
                calendar_id=calendar_id,
                event_id=event_id,
            )
        except GoogleCalendarAPIError as exc:
            if exc.status_code == 401:
                await self._handle_unauthorized(event_context)
                current_event = await event_context.provider.get_event(
                    calendar_id=calendar_id,
                    event_id=event_id,
                )
            else:
                raise GoogleCalendarServiceError(
                    f"Failed to fetch event for update: {str(exc)}"
                ) from exc

        # Build update payload: only include fields to UPDATE, preserve everything else AS IS
        event_data: Dict[str, Any] = {}

        # Summary: update if provided, otherwise preserve existing
        if summary is not None:
            event_data["summary"] = summary
        elif current_event.get("summary"):
            event_data["summary"] = current_event["summary"]

        # Get current start/end from the event (needed for all code paths)
        current_start = current_event.get("start", {})
        current_end = current_event.get("end", {})

        # Handle start/end updates using pattern matching
        if start is not None and end is not None:
            # Both start and end provided - use them directly
            if isinstance(start, AllDayEventTime) and isinstance(end, AllDayEventTime):
                event_data["start"] = {"date": start.date.isoformat()}
                event_data["end"] = {"date": end.date.isoformat()}
            elif isinstance(start, TimedEventTime) and isinstance(end, TimedEventTime):
                tz_name = start.time_zone or timezone_name
                tz = ZoneInfo(tz_name)
                start_dt = start.date_time.replace(tzinfo=tz) if start.date_time.tzinfo is None else start.date_time.astimezone(tz)
                end_dt = end.date_time.replace(tzinfo=tz) if end.date_time.tzinfo is None else end.date_time.astimezone(tz)
                event_data["start"] = {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": tz_name,
                }
                event_data["end"] = {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": tz_name,
                }
            else:
                raise GoogleCalendarUserError(
                    "Start and end must both be timed or both be all-day events"
                )
        elif start is not None:
            # Only start provided - need to handle conversion
            if isinstance(start, AllDayEventTime):
                event_data["start"] = {"date": start.date.isoformat()}
                # Preserve existing end, converting if needed
                if "date" in current_end:
                    event_data["end"] = {"date": current_end["date"]}
                elif "dateTime" in current_end:
                    # Converting from timed to all-day - need end too
                    raise GoogleCalendarUserError(
                        "Cannot convert timed event to all-day without providing end date"
                    )
            elif isinstance(start, TimedEventTime):
                tz_name = start.time_zone or timezone_name
                tz = ZoneInfo(tz_name)
                start_dt = start.date_time.replace(tzinfo=tz) if start.date_time.tzinfo is None else start.date_time.astimezone(tz)
                event_data["start"] = {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": tz_name,
                }
                # Preserve existing end
                if "dateTime" in current_end:
                    event_data["end"] = {
                        "dateTime": current_end["dateTime"],
                        "timeZone": current_end.get("timeZone", tz_name),
                    }
                elif "date" in current_end:
                    # Converting from all-day to timed - need end too
                    raise GoogleCalendarUserError(
                        "Cannot convert all-day event to timed without providing end datetime"
                    )
        elif end is not None:
            # Only end provided - need to handle conversion
            if isinstance(end, AllDayEventTime):
                event_data["end"] = {"date": end.date.isoformat()}
                # Preserve existing start, converting if needed
                if "date" in current_start:
                    event_data["start"] = {"date": current_start["date"]}
                elif "dateTime" in current_start:
                    # Converting from timed to all-day - need start too
                    raise GoogleCalendarUserError(
                        "Cannot convert timed event to all-day without providing start date"
                    )
            elif isinstance(end, TimedEventTime):
                tz_name = end.time_zone or timezone_name
                tz = ZoneInfo(tz_name)
                end_dt = end.date_time.replace(tzinfo=tz) if end.date_time.tzinfo is None else end.date_time.astimezone(tz)
                event_data["end"] = {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": tz_name,
                }
                # Preserve existing start
                if "dateTime" in current_start:
                    event_data["start"] = {
                        "dateTime": current_start["dateTime"],
                        "timeZone": current_start.get("timeZone", tz_name),
                    }
                elif "date" in current_start:
                    # Converting from all-day to timed - need start too
                    raise GoogleCalendarUserError(
                        "Cannot convert all-day event to timed without providing start datetime"
                    )
        else:
            # No start/end updates - preserve existing format
            if "dateTime" in current_start:
                event_data["start"] = {
                    "dateTime": current_start["dateTime"],
                    "timeZone": current_start.get("timeZone", timezone_name),
                }
            elif "date" in current_start:
                event_data["start"] = {"date": current_start["date"]}
            
            if "dateTime" in current_end:
                event_data["end"] = {
                    "dateTime": current_end["dateTime"],
                    "timeZone": current_end.get("timeZone", timezone_name),
                }
            elif "date" in current_end:
                event_data["end"] = {"date": current_end["date"]}

        # Description: update if provided, otherwise preserve existing
        if description is not None:
            event_data["description"] = description
        elif current_event.get("description"):
            event_data["description"] = current_event["description"]

        # Location: update if provided, otherwise preserve existing
        if location is not None:
            event_data["location"] = location
        elif current_event.get("location"):
            event_data["location"] = current_event["location"]

        if not event_data:
            raise GoogleCalendarUserError("No fields provided to update.")

        # Update the event via provider
        try:
            updated_event = await event_context.provider.update_event(
                calendar_id=calendar_id,
                event_id=event_id,
                event_data=event_data,
            )
        except GoogleCalendarAPIError as exc:
            if exc.status_code == 401:
                await self._handle_unauthorized(event_context)
                updated_event = await event_context.provider.update_event(
                    calendar_id=calendar_id,
                    event_id=event_id,
                    event_data=event_data,
                )
            elif exc.status_code == 403:
                # Preserve 403 errors so they can be handled properly in the endpoint
                # The endpoint has specific logic to return user-friendly messages for 403
                raise
            else:
                raise GoogleCalendarServiceError(
                    f"Failed to update event in Google Calendar: {str(exc)}"
                ) from exc

        # Convert Supabase calendar to Google format for _build_event_payload
        calendar_dict = {
            "id": supabase_calendar["google_calendar_id"],
            "summary": supabase_calendar.get("name") or supabase_calendar["google_calendar_id"],
            "backgroundColor": supabase_calendar.get("color"),
            "primary": supabase_calendar.get("is_primary", False),
            "accessRole": supabase_calendar.get("access_role"),
        }
        return _build_event_payload(
            updated_event,
            calendar_dict,
            event_context,
            supabase_calendar,
        )

    async def delete_event(
        self,
        *,
        user_id: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """Delete an event from Google Calendar."""
        contexts, calendars_by_id = await self._prepare_context(user_id)

        # Find the account context that has access to this calendar using Supabase data
        # Validate calendar ID format first
        self._validate_calendar_id(calendar_id)
        supabase_calendar = calendars_by_id.get(calendar_id)
        if not supabase_calendar:
            raise GoogleCalendarUserError(
                f"Calendar {calendar_id} not found in any linked Google account."
            )
        
        account_id = supabase_calendar["google_account_id"]
        event_context = next((ctx for ctx in contexts if ctx.id == account_id), None)
        if not event_context:
            raise GoogleCalendarUserError(
                f"Account for calendar {calendar_id} not found."
            )

        # Delete the event via provider
        try:
            await event_context.provider.delete_event(
                calendar_id=calendar_id,
                event_id=event_id,
            )
        except GoogleCalendarAPIError as exc:
            if exc.status_code == 401:
                await self._handle_unauthorized(event_context)
                await event_context.provider.delete_event(
                    calendar_id=calendar_id,
                    event_id=event_id,
                )
            elif exc.status_code == 403:
                # Preserve 403 errors so they can be handled properly in the endpoint
                # The endpoint has specific logic to return user-friendly messages for 403
                raise
            else:
                raise GoogleCalendarServiceError(
                    f"Failed to delete event in Google Calendar: {str(exc)}"
                ) from exc

    async def _prepare_context(
        self, user_id: str
    ) -> Tuple[List[AccountContext], Dict[str, Dict[str, Any]]]:
        """Prepare account contexts and calendars map."""
        method_start = time_module.time()
        log_start("backend.calendar_service._prepare_context", details=f"user_id={user_id}")
        
        repo_start = time_module.time()
        accounts = self.repository.get_accounts(user_id)
        if not accounts:
            raise GoogleCalendarUserError(
                "Link a Google account before requesting calendar data."
            )

        user_calendars = self.repository.get_calendars(user_id)
        repo_duration = time_module.time() - repo_start
        log_step("backend.calendar_service._prepare_context.repository", repo_duration, details=f"accounts={len(accounts)} calendars={len(user_calendars)}")
        
        calendars_by_id = {
            calendar["google_calendar_id"]: calendar for calendar in user_calendars
        }

        build_start = time_module.time()
        contexts = await self._build_account_contexts(accounts)
        build_duration = time_module.time() - build_start
        log_step("backend.calendar_service._prepare_context.build_contexts", build_duration, details=f"contexts={len(contexts)}")
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service._prepare_context", method_duration)
        return contexts, calendars_by_id

    async def _build_account_contexts(
        self, accounts: List[Dict[str, Any]]
    ) -> List[AccountContext]:
        """Build account contexts with providers."""
        contexts: List[AccountContext] = []
        for account in accounts:
            access_token = await self._ensure_access_token(account)
            provider = GoogleCalendarProvider(
                access_token=access_token,
                refresh_token=account.get("refresh_token", ""),
            )
            contexts.append(
                AccountContext(account=account, access_token=access_token, provider=provider)
            )
        return contexts

    async def _locate_event(
        self,
        contexts: List[AccountContext],
        *,
        calendar_id: str,
        event_id: str,
    ) -> Tuple[Dict[str, Any] | None, AccountContext | None]:
        """Locate an event across accounts."""
        for context in contexts:
            try:
                event_payload = await context.provider.get_event(
                    calendar_id=calendar_id,
                    event_id=event_id,
                )
                return event_payload, context
            except GoogleCalendarAPIError as exc:
                if exc.status_code in {403, 404}:
                    continue
                if exc.status_code == 401:
                    await self._handle_unauthorized(context)
                    try:
                        event_payload = await context.provider.get_event(
                            calendar_id=calendar_id,
                            event_id=event_id,
                        )
                        return event_payload, context
                    except GoogleCalendarAPIError as retry_exc:
                        if retry_exc.status_code in {403, 404}:
                            continue
                        raise GoogleCalendarServiceError(
                            "Failed to fetch event due to Google API error."
                        ) from retry_exc
                raise GoogleCalendarServiceError(
                    "Unexpected Google Calendar API error."
                ) from exc
        return None, None

    async def _events_for_window(
        self,
        contexts: List[AccountContext],
        calendars_by_id: Dict[str, Dict[str, Any]],
        timezone_name: str,
        window: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get events for a time window."""
        method_start = time_module.time()
        log_start("backend.calendar_service._events_for_window")
        
        # Convert Supabase calendars to Google format (no hydration needed)
        convert_start = time_module.time()
        self._convert_supabase_calendars_to_google_format(contexts, calendars_by_id)
        convert_duration = time_module.time() - convert_start
        log_step("backend.calendar_service._events_for_window.convert_calendars", convert_duration)
        
        collect_start = time_module.time()
        events = await self._collect_events_within_window(
            contexts,
            calendars_by_id,
            timezone_name,
            window["start_local"],
            window["end_local"],
            window["time_min_utc"],
            window["time_max_utc"],
        )
        collect_duration = time_module.time() - collect_start
        log_step("backend.calendar_service._events_for_window.collect_events", collect_duration, details=f"event_count={len(events)}")
        
        sort_start = time_module.time()
        events.sort(key=_event_sort_key)
        sort_duration = time_module.time() - sort_start
        log_step("backend.calendar_service._events_for_window.sort", sort_duration)
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service._events_for_window", method_duration, details=f"event_count={len(events)}")
        return events

    def _convert_supabase_calendars_to_google_format(
        self,
        contexts: List[AccountContext],
        calendars_by_id: Dict[str, Dict[str, Any]],
    ) -> None:
        """Convert Supabase calendars to Google API format and populate context.calendars.
        
        This replaces hydration for agent operations, using Supabase as the source of truth.
        Calendars are grouped by google_account_id and matched to AccountContext objects.
        
        Args:
            contexts: Account contexts to populate with calendars
            calendars_by_id: Map of google_calendar_id to Supabase calendar records
        """
        method_start = time_module.time()
        log_start("backend.calendar_service._convert_supabase_calendars_to_google_format", details=f"contexts={len(contexts)} calendars={len(calendars_by_id)}")
        
        # Group calendars by google_account_id for efficient lookup
        calendars_by_account: Dict[str, List[Dict[str, Any]]] = {}
        for calendar in calendars_by_id.values():
            account_id = calendar.get("google_account_id")
            if account_id:
                if account_id not in calendars_by_account:
                    calendars_by_account[account_id] = []
                calendars_by_account[account_id].append(calendar)
        
        # Populate context.calendars for each account
        for context in contexts:
            account_id = context.id
            if not account_id:
                continue
            
            account_calendars = calendars_by_account.get(account_id, [])
            google_format_calendars = []
            
            for supabase_calendar in account_calendars:
                # Convert Supabase format to Google API format
                google_calendar = {
                    "id": supabase_calendar["google_calendar_id"],
                    "summary": supabase_calendar.get("name") or supabase_calendar["google_calendar_id"],
                    "description": supabase_calendar.get("description"),
                    "backgroundColor": supabase_calendar.get("color"),
                    "foregroundColor": supabase_calendar.get("color"),  # Use same color for both
                    "primary": supabase_calendar.get("is_primary", False),
                    "accessRole": supabase_calendar.get("access_role"),
                }
                google_format_calendars.append(google_calendar)
            
            context.calendars = google_format_calendars
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service._convert_supabase_calendars_to_google_format", method_duration, details=f"contexts={len(contexts)} total_calendars={sum(len(ctx.calendars) for ctx in contexts)}")

    async def _hydrate_calendars(self, contexts: List[AccountContext]) -> None:
        """Hydrate calendars for each context in parallel.
        
        Fetches calendars from Google and syncs to Supabase for all accounts
        concurrently for maximum performance.
        
        NOTE: This is now only used by the refresh endpoint. Agent operations
        use _convert_supabase_calendars_to_google_format() instead.
        """
        method_start = time_module.time()
        log_start("backend.calendar_service._hydrate_calendars", details=f"contexts={len(contexts)}")
        
        async def hydrate_single_account(context: AccountContext, idx: int) -> None:
            """Hydrate calendars for a single account context."""
            try:
                list_start = time_module.time()
                calendars = await context.provider.list_calendars()
                list_duration = time_module.time() - list_start
                log_step(f"backend.calendar_service._hydrate_calendars.list_calendars.context_{idx}", list_duration, details=f"calendar_count={len(calendars)}")
                
                context.calendars = calendars
                
                # Sync calendars to Supabase after fetching from Google
                account_id = context.id
                if account_id:
                    try:
                        sync_start = time_module.time()
                        self.repository.sync_calendars(account_id, calendars)
                        sync_duration = time_module.time() - sync_start
                        log_step(f"backend.calendar_service._hydrate_calendars.sync_calendars.context_{idx}", sync_duration)
                        logger.debug(
                            "Synced %d calendars to Supabase for account_id=%s account=%s",
                            len(calendars),
                            account_id,
                            context.email or "unknown",
                        )
                    except SupabaseStorageError as sync_exc:
                        # Log error but don't fail the operation - calendars are already in memory
                        logger.warning(
                            "Failed to sync calendars to Supabase for account_id=%s account=%s: %s",
                            account_id,
                            context.email or "unknown",
                            sync_exc,
                        )
                else:
                    logger.warning(
                        "Cannot sync calendars: missing account_id for account=%s",
                        context.email or "unknown",
                    )
            except GoogleCalendarAPIError as exc:
                if exc.status_code in {401, 403}:
                    await self._handle_unauthorized(context)
                    try:
                        calendars = await context.provider.list_calendars()
                        context.calendars = calendars
                        
                        # Sync calendars to Supabase after retry fetch
                        account_id = context.id
                        if account_id:
                            try:
                                self.repository.sync_calendars(account_id, calendars)
                                logger.debug(
                                    "Synced %d calendars to Supabase for account_id=%s account=%s (after retry)",
                                    len(calendars),
                                    account_id,
                                    context.email or "unknown",
                                )
                            except SupabaseStorageError as sync_exc:
                                logger.warning(
                                    "Failed to sync calendars to Supabase for account_id=%s account=%s (after retry): %s",
                                    account_id,
                                    context.email or "unknown",
                                    sync_exc,
                                )
                    except GoogleCalendarAPIError as retry_exc:
                        if retry_exc.status_code in {401, 403}:
                            return  # Skip this account
                        raise GoogleCalendarServiceError(
                            "Failed to list calendars from Google."
                        ) from retry_exc
                else:
                    raise GoogleCalendarServiceError(
                        "Unexpected error retrieving calendars from Google."
                    ) from exc
        
        # Process all accounts in parallel
        await asyncio.gather(
            *[hydrate_single_account(context, idx) for idx, context in enumerate(contexts)],
            return_exceptions=True
        )
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service._hydrate_calendars", method_duration, details=f"contexts={len(contexts)}")

    async def hydrate_calendars(self, user_id: str) -> None:
        """Public method to refresh calendars from Google API and sync to Supabase.
        
        This is called by the refresh endpoint when the calendar accounts page is visited.
        Fetches calendars from Google for all linked accounts and syncs them to Supabase.
        
        Args:
            user_id: User ID to refresh calendars for
        """
        method_start = time_module.time()
        log_start("backend.calendar_service.hydrate_calendars", details=f"user_id={user_id}")
        
        # Build contexts for all accounts
        contexts, _ = await self._prepare_context(user_id)
        
        # Hydrate calendars (fetch from Google and sync to Supabase)
        await self._hydrate_calendars(contexts)
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service.hydrate_calendars", method_duration, details=f"user_id={user_id} contexts={len(contexts)}")

    async def _collect_events_within_window(
        self,
        contexts: List[AccountContext],
        calendars_by_id: Dict[str, Dict[str, Any]],
        timezone_name: str,
        window_start_local: datetime,
        window_end_local: datetime,
        time_min_utc: str,
        time_max_utc: str,
    ) -> List[Dict[str, Any]]:
        """Collect events within a time window.
        
        Queries all calendars in parallel for maximum performance. Each query uses
        a fresh provider instance to avoid thread-safety issues with googleapiclient
        (which uses C extensions that aren't thread-safe for concurrent access).
        
        Args:
            contexts: Account contexts with their calendars already hydrated
            calendars_by_id: Map of calendar IDs to Supabase calendar records
            timezone_name: Timezone for window filtering
            window_start_local: Start of time window in local timezone
            window_end_local: End of time window in local timezone
            time_min_utc: Start time in UTC ISO format for API queries
            time_max_utc: End time in UTC ISO format for API queries
            
        Returns:
            List of event payloads within the time window
        """
        method_start = time_module.time()
        log_start("backend.calendar_service._collect_events_within_window", details=f"contexts={len(contexts)}")
        
        # Collect all calendars to query across all accounts
        calendar_queries: List[Tuple[Dict[str, Any], AccountContext, str]] = []
        for context in contexts:
            for calendar in context.calendars:
                calendar_id = calendar.get("id")
                if not calendar_id:
                    continue
                calendar_queries.append((calendar, context, calendar_id))
        
        total_calendars = len(calendar_queries)
        log_start("backend.calendar_service._collect_events_within_window.parallel_queries", details=f"calendar_count={total_calendars} accounts={len(contexts)}")
        
        async def query_single_calendar(
            calendar: Dict[str, Any], 
            context: AccountContext, 
            calendar_id: str
        ) -> Tuple[str, List[Dict[str, Any]], AccountContext, Dict[str, Any]]:
            """Query a single calendar and return results.
            
            Creates a fresh provider instance for thread-safety. While this creates
            more provider instances than strictly necessary (one per calendar vs one
            per account), it's required because googleapiclient's service objects
            are not thread-safe when accessed concurrently via asyncio.to_thread().
            
            Returns:
                Tuple of (calendar_id, items, context, calendar_dict)
            """
            try:
                # Create fresh provider for thread-safety (googleapiclient is not thread-safe)
                # Note: We could reuse context.provider if queries were sequential, but
                # parallel execution requires separate instances to avoid memory corruption
                fresh_provider = GoogleCalendarProvider(
                    access_token=context.access_token,
                    refresh_token=context.account.get("refresh_token", ""),
                )
                result = await fresh_provider.list_events(
                    calendar_id=calendar_id,
                    time_min=time_min_utc,
                    time_max=time_max_utc,
                )
                items = result.get("items", []) if isinstance(result, dict) else result
                return (calendar_id, items, context, calendar)
            except GoogleCalendarAPIError as exc:
                if exc.status_code in {401, 403, 404}:
                    # Return empty items for calendars we can't access (permissions, not found, etc.)
                    return (calendar_id, [], context, calendar)
                raise GoogleCalendarServiceError(
                    f"Failed to list events from Google for calendar {calendar_id}."
                ) from exc
        
        # Execute all calendar queries in parallel
        parallel_start = time_module.time()
        results = await asyncio.gather(
            *[query_single_calendar(cal, ctx, cal_id) for cal, ctx, cal_id in calendar_queries],
            return_exceptions=True
        )
        parallel_duration = time_module.time() - parallel_start
        log_step("backend.calendar_service._collect_events_within_window.parallel_queries", parallel_duration, details=f"calendar_count={total_calendars}")
        
        # Process results and filter events within the time window
        events: List[Dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Failed to query calendar: %s", result)
                continue
            
            calendar_id, items, context, calendar = result
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Filter events to only those within the local time window
                if not _event_within_window(
                    item,
                    timezone_name,
                    window_start_local,
                    window_end_local,
                ):
                    continue
                supabase_calendar = calendars_by_id.get(calendar_id)
                event_payload = _build_event_payload(
                    item,
                    calendar,
                    context,
                    supabase_calendar,
                )
                events.append(event_payload)
        
        method_duration = time_module.time() - method_start
        log_step("backend.calendar_service._collect_events_within_window", method_duration, details=f"total_events={len(events)} calendars_queried={total_calendars}")
        return events

    async def _ensure_access_token(self, account: Dict[str, Any]) -> str:
        """Ensure access token is valid, refresh if needed."""
        access_token = account.get("access_token")
        expires_at = _parse_datetime(account.get("expires_at"))
        if (
            access_token
            and expires_at
            and expires_at > datetime.now(timezone.utc) + TOKEN_REFRESH_LEEWAY
        ):
            return access_token
        if access_token and expires_at is None:
            return access_token

        refresh_token = account.get("refresh_token")
        if not refresh_token:
            raise GoogleCalendarAuthError(
                f"Google account {account.get('email') or account.get('id')} has no refresh token."
            )

        tokens = await refresh_access_token(refresh_token)
        expires = tokens.expires_at()
        expires_at_str = expires.isoformat() if isinstance(expires, datetime) else expires
        updated_metadata = _merge_metadata(
            account.get("metadata"),
            {
                "last_token_refresh_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        updated = self.repository.update_account_tokens(
            account["user_id"],
            account["id"],
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or refresh_token,
            expires_at=expires_at_str,
            metadata=updated_metadata,
        )
        account.update(updated)
        return updated["access_token"]

    async def _handle_unauthorized(self, context: AccountContext) -> None:
        """Handle unauthorized error by refreshing token."""
        refreshed_token = await self._ensure_access_token(context.account)
        context.access_token = refreshed_token
        # Recreate provider with new token
        context.provider = GoogleCalendarProvider(
            access_token=refreshed_token,
            refresh_token=context.account.get("refresh_token", ""),
        )


# Helper functions
def _window_from_dates(
    start_date: date, end_date: date, timezone_name: str
) -> Dict[str, Any]:
    """Create window from dates."""
    if end_date < start_date:
        raise GoogleCalendarUserError("end_date must be on or after start_date.")
    tz = ZoneInfo(timezone_name)
    window_start_local = datetime.combine(start_date, time.min, tz)
    window_end_local = datetime.combine(end_date + timedelta(days=1), time.min, tz)
    return {
        "start_local": window_start_local,
        "end_local": window_end_local,
        "start_date": start_date,
        "end_date": end_date,
        "time_min_utc": window_start_local.astimezone(timezone.utc).isoformat(),
        "time_max_utc": window_end_local.astimezone(timezone.utc).isoformat(),
        "end_inclusive": window_end_local - timedelta(microseconds=1),
        "timezone": timezone_name,
    }


def _window_to_response(window: Dict[str, Any]) -> Dict[str, Any]:
    """Convert window to response format."""
    return {
        "start": window["start_local"].isoformat(),
        "end": window["end_inclusive"].isoformat(),
        "timezone": window["timezone"],
        "start_date": window["start_date"].isoformat(),
        "end_date": window["end_date"].isoformat(),
    }


def _localize_event_time(
    payload: Dict[str, Any],
    tz: ZoneInfo,
) -> Tuple[datetime, bool]:
    """Localize event time."""
    timezone_name = payload.get("timeZone")
    if timezone_name:
        tz = ZoneInfo(timezone_name)

    if "dateTime" in payload and payload["dateTime"]:
        dt = _parse_datetime(payload["dateTime"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz), False

    if "date" in payload and payload["date"]:
        date_value = _parse_date(payload["date"])
        localized = datetime.combine(date_value, time.min, tz)
        return localized, True

    raise GoogleCalendarServiceError("Event payload is missing start or end time.")


def _parse_datetime(value: Any) -> datetime:
    """Parse datetime value."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    raise GoogleCalendarServiceError("Invalid datetime payload from Google Calendar.")


def _parse_date(value: Any) -> date:
    """Parse date value."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise GoogleCalendarServiceError("Invalid date payload from Google Calendar.")


def _merge_metadata(
    original: Any,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge metadata dictionaries."""
    if isinstance(original, dict):
        merged = {**original}
    else:
        merged = {}
    merged.update(updates)
    return merged


def _event_within_window(
    payload: Dict[str, Any],
    timezone_name: str,
    window_start_local: datetime,
    window_end_local: datetime,
) -> bool:
    """Check if event is within window."""
    tz = ZoneInfo(timezone_name)
    try:
        start_dt, start_all_day = _localize_event_time(payload.get("start") or {}, tz)
        end_dt, end_all_day = _localize_event_time(payload.get("end") or {}, tz)
    except GoogleCalendarServiceError:
        return False

    if end_all_day:
        end_dt = end_dt - timedelta(microseconds=1)

    return start_dt < window_end_local and end_dt > window_start_local


def _build_event_payload(
    event: Dict[str, Any],
    calendar: Dict[str, Any],
    context: AccountContext,
    supabase_calendar: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """Build event payload with context."""
    calendar_id = calendar.get("id") or (supabase_calendar or {}).get(
        "google_calendar_id"
    )
    calendar_name = _resolve_calendar_name(calendar, supabase_calendar)
    calendar_color = _resolve_calendar_color(calendar, supabase_calendar)
    return {
        "id": event.get("id"),
        "summary": event.get("summary"),
        "description": event.get("description"),
        "status": event.get("status"),
        "start": event.get("start"),
        "end": event.get("end"),
        "html_link": event.get("htmlLink"),
        "hangout_link": event.get("hangoutLink"),
        "updated": event.get("updated"),
        "account_id": context.id,
        "account_email": context.email,
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "calendar_color": calendar_color,
        "is_primary": calendar.get("primary")
        or (supabase_calendar or {}).get("is_primary"),
        "raw": event,
    }


def _resolve_calendar_name(
    calendar_payload: Dict[str, Any],
    supabase_calendar: Dict[str, Any] | None,
) -> str | None:
    """Resolve calendar name."""
    if supabase_calendar and supabase_calendar.get("name"):
        return supabase_calendar["name"]
    return calendar_payload.get("summary")


def _resolve_calendar_color(
    calendar_payload: Dict[str, Any],
    supabase_calendar: Dict[str, Any] | None,
) -> str | None:
    """Resolve calendar color."""
    if supabase_calendar and supabase_calendar.get("color"):
        return supabase_calendar["color"]
    return calendar_payload.get("backgroundColor")


def _event_sort_key(payload: Dict[str, Any]) -> Tuple[int, str]:
    """Get sort key for event."""
    start = payload.get("start") or {}
    value = start.get("dateTime") or start.get("date") or ""
    return (0 if start.get("dateTime") else 1, value)
