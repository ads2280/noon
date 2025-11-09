from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from dependencies import AuthenticatedUser, get_current_user
from schemas import google_accounts as schema
from services import google_oauth, supabase_client

router = APIRouter(prefix="/google-accounts", tags=["google_accounts"])
logger = logging.getLogger("google_oauth")


@router.get("/", response_model=list[schema.GoogleAccountResponse])
async def list_google_accounts(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[schema.GoogleAccountResponse]:
    try:
        rows = supabase_client.list_google_accounts(current_user.id)
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return [schema.GoogleAccountResponse(**row) for row in rows]


@router.post("/oauth/start", response_model=schema.GoogleOAuthStartResponse)
async def start_google_oauth(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> schema.GoogleOAuthStartResponse:
    state = google_oauth.create_state_token(current_user.id)
    try:
        claims = google_oauth.decode_state_token(state)
    except google_oauth.GoogleStateError:
        # This should never happen because we issue the token, but guard regardless.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare OAuth state token.",
        )

    authorization_url = google_oauth.build_authorization_url(state)
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    return schema.GoogleOAuthStartResponse(
        authorization_url=authorization_url,
        state=state,
        state_expires_at=expires_at,
    )


@router.get("/oauth/callback", include_in_schema=False)
async def google_oauth_callback(state: str, code: str) -> RedirectResponse:
    try:
        claims = google_oauth.decode_state_token(state)
    except google_oauth.GoogleStateError as exc:
        logger.warning("Rejected Google OAuth callback with invalid state: %s", exc)
        redirect_url = google_oauth.build_app_redirect_url(
            False, state="", message="invalid_state"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    user_id = claims.get("sub")
    if not user_id:
        redirect_url = google_oauth.build_app_redirect_url(
            False, state, message="missing_user"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    try:
        tokens = await google_oauth.exchange_code_for_tokens(code)
        profile = await google_oauth.fetch_profile(tokens.access_token)
        calendars = await google_oauth.fetch_calendar_list(tokens.access_token)
    except google_oauth.GoogleOAuthError as exc:
        logger.error("Google OAuth flow failed for user %s: %s", user_id, exc)
        redirect_url = google_oauth.build_app_redirect_url(
            False, state, message="google_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception:  # pragma: no cover - unexpected runtime issues
        logger.exception(
            "Unexpected error during Google OAuth callback for user %s", user_id
        )
        redirect_url = google_oauth.build_app_redirect_url(
            False, state, message="unexpected_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    expires_at = tokens.expires_at()
    metadata: dict[str, object] = {
        "scopes": tokens.scopes,
        "calendars": calendars,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "token_type": tokens.token_type,
    }
    if tokens.id_token:
        metadata["id_token"] = tokens.id_token

    payload = {
        "google_user_id": profile.id,
        "email": profile.email,
        "display_name": profile.name,
        "avatar_url": profile.picture,
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "metadata": metadata,
    }

    try:
        supabase_client.upsert_google_account(user_id, payload)
        supabase_client.sync_google_calendars(user_id, calendars)
    except supabase_client.SupabaseStorageError as exc:
        logger.error("Failed to persist Google account for user %s: %s", user_id, exc)
        redirect_url = google_oauth.build_app_redirect_url(
            False, state, message="storage_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    redirect_url = google_oauth.build_app_redirect_url(True, state, message="linked")
    return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/",
    response_model=schema.GoogleAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_google_account(
    payload: schema.GoogleAccountCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> schema.GoogleAccountResponse:
    try:
        row = supabase_client.upsert_google_account(
            current_user.id, payload.model_dump(exclude_none=True)
        )
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return schema.GoogleAccountResponse(**row)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_google_account(
    account_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        supabase_client.delete_google_account(current_user.id, account_id)
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
