"""Request logging middleware for tracking user interactions and building patterns."""

import json
import time
import logging
from typing import Callable
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests for pattern analysis."""

    def __init__(self, app: ASGIApp, exclude_paths: list[str] | None = None):
        """
        Initialize request logging middleware.

        Args:
            app: ASGI application
            exclude_paths: List of path prefixes to exclude from logging (e.g., ['/healthz'])
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/healthz", "/docs", "/openapi.json", "/redoc"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        start_time = time.time()
        user_id = None

        # Try to extract user ID from request (if authenticated)
        # User ID will be extracted from JWT in the endpoint handlers
        # For now, we'll get it from the request state if available
        if hasattr(request.state, "user_id"):
            user_id = str(request.state.user_id)

        # Read request body (if available)
        request_body = None
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    try:
                        request_body = json.loads(body.decode())
                    except json.JSONDecodeError:
                        request_body = {"raw": body.decode()[:500]}  # Truncate non-JSON
        except Exception as e:
            logger.debug(f"Could not read request body: {e}")

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Note: Response body is already sent, so we can't read it here
        # Response details will be logged in endpoint handlers if needed

        # Extract agent-specific fields from response (if agent endpoint)
        agent_action = None
        agent_tool = None
        agent_success = None
        agent_summary = None

        if request.url.path.startswith("/agent/"):
            # Try to extract from response headers or log in endpoint
            # For now, we'll log this in the endpoint handlers
            pass

        # Log to database (async, non-blocking)
        try:
            self._log_to_database(
                user_id=user_id,
                endpoint=request.url.path,
                method=request.method,
                request_body=request_body,
                request_headers=self._sanitize_headers(dict(request.headers)),
                response_status=response.status_code,
                response_time_ms=response_time_ms,
                agent_action=agent_action,
                agent_tool=agent_tool,
                agent_success=agent_success,
                agent_summary=agent_summary,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception as e:
            logger.error(f"Failed to log request to database: {e}", exc_info=True)

        return response

    def _sanitize_headers(self, headers: dict) -> dict:
        """Remove sensitive headers before logging."""
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
        }
        return {
            k: v if k.lower() not in sensitive_headers else "[REDACTED]"
            for k, v in headers.items()
        }

    def _log_to_database(
        self,
        user_id: str | None,
        endpoint: str,
        method: str,
        request_body: dict | None,
        request_headers: dict | None,
        response_status: int,
        response_time_ms: int,
        agent_action: str | None,
        agent_tool: str | None,
        agent_success: bool | None,
        agent_summary: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Log request to Supabase database."""
        if not user_id:
            # Skip logging if no user (unauthenticated requests)
            return

        try:
            supabase = get_supabase_client()
            supabase.table("request_logs").insert(
                {
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "method": method,
                    "request_body": request_body,
                    "request_headers": request_headers,
                    "response_status": response_status,
                    "response_time_ms": response_time_ms,
                    "agent_action": agent_action,
                    "agent_tool": agent_tool,
                    "agent_success": agent_success,
                    "agent_summary": agent_summary,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                }
            ).execute()
        except Exception as e:
            logger.error(f"Database logging failed: {e}", exc_info=True)

