"""Unit tests for the CalendarService abstraction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest

from noon_agent.calendar_service import CalendarService, CalendarServiceError


def _stub_service_factory(expected_token: str):
    captured: Dict[str, Any] = {}

    def factory(token: str):
        captured["token"] = token
        return object()

    return factory, captured


def test_create_event_uses_context_defaults(monkeypatch):
    calls: Dict[str, Any] = {}

    def fake_create_calendar_event(**kwargs):
        calls.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(
        "services.calendar_client.service.create_calendar_event", fake_create_calendar_event
    )

    factory, captured = _stub_service_factory("token-123")
    service = CalendarService(service_factory=factory)

    start = datetime.now(timezone.utc)
    result = service.create_event(
        auth_token="token-123",
        summary="Demo",
        start_time=start,
        end_time=start + timedelta(hours=1),
        attendees=["a@example.com"],
        context={"primary_calendar_id": "team", "timezone": "America/Los_Angeles"},
    )

    assert result["status"] == "success"
    assert captured["token"] == "token-123"
    assert calls["calendar_id"] == "team"
    assert calls["timezone"] == "America/Los_Angeles"
    assert calls["attendees"] == ["a@example.com"]


def test_read_events_defaults_to_primary(monkeypatch):
    calls: Dict[str, Any] = {}

    def fake_read_calendar_events(**kwargs):
        calls.update(kwargs)
        return {"status": "success", "count": 0, "events": []}

    monkeypatch.setattr(
        "services.calendar_client.service.read_calendar_events", fake_read_calendar_events
    )

    service = CalendarService(service_factory=lambda _: object())
    service.read_events(auth_token="abc", time_min=datetime.now(timezone.utc))

    assert calls["calendar_id"] == "primary"
    assert calls["max_results"] == 250


def test_update_event_requires_identifier():
    service = CalendarService(service_factory=lambda _: object())

    with pytest.raises(CalendarServiceError):
        service.update_event(auth_token="abc", event_id=None)


def test_search_events_requires_query():
    service = CalendarService(service_factory=lambda _: object())

    with pytest.raises(CalendarServiceError):
        service.search_events(auth_token="abc", query="")


def test_get_schedule_requires_date_range():
    service = CalendarService(service_factory=lambda _: object())

    with pytest.raises(CalendarServiceError):
        service.get_schedule(auth_token="abc", start_time=None, end_time=None)


def test_build_service_falls_back_to_token_file(monkeypatch):
    fallback_service = object()
    captured: Dict[str, Any] = {}

    monkeypatch.setattr(
        "services.calendar_client.service.get_calendar_service_from_file",
        lambda cred, token: fallback_service,
    )

    def fake_read_calendar_events(service, **kwargs):
        captured["service"] = service
        return {"status": "success", "count": 0, "events": []}

    monkeypatch.setattr(
        "services.calendar_client.service.read_calendar_events", fake_read_calendar_events
    )

    def token_factory(_token):
        raise AssertionError("token factory should not be called when using token file fallback")

    service = CalendarService(
        service_factory=token_factory,
        use_token_file=True,
        credentials_path="credentials.json",
        token_path="token.json",
    )

    service.read_events(auth_token=None, time_min=datetime.now(timezone.utc))
    assert captured["service"] is fallback_service
