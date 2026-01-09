"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import router as v1_router
from api.v1.calendars import oauth_callback
from fastapi import Query

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting Noon backend API...")
    yield
    logger.info("Shutting down Noon backend API...")


# Create FastAPI application
app = FastAPI(
    title="Noon Backend API",
    description="Backend API for Noon - handles authentication, Google Calendar integration, and agent services",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(v1_router, prefix="/api/v1")


# TEMPORARY: Legacy OAuth callback route for backwards compatibility
# TODO: Remove this route after updating Google OAuth Console redirect URI
# The correct route is: /api/v1/calendars/accounts/oauth/callback
# This route exists only to support the old redirect URI: /google-accounts/oauth/callback
# See instructions in README or docs for updating GCP OAuth configuration
@app.get("/google-accounts/oauth/callback", include_in_schema=False)
async def legacy_oauth_callback(
    state: str = Query(...), code: str = Query(...)
):
    """
    TEMPORARY legacy OAuth callback route.
    
    This route forwards to the actual callback handler at /api/v1/calendars/accounts/oauth/callback.
    This is a temporary compatibility layer - update your Google OAuth Console redirect URI
    to use the correct route and remove this handler.
    """
    return await oauth_callback(state=state, code=code)


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Noon Backend API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
