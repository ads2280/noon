"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.routes import auth as auth_routes
from google_calendar.routes import google_accounts, google_calendar
from middleware.request_logging import RequestLoggingMiddleware

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

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
# Auth routes (no authentication required)
app.include_router(auth_routes.router)

# Google Calendar routes (authentication required via Depends(get_current_user))
app.include_router(google_accounts.router)
app.include_router(google_calendar.router)


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
