"""Pytest fixtures for backend tests."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from main import app


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_authenticated_user():
    """Mock authenticated user data."""
    return {
        "id": "test-user-123",
        "phone": "+1234567890",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def auth_headers():
    """Mock valid authentication headers."""
    return {"Authorization": "Bearer test-token-123"}


@pytest.fixture
def mock_google_account():
    """Mock Google account with tokens."""
    return {
        "id": "google-account-123",
        "email": "test@example.com",
        "tokens": {
            "access_token": "ya29.test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_at": "2024-12-31T23:59:59Z",
            "token_type": "Bearer",
        }
    }


@pytest.fixture
def mock_get_current_user(mock_authenticated_user):
    """Mock the get_current_user dependency."""
    with patch("agent.routes.agent.get_current_user") as mock:
        mock.return_value = type("AuthenticatedUser", (), mock_authenticated_user)
        yield mock


@pytest.fixture
def mock_get_google_account(mock_google_account):
    """Mock get_google_account function."""
    with patch("agent.routes.agent.get_google_account") as mock:
        mock.return_value = mock_google_account
        yield mock


@pytest.fixture
def mock_langgraph_client():
    """Mock LangGraph SDK client."""
    with patch("agent.routes.agent.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_runs = MagicMock()

        # Mock wait method to return agent response
        async def mock_wait(*args, **kwargs):
            return {
                "success": True,
                "request": "show-schedule",
                "metadata": {
                    "start-date": "2024-11-16",
                    "end-date": "2024-11-17"
                }
            }

        mock_runs.wait = AsyncMock(side_effect=mock_wait)
        mock_client.runs = mock_runs
        mock_get_client.return_value = mock_client

        yield mock_client
