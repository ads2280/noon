"""Services module exports."""

from auth.utils import supabase_client
from google_calendar.utils import google_oauth as _google_oauth

# Re-export google_oauth as a submodule
google_oauth = _google_oauth

__all__ = ["supabase_client", "google_oauth"]

