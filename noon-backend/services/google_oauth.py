from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlencode

import httpx
import jwt

from config import get_settings

STATE_AUDIENCE = "google-oauth-state"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
CALENDAR_LIST_ENDPOINT = "https://www.googleapis.com/calendar/v3/users/me/calendarList"


class GoogleOAuthError(RuntimeError):
    """Raised when Google OAuth flow fails."""


class GoogleStateError(RuntimeError):
    """Raised when the OAuth state token is invalid."""


@dataclass(frozen=True)
class GoogleTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scope: str
    token_type: str
    id_token: str | None

    def expires_at(self, issued_at: datetime | None = None) -> datetime | None:
        if self.expires_in is None:
            return None
        base = issued_at or datetime.now(timezone.utc)
        return base + timedelta(seconds=self.expires_in)

    @property
    def scopes(self) -> List[str]:
        if not self.scope:
            return []
        return [segment for segment in self.scope.split() if segment]


@dataclass(frozen=True)
class GoogleProfile:
    id: str
    email: str
    name: str | None
    picture: str | None


def _state_secret() -> str:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET must be configured to sign Google OAuth state tokens."
        )
    return settings.supabase_jwt_secret


def create_state_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": STATE_AUDIENCE,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def decode_state_token(state: str) -> Dict[str, Any]:
    try:
        decoded = jwt.decode(
            state,
            _state_secret(),
            algorithms=["HS256"],
            audience=STATE_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise GoogleStateError("Invalid or expired OAuth state token") from exc
    return decoded


def build_authorization_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.google_oauth_scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_code_for_tokens(code: str) -> GoogleTokens:
    settings = get_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_oauth_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TOKEN_ENDPOINT, data=payload, headers={"Accept": "application/json"}
        )
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Token exchange failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleOAuthError(
            "Token exchange response did not include an access token."
        )

    return GoogleTokens(
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope", ""),
        token_type=data.get("token_type", ""),
        id_token=data.get("id_token"),
    )


async def refresh_access_token(refresh_token: str) -> GoogleTokens:
    settings = get_settings()
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TOKEN_ENDPOINT, data=payload, headers={"Accept": "application/json"}
        )
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Token refresh failed with status {response.status_code}: {response.text}"
        )
    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise GoogleOAuthError("Token refresh response did not include an access token.")

    return GoogleTokens(
        access_token=access_token,
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        scope=data.get("scope", ""),
        token_type=data.get("token_type", ""),
        id_token=data.get("id_token"),
    )


async def fetch_profile(access_token: str) -> GoogleProfile:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(USERINFO_ENDPOINT, headers=headers)
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Failed to load Google profile: {response.status_code} {response.text}"
        )
    data = response.json()
    profile_id = data.get("id") or data.get("sub")
    email = data.get("email")
    if not profile_id or not email:
        raise GoogleOAuthError("Google did not return a profile ID or email address.")

    return GoogleProfile(
        id=profile_id,
        email=email,
        name=data.get("name"),
        picture=data.get("picture"),
    )


async def fetch_calendar_list(access_token: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {"minAccessRole": "reader"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            CALENDAR_LIST_ENDPOINT, headers=headers, params=params
        )
    if response.status_code != httpx.codes.OK:
        raise GoogleOAuthError(
            f"Failed to load Google calendars: {response.status_code} {response.text}"
        )
    data = response.json()
    items = data.get("items") or []
    sanitized: List[Dict[str, Any]] = []
    for item in items:
        sanitized.append(
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "access_role": item.get("accessRole"),
                "background_color": item.get("backgroundColor"),
                "foreground_color": item.get("foregroundColor"),
            }
        )
    return sanitized


def build_app_redirect_url(
    success: bool, state: str, message: str | None = None
) -> str:
    settings = get_settings()
    base = settings.google_oauth_app_redirect_uri
    params = {
        "result": "success" if success else "error",
        "state": state,
    }
    if message:
        params["message"] = message
    query = urlencode(params)
    if "?" in base:
        return f"{base}&{query}"
    return f"{base}?{query}"
