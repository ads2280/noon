"""Tests for the agent endpoint."""

import pytest
from io import BytesIO
from unittest.mock import patch, AsyncMock


class TestAgentAction:
    """Tests for POST /agent/action endpoint."""

    def test_agent_action_success(
        self,
        test_client,
        auth_headers,
        mock_get_current_user,
        mock_list_google_accounts,
        mock_transcription_service,
        mock_langgraph_client,
    ):
        """Test successful agent invocation with audio file."""
        # Arrange
        audio_file = ("test.wav", BytesIO(b"fake audio data"), "audio/wav")

        # Act
        response = test_client.post(
            "/agent/action", files={"file": audio_file}, headers=auth_headers
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["request"] == "show-schedule"
        assert "metadata" in data
        assert "start-date" in data["metadata"]
        assert "end-date" in data["metadata"]

        # Verify transcription was called
        mock_transcription_service.assert_called_once()

        # Verify LangGraph client was called
        mock_langgraph_client.runs.wait.assert_called_once()
        call_kwargs = mock_langgraph_client.runs.wait.call_args.kwargs
        assert call_kwargs["assistant_id"] == "agent"
        assert "query" in call_kwargs["input"]
        assert "auth" in call_kwargs["input"]

    def test_agent_action_no_google_account(
        self,
        test_client,
        auth_headers,
        mock_get_current_user,
    ):
        """Test agent invocation when user has no Google account linked."""
        # Arrange
        audio_file = ("test.wav", BytesIO(b"fake audio data"), "audio/wav")

        with patch(
            "agent.routes.agent.supabase_client.list_google_accounts"
        ) as mock_list:
            mock_list.return_value = []

            # Act
            response = test_client.post(
                "/agent/action", files={"file": audio_file}, headers=auth_headers
            )

        # Assert
        assert response.status_code == 400
        assert "No Google account linked" in response.json()["detail"]

    def test_agent_action_transcription_failure(
        self,
        test_client,
        auth_headers,
        mock_get_current_user,
        mock_list_google_accounts,
    ):
        """Test agent invocation when transcription fails."""
        # Arrange
        audio_file = ("test.wav", BytesIO(b"fake audio data"), "audio/wav")

        with patch(
            "agent.routes.agent.transcription_service.transcribe"
        ) as mock_transcribe:

            async def fail_transcribe(*args, **kwargs):
                raise Exception("Transcription service unavailable")

            mock_transcribe.side_effect = fail_transcribe

            # Act
            response = test_client.post(
                "/agent/action", files={"file": audio_file}, headers=auth_headers
            )

        # Assert
        assert response.status_code == 500
        assert "Failed to transcribe audio" in response.json()["detail"]

    def test_agent_action_unauthenticated(self, test_client):
        """Test agent invocation without authentication."""
        # Arrange
        audio_file = ("test.wav", BytesIO(b"fake audio data"), "audio/wav")

        # Act - No auth headers
        response = test_client.post("/agent/action", files={"file": audio_file})

        # Assert
        assert response.status_code == 403

    def test_agent_action_missing_file(
        self,
        test_client,
        auth_headers,
        mock_get_current_user,
        mock_list_google_accounts,
    ):
        """Test agent invocation without file."""
        # Act
        response = test_client.post("/agent/action", headers=auth_headers)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_agent_action_empty_transcription(
        self,
        test_client,
        auth_headers,
        mock_get_current_user,
        mock_list_google_accounts,
    ):
        """Test agent invocation when transcription returns empty text."""
        # Arrange
        audio_file = ("test.wav", BytesIO(b"fake audio data"), "audio/wav")

        with patch(
            "agent.routes.agent.transcription_service.transcribe"
        ) as mock_transcribe:

            async def empty_transcribe(*args, **kwargs):
                return ""

            mock_transcribe.side_effect = empty_transcribe

            # Act
            response = test_client.post(
                "/agent/action", files={"file": audio_file}, headers=auth_headers
            )

        # Assert
        assert response.status_code == 400
        assert "empty text" in response.json()["detail"]
