"""Unit tests for the CalendarAgentService abstraction."""

from __future__ import annotations

import sys
import types
from pathlib import Path

# Ensure the backend package root is on sys.path so `services` imports work when
# the test runner executes from other directories (e.g., repo root).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

import pytest


def _install_google_stubs():
    """Provide minimal google client stubs so noon-agent imports succeed."""

    def ensure(name: str):
        if name in sys.modules:
            return sys.modules[name]
        module = types.ModuleType(name)
        sys.modules[name] = module
        return module

    ensure("google")
    ensure("google.auth")
    ensure("google.auth.transport")
    requests_mod = ensure("google.auth.transport.requests")

    class Request:  # pragma: no cover - never invoked
        pass

    requests_mod.Request = Request

    ensure("google.oauth2")
    credentials_mod = ensure("google.oauth2.credentials")

    class Credentials:  # pragma: no cover - never invoked
        def __init__(self, token=None):
            self.token = token

        def refresh(self, _request):
            return None

        def to_json(self):
            return "{}"

    credentials_mod.Credentials = Credentials

    ensure("google_auth_oauthlib")
    flow_mod = ensure("google_auth_oauthlib.flow")

    class InstalledAppFlow:  # pragma: no cover - never invoked
        @classmethod
        def from_client_secrets_file(cls, *_args, **_kwargs):
            return cls()

        def run_local_server(self, **_kwargs):
            raise RuntimeError("OAuth not supported in tests")

    flow_mod.InstalledAppFlow = InstalledAppFlow

    ensure("googleapiclient")
    discovery_mod = ensure("googleapiclient.discovery")
    errors_mod = ensure("googleapiclient.errors")

    def build(*_args, **_kwargs):  # pragma: no cover - never invoked
        class DummyService:
            def events(self):
                raise RuntimeError("Not implemented")

        return DummyService()

    discovery_mod.build = build

    class HttpError(Exception):
        pass

    errors_mod.HttpError = HttpError


_install_google_stubs()

from services.calendar_agent import (  # noqa: E402
    CalendarAgentError,
    CalendarAgentService,
    CalendarAgentUserError,
)


class DummyGraph:
    def __init__(self, response):
        self._response = response
        self.invocations = []

    def invoke(self, state):
        self.invocations.append(state)
        return self._response


def _default_context():
    return {
        "access_token": "token-123",
        "primary_calendar_id": "primary",
        "timezone": "UTC",
        "all_calendar_ids": ["primary"],
        "friends": [],
    }


def _context_without_token():
    ctx = _default_context()
    ctx.pop("access_token", None)
    return ctx


def test_chat_invokes_graph_with_expected_state():
    graph = DummyGraph(
        {
            "action": "create",
            "response": "Created lunch",
            "result_data": {"id": "abc"},
            "success": True,
        }
    )

    service = CalendarAgentService(
        graph=graph,
        load_user_context=lambda user_id: _default_context(),
    )

    result = service.chat(user_id="user-1", message="book lunch")

    assert result == {
        "tool": "create",
        "summary": "Created lunch",
        "result": {"id": "abc"},
        "success": True,
    }
    assert graph.invocations  # ensures graph was called
    state = graph.invocations[0]
    assert state["messages"] == "book lunch"
    assert state["auth_token"] == "token-123"
    assert state["context"]["primary_calendar_id"] == "primary"


def test_chat_raises_when_message_missing():
    service = CalendarAgentService(
        graph=DummyGraph({}),
        load_user_context=lambda user_id: _default_context(),
    )

    with pytest.raises(CalendarAgentUserError):
        service.chat(user_id="user-1", message="")


def test_chat_requires_access_token():
    service = CalendarAgentService(
        graph=DummyGraph({}),
        load_user_context=lambda user_id: _context_without_token(),
    )

    with pytest.raises(CalendarAgentUserError):
        service.chat(user_id="user-1", message="hello")


def test_chat_wraps_graph_errors():
    class ExplodingGraph:
        def invoke(self, state):
            raise RuntimeError("boom")

    service = CalendarAgentService(
        graph=ExplodingGraph(),
        load_user_context=lambda user_id: _default_context(),
    )

    with pytest.raises(CalendarAgentError) as excinfo:
        service.chat(user_id="user-1", message="ping")

    assert "boom" in str(excinfo.value)
