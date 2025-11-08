from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..dependencies import AuthenticatedUser, get_current_user
from ..schemas import google_accounts as schema
from ..services import supabase_client

router = APIRouter(prefix="/google-accounts", tags=["google_accounts"])


@router.get("/", response_model=list[schema.GoogleAccountResponse])
async def list_google_accounts(current_user: AuthenticatedUser = Depends(get_current_user)) -> list[schema.GoogleAccountResponse]:
    try:
        rows = supabase_client.list_google_accounts(current_user.id)
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return [schema.GoogleAccountResponse(**row) for row in rows]


@router.post("/", response_model=schema.GoogleAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_google_account(
    payload: schema.GoogleAccountCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> schema.GoogleAccountResponse:
    try:
        row = supabase_client.upsert_google_account(current_user.id, payload.model_dump(exclude_none=True))
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return schema.GoogleAccountResponse(**row)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_google_account(
    account_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    try:
        supabase_client.delete_google_account(current_user.id, account_id)
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)

