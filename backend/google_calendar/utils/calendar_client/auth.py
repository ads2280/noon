"""Google Calendar authentication and service creation."""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarService:
    """Manages Google Calendar API authentication and service creation."""

    def __init__(
        self, credentials_path: str = "credentials.json", token_path: str = "token.json"
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = None

    def get_credentials(self) -> Credentials:
        """Get valid user credentials from storage or create new ones."""
        creds = None

        # Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return creds

    def get_service(self):
        """Get or create Calendar API service."""
        if self._service is None:
            creds = self.get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service


def get_calendar_service(access_token: str):
    """
    Create Google Calendar service from access token.

    Args:
        access_token: OAuth 2.0 access token

    Returns:
        Google Calendar API service object
    """
    credentials = Credentials(token=access_token)
    service = build("calendar", "v3", credentials=credentials)
    return service


def get_calendar_service_from_file(
    credentials_path: str = "credentials.json", token_path: str = "token.json"
):
    """
    Create Google Calendar service using local credentials file.

    This is useful for development/testing. In production, use get_calendar_service
    with an access token.

    Args:
        credentials_path: Path to credentials.json file
        token_path: Path to token.json file

    Returns:
        Google Calendar API service object
    """
    cal_service = CalendarService(credentials_path, token_path)
    return cal_service.get_service()
