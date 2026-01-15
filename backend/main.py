"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import router as v1_router
from core.logging import setup_logging, get_logger
from core.middleware import RequestLoggingMiddleware

# Configure centralized logging
setup_logging()
logger = get_logger(__name__)


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

# Add request logging middleware (must be after CORS to log authenticated requests)
app.add_middleware(RequestLoggingMiddleware)

# Include API router
app.include_router(v1_router, prefix="/api/v1")


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
