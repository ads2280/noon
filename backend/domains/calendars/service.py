"""Service for calendar business logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from domains.calendars.providers.base import CalendarProvider
from domains.calendars.providers.google import (
    GoogleCalendarProvider,
    GoogleCalendarHttpClient,
    refresh_access_token,
)
from domains.calendars.repository import CalendarRepository
from utils.errors import (
    GoogleCalendarServiceError,
    GoogleCalendarUserError,
    GoogleCalendarAuthError,
    GoogleCalendarEventNotFoundError,
    GoogleCalendarAPIError,
    SupabaseStorageError,
)


TOKEN_REFRESH_LEEWAY = timedelta(minutes=5)


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

    async def events_for_event_window(
        self,
        *,
        user_id: str,
        event_id: str,
        calendar_id: str,
        timezone_name: str,
    ) -> Dict[str, Any]:
        """Get event and surrounding schedule."""
        contexts, calendars_by_id = await self._prepare_context(user_id)

        event_payload, event_context = await self._locate_event(
            contexts,
            calendar_id=calendar_id,
            event_id=event_id,
        )
        if event_payload is None or event_context is None:
            raise GoogleCalendarEventNotFoundError(
                "Event not found in any linked Google calendar."
            )

        window = _calculate_window(event_payload, timezone_name)

        events = await self._events_for_window(
            contexts,
            calendars_by_id,
            timezone_name,
            window,
        )

        primary_calendar = calendars_by_id.get(calendar_id)
        event_wrapper = {
            "data": event_payload,
            "calendar_id": calendar_id,
            "calendar_name": _resolve_calendar_name(event_payload, primary_calendar),
            "account_id": event_context.id,
            "account_email": event_context.email,
        }

        response = {
            "event": event_wrapper,
            "schedule": {
                "window": _window_to_response(window),
                "events": events,
            },
        }
        return response

    async def events_for_date_range(
        self,
        *,
        user_id: str,
        start_date: date,
        end_date: date,
        timezone_name: str,
    ) -> Dict[str, Any]:
        """Get events for a date range."""
        contexts, calendars_by_id = await self._prepare_context(user_id)
        window = _window_from_dates(start_date, end_date, timezone_name)

        events = await self._events_for_window(
            contexts,
            calendars_by_id,
            timezone_name,
            window,
        )

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
        contexts, _ = await self._prepare_context(user_id)

        event_payload, event_context = await self._locate_event(
            contexts,
            calendar_id=calendar_id,
            event_id=event_id,
        )
        if event_payload is None or event_context is None:
            raise GoogleCalendarEventNotFoundError(
                "Event not found in any linked Google calendar."
            )

        return event_payload

    async def _prepare_context(
        self, user_id: str
    ) -> Tuple[List[AccountContext], Dict[str, Dict[str, Any]]]:
        """Prepare account contexts and calendars map."""
        accounts = self.repository.get_accounts(user_id)
        if not accounts:
            raise GoogleCalendarUserError(
                "Link a Google account before requesting calendar data."
            )

        user_calendars = self.repository.get_calendars(user_id)
        calendars_by_id = {
            calendar["google_calendar_id"]: calendar for calendar in user_calendars
        }

        contexts = await self._build_account_contexts(accounts)
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
        await self._hydrate_calendars(contexts)
        events = await self._collect_events_within_window(
            contexts,
            calendars_by_id,
            timezone_name,
            window["start_local"],
            window["end_local"],
            window["time_min_utc"],
            window["time_max_utc"],
        )
        events.sort(key=_event_sort_key)
        return events

    async def _hydrate_calendars(self, contexts: List[AccountContext]) -> None:
        """Hydrate calendars for each context."""
        for context in contexts:
            try:
                calendars = await context.provider.list_calendars()
                context.calendars = calendars
            except GoogleCalendarAPIError as exc:
                if exc.status_code in {401, 403}:
                    await self._handle_unauthorized(context)
                    try:
                        calendars = await context.provider.list_calendars()
                        context.calendars = calendars
                    except GoogleCalendarAPIError as retry_exc:
                        if retry_exc.status_code in {401, 403}:
                            continue
                        raise GoogleCalendarServiceError(
                            "Failed to list calendars from Google."
                        ) from retry_exc
                else:
                    raise GoogleCalendarServiceError(
                        "Unexpected error retrieving calendars from Google."
                    ) from exc

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
        """Collect events within a time window."""
        events: List[Dict[str, Any]] = []
        for context in contexts:
            for calendar in context.calendars:
                calendar_id = calendar.get("id")
                if not calendar_id:
                    continue
                try:
                    result = await context.provider.list_events(
                        calendar_id=calendar_id,
                        time_min=time_min_utc,
                        time_max=time_max_utc,
                    )
                    items = result.get("items", []) if isinstance(result, dict) else result
                except GoogleCalendarAPIError as exc:
                    if exc.status_code in {401, 403, 404}:
                        continue
                    raise GoogleCalendarServiceError(
                        "Failed to list events from Google."
                    ) from exc

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if not _event_within_window(
                        item,
                        timezone_name,
                        window_start_local,
                        window_end_local,
                    ):
                        continue
                    supabase_calendar = calendars_by_id.get(calendar_id)
                    events.append(
                        _build_event_payload(
                            item,
                            calendar,
                            context,
                            supabase_calendar,
                        )
                    )
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
def _calculate_window(
    event_payload: Dict[str, Any], timezone_name: str
) -> Dict[str, Any]:
    """Calculate window from event."""
    tz = ZoneInfo(timezone_name)
    start_info = event_payload.get("start") or {}
    end_info = event_payload.get("end") or {}
    start_dt, start_all_day = _localize_event_time(start_info, tz)
    end_dt, end_all_day = _localize_event_time(end_info, tz)

    if end_all_day:
        end_dt = end_dt - timedelta(microseconds=1)

    start_date = start_dt.date()
    end_date = end_dt.date()

    window_start_local = datetime.combine(start_date, time.min, tz)
    window_end_local = datetime.combine(end_date + timedelta(days=1), time.min, tz)
    time_min_utc = window_start_local.astimezone(timezone.utc).isoformat()
    time_max_utc = window_end_local.astimezone(timezone.utc).isoformat()

    return {
        "start_local": window_start_local,
        "end_local": window_end_local,
        "start_date": start_date,
        "end_date": end_date,
        "time_min_utc": time_min_utc,
        "time_max_utc": time_max_utc,
        "end_inclusive": window_end_local - timedelta(microseconds=1),
        "timezone": timezone_name,
    }


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
