"""Database operations for loading UserContext and managing calendar data."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from .calendar_state import Friend as FriendSchema
from .calendar_state import UserContext
from .database import get_supabase_client
from .gcal_auth import get_calendar_service
from .models import Calendar, Friend, User
from .tools.gcal_api import list_events_api


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


def load_user_friends(user_id: str) -> List[Friend]:
    """
    Load all friends for a user.

    Args:
        user_id: User UUID as string

    Returns:
        List of Friend models
    """
    db = get_supabase_client()

    result = db.table("friends").select("*").eq("user_id", user_id).execute()

    return [Friend(**friend) for friend in result.data]


def load_user_context_from_db(user_id: str) -> UserContext:
    """
    Load complete UserContext from database for LangGraph agent.

    This function:
    1. Loads user from database (includes OAuth tokens, timezone)
    2. Loads all user's calendars
    3. Loads user's friends
    4. Fetches upcoming events from Google Calendar
    5. Constructs UserContext for the agent

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

    if not user.google_access_token:
        raise ValueError(f"User {user_id} has no Google access token")

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

    # Load friends
    friends_db = load_user_friends(user_id)
    friends_list: List[FriendSchema] = []
    for friend in friends_db:
        friends_list.append(
            {
                "name": friend.name,
                "email": friend.email,
                "calendar_id": friend.google_calendar_id or friend.email,
            }
        )

    # Fetch upcoming events from Google Calendar
    upcoming_events = []
    try:
        service = get_calendar_service(user.google_access_token)

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
        "friends": friends_list,
        "upcoming_events": upcoming_events,
        "access_token": user.google_access_token,
    }

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

    update_data: Dict[str, any] = {
        "google_access_token": access_token,
        "updated_at": datetime.utcnow().isoformat(),
    }

    if refresh_token:
        update_data["google_refresh_token"] = refresh_token

    if expiry:
        update_data["google_token_expiry"] = expiry.isoformat()

    db.table("users").update(update_data).eq("id", user_id).execute()


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
