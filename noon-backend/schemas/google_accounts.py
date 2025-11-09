from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GoogleAccountBase(BaseModel):
    google_user_id: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, object]] = None


class GoogleAccountCreate(GoogleAccountBase):
    pass


class GoogleAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[dict[str, object]] = None


class GoogleAccountResponse(GoogleAccountBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
