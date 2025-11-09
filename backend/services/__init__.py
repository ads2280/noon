"""Services module exports."""

from auth.utils import supabase_client
from google_calendar.utils import google_oauth as _google_oauth
from services import agent_calendar_service

# Re-export google_oauth as a submodule
google_oauth = _google_oauth

__all__ = ["supabase_client", "google_oauth", "agent_calendar_service"]
