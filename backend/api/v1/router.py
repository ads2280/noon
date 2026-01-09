"""API router aggregating all v1 routes."""

from __future__ import annotations

from fastapi import APIRouter

from .auth import router as auth_router
from .calendars import router as calendars_router
from .agent import router as agent_router

router = APIRouter()

router.include_router(auth_router, tags=["auth"])
router.include_router(calendars_router, tags=["calendars"])
router.include_router(agent_router, tags=["agent"])
