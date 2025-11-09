"""Database operations for loading UserContext and managing calendar data."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings as get_backend_settings
from .calendar_state import UserContext
from .database import get_supabase_client
from .gcal_auth import get_calendar_service
from .models import Calendar, GoogleAccount, User
from .tools.gcal_api import list_events_api

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
TOKEN_REFRESH_MARGIN = timedelta(minutes=2)


def load_user_from_db(user_id: str) -> Optional[User]:
    """
    Load user from database by ID.

    Args:
        user_id: User UUID as string

    Returns:
        User model or None if not found
    """
    db = get_supabase_client()

    result = db.table("users").select("*").eq("id", user_id).execute()

    if not result.data:
        return None

    return User(**result.data[0])


def load_user_calendars(user_id: str) -> List[Calendar]:
    """
    Load all calendars for a user.

    Args:
        user_id: User UUID as string

    Returns:
        List of Calendar models
    """
    db = get_supabase_client()

    result = db.table("calendars").select("*").eq("user_id", user_id).execute()

    return [Calendar(**cal) for cal in result.data]


def load_first_google_account(user_id: str) -> Optional[GoogleAccount]:
    """
    Load the first Google account associated with the user.

    Args:
        user_id: User UUID as string

    Returns:
        GoogleAccount model or None if not found
    """
    db = get_supabase_client()

    query = (
        db.table("google_accounts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        .limit(1)
    )

    result = query.execute()
    if not result.data:
        return None

    try:
        return GoogleAccount(**result.data[0])
    except TypeError:
        # Backwards compatibility with missing fields
        return GoogleAccount.model_validate(result.data[0])


def _refresh_google_access_token(
    user_id: str, account: GoogleAccount
) -> GoogleAccount:
    if not account.refresh_token:
        raise ValueError(
            f"User {user_id} has no refresh token to renew Google access token"
        )

    settings = get_backend_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": account.refresh_token,
        "grant_type": "refresh_token",
    }

    response = httpx.post(
        TOKEN_ENDPOINT, data=payload, headers={"Accept": "application/json"}, timeout=15.0
    )
    if response.status_code != httpx.codes.OK:
        raise ValueError(
            f"Failed to refresh Google access token for user {user_id}: "
            f"{response.status_code} {response.text}"
        )

    data = response.json()
    new_access_token = data.get("access_token")
    if not new_access_token:
        raise ValueError(
            f"Google refresh response did not include access token for user {user_id}"
        )

    expires_in = data.get("expires_in")
    new_expires_at = None
    if isinstance(expires_in, (int, float)):
        new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    update_data: Dict[str, Any] = {"access_token": new_access_token}
    if new_expires_at:
        update_data["expires_at"] = new_expires_at.isoformat()

    db = get_supabase_client()
    db.table("google_accounts").update(update_data).eq("id", str(account.id)).execute()

    return account.model_copy(
        update={
            "access_token": new_access_token,
            "expires_at": new_expires_at or account.expires_at,
        }
    )


def _ensure_valid_google_account(
    user_id: str, account: GoogleAccount
) -> GoogleAccount:
    """
    Ensure the Google account has a usable access token, refreshing if needed.
    """

    if not account.access_token:
        if account.refresh_token:
            return _refresh_google_access_token(user_id, account)
        raise ValueError(f"User {user_id} has no Google access token")

    if account.expires_at:
        if isinstance(account.expires_at, str):
            expires_at = datetime.fromisoformat(account.expires_at)
        else:
            expires_at = account.expires_at

        if expires_at <= datetime.now(timezone.utc) + TOKEN_REFRESH_MARGIN:
            if account.refresh_token:
                return _refresh_google_access_token(user_id, account)
            raise ValueError(
                f"Google access token expired for user {user_id} and no refresh token available"
            )

    return account


def load_user_context_from_db(user_id: str) -> UserContext:
    """
    Load complete UserContext from database for LangGraph agent.

    This function:
    1. Loads user from database (includes OAuth tokens, timezone)
    2. Loads all user's calendars
    3. Fetches upcoming events from Google Calendar
    4. Constructs UserContext for the agent

    Args:
        user_id: User UUID as string

    Returns:
        UserContext dict ready for the calendar agent

    Raises:
        ValueError: If user not found or missing access token
    """
    # Load user
    user = load_user_from_db(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    account = load_first_google_account(user_id)
    if not account:
        raise ValueError(f"User {user_id} has no linked Google account")

    account = _ensure_valid_google_account(user_id, account)
    print(
        f"[AgentDB] Using Google account {account.id} for user {user_id}; "
        f"token present={bool(account.access_token)} expires_at={account.expires_at}"
    )

    # Load calendars
    calendars = load_user_calendars(user_id)
    all_calendar_ids = [cal.google_calendar_id for cal in calendars]

    # Determine primary calendar
    primary_calendar_id = user.primary_calendar_id
    if not primary_calendar_id:
        # Try to find a calendar marked as primary
        primary_cals = [cal for cal in calendars if cal.is_primary]
        if primary_cals:
            primary_calendar_id = primary_cals[0].google_calendar_id
        elif calendars:
            # Fall back to first calendar
            primary_calendar_id = calendars[0].google_calendar_id
        else:
            # Default to 'primary'
            primary_calendar_id = "primary"

    # Fetch upcoming events from Google Calendar
    upcoming_events = []
    try:
        service = get_calendar_service(account.access_token)

        time_min = datetime.utcnow().isoformat() + "Z"
        time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

        # Fetch from primary calendar only (to keep it fast)
        events_result = list_events_api(
            service=service,
            calendar_id=primary_calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=20,
        )

        for event in events_result.get("events", []):
            upcoming_events.append(
                {
                    "event_id": event["event_id"],
                    "calendar_id": event.get(
                        "calendar_id", primary_calendar_id
                    ),  # Include calendar_id with event_id
                    "summary": event["summary"],
                    "start": event["start"],
                    "end": event["end"],
                    "attendees": event.get("attendees", []),
                }
            )

    except Exception as e:
        # If we can't fetch events, continue with empty list
        print(f"Warning: Could not fetch upcoming events for user {user_id}: {e}")

    # Construct UserContext
    user_context: UserContext = {
        "user_id": user_id,
        "timezone": user.timezone,
        "primary_calendar_id": primary_calendar_id,
        "all_calendar_ids": all_calendar_ids,
        "upcoming_events": upcoming_events,
        "access_token": account.access_token,
    }

    user_context["google_account"] = {
        "id": str(account.id),
        "email": account.email,
        "display_name": account.display_name,
        "google_user_id": account.google_user_id,
    }
    if account.refresh_token:
        user_context["google_account"]["refresh_token"] = account.refresh_token
    if account.expires_at:
        user_context["google_account"]["expires_at"] = account.expires_at.isoformat()

    return user_context


def update_user_tokens(
    user_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expiry: Optional[datetime] = None,
) -> None:
    """
    Update user's Google OAuth tokens in database.

    Args:
        user_id: User UUID as string
        access_token: New access token
        refresh_token: New refresh token (optional)
        expiry: Token expiry datetime (optional)
    """
    db = get_supabase_client()

    account = load_first_google_account(user_id)
    if not account:
        raise ValueError(f"User {user_id} has no linked Google account to update")

    update_data: Dict[str, Any] = {
        "access_token": access_token,
        "updated_at": datetime.utcnow().isoformat(),
    }

    if refresh_token:
        update_data["refresh_token"] = refresh_token

    if expiry:
        update_data["expires_at"] = expiry.isoformat()

    db.table("google_accounts").update(update_data).eq("id", str(account.id)).execute()


def get_or_create_user_by_email(email: str, full_name: Optional[str] = None) -> User:
    """
    Get existing user by email or create a new one.

    Args:
        email: User's email address
        full_name: User's full name (for new users)

    Returns:
        User model
    """
    db = get_supabase_client()

    # Try to find existing user
    result = db.table("users").select("*").eq("email", email).execute()

    if result.data:
        return User(**result.data[0])

    # Create new user
    new_user_data = {
        "email": email,
        "full_name": full_name,
        "timezone": "UTC",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = db.table("users").insert(new_user_data).execute()

    return User(**result.data[0])


def sync_user_calendars_from_google(user_id: str, access_token: str) -> List[Calendar]:
    """
    Sync user's calendars from Google Calendar to database.

    This fetches all calendars from Google and creates/updates them in the database.

    Args:
        user_id: User UUID as string
        access_token: Google OAuth access token

    Returns:
        List of synced Calendar models
    """
    db = get_supabase_client()
    service = get_calendar_service(access_token)

    # Fetch calendars from Google
    calendar_list = service.calendarList().list().execute()
    google_calendars = calendar_list.get("items", [])

    synced_calendars = []

    for gcal in google_calendars:
        calendar_id = gcal["id"]
        name = gcal.get("summary", "Untitled Calendar")
        description = gcal.get("description")
        color = gcal.get("backgroundColor")
        is_primary = gcal.get("primary", False)

        # Check if calendar already exists in DB
        existing = (
            db.table("calendars")
            .select("*")
            .eq("user_id", user_id)
            .eq("google_calendar_id", calendar_id)
            .execute()
        )

        if existing.data:
            # Update existing calendar
            update_data = {
                "name": name,
                "description": description,
                "color": color,
                "is_primary": is_primary,
                "updated_at": datetime.utcnow().isoformat(),
            }
            result = (
                db.table("calendars").update(update_data).eq("id", existing.data[0]["id"]).execute()
            )
            synced_calendars.append(Calendar(**result.data[0]))
        else:
            # Create new calendar
            new_cal_data = {
                "user_id": user_id,
                "google_calendar_id": calendar_id,
                "name": name,
                "description": description,
                "color": color,
                "is_primary": is_primary,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            result = db.table("calendars").insert(new_cal_data).execute()
            synced_calendars.append(Calendar(**result.data[0]))

    return synced_calendars
