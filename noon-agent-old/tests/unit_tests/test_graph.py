from datetime import datetime, timedelta
from types import SimpleNamespace

from noon_agent import invoke_agent
from noon_agent import main as agent_main
from noon_agent.schemas import ParsedIntent


class DummyIntentChain:
    def __init__(self, parsed_intent):
        self._intent = parsed_intent

    def invoke(self, _):
        return self._intent


def _stub_intent(monkeypatch, parsed_intent):
    monkeypatch.setattr(agent_main, "get_intent_chain", lambda: DummyIntentChain(parsed_intent))


def _stub_service(monkeypatch, **methods):
    monkeypatch.setattr(agent_main, "calendar_service", SimpleNamespace(**methods))


def _base_intent(action: str, start: datetime, end: datetime) -> ParsedIntent:
    return ParsedIntent(
        action=action,
        start_time=start,
        end_time=end,
        people=["user@example.com"],
        summary="Team sync",
        event_id="evt_123" if action in {"update", "delete"} else None,
        calendar_id="primary",
    )


def test_invoke_agent_create_returns_create_payload(monkeypatch):
    start = datetime(2024, 2, 1, 14, 0, 0)
    end = start + timedelta(hours=1)
    _stub_intent(monkeypatch, _base_intent("create", start, end))

    create_result = {
        "status": "success",
        "event_id": "evt_plan",
        "calendar_id": "primary",
        "summary": "Team sync",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "link": "https://example.com",
    }
    _stub_service(monkeypatch, create_event=lambda **_: create_result)

    response = invoke_agent({"query": "plan something", "auth_token": "token"})
    assert response["tool"] == "create"
    assert response["id"] == "evt_plan"
    assert response["calendar"] == "primary"
    assert response["start_time"] == start.isoformat()
    assert response["metadata"] == {"service_result": create_result}


def test_invoke_agent_schedule_returns_show_schedule_payload(monkeypatch):
    start = datetime(2024, 3, 1, 9, 0, 0)
    end = start + timedelta(days=5)
    _stub_intent(monkeypatch, _base_intent("schedule", start, end))

    _stub_service(
        monkeypatch,
        get_schedule=lambda **_: {
            "status": "success",
            "events": [{"summary": "Foo"}],
        },
    )

    response = invoke_agent({"query": "show my week", "auth_token": "token"})
    assert response == {
        "tool": "show-schedule",
        "start_day": start.date().isoformat(),
        "end_day": end.date().isoformat(),
        "events": [{"summary": "Foo"}],
    }


def test_invoke_agent_update_returns_update_payload(monkeypatch):
    start = datetime(2024, 4, 1, 10, 0, 0)
    end = start + timedelta(hours=2)
    intent = _base_intent("update", start, end)
    _stub_intent(monkeypatch, intent)

    _stub_service(
        monkeypatch,
        update_event=lambda **_: {
            "status": "success",
            "event_id": "evt_update",
            "calendar_id": "primary",
            "summary": "Team sync",
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )

    response = invoke_agent({"query": "update it", "auth_token": "token"})
    assert response["tool"] == "update"
    assert response["id"] == "evt_update"
    assert response["changes"]["summary"] == "Team sync"


def test_invoke_agent_delete_returns_delete_payload(monkeypatch):
    start = datetime(2024, 5, 1, 10, 0, 0)
    end = start + timedelta(hours=1)
    _stub_intent(monkeypatch, _base_intent("delete", start, end))

    _stub_service(
        monkeypatch,
        delete_event=lambda **_: {
            "status": "success",
            "event_id": "evt_delete",
            "calendar_id": "primary",
        },
    )

    response = invoke_agent({"query": "delete", "auth_token": "token"})
    assert response == {"tool": "delete", "id": "evt_delete", "calendar": "primary"}


def test_invoke_agent_search_returns_show_payload(monkeypatch):
    start = datetime(2024, 6, 1, 8, 0, 0)
    end = start + timedelta(hours=1)
    _stub_intent(monkeypatch, _base_intent("search", start, end))

    events = [
        {
            "event_id": "evt_search",
            "calendar_id": "primary",
            "summary": "Team sync",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    ]

    _stub_service(
        monkeypatch,
        search_events=lambda **_: {"status": "success", "events": events},
    )

    response = invoke_agent({"query": "search", "auth_token": "token"})
    assert response["tool"] == "show"
    assert response["id"] == "evt_search"
    assert response["event"]["matches"] == events


def test_invoke_agent_read_returns_show_payload(monkeypatch):
    start = datetime(2024, 7, 1, 8, 0, 0)
    end = start + timedelta(hours=1)
    _stub_intent(monkeypatch, _base_intent("read", start, end))

    events = [
        {
            "event_id": "evt_read",
            "calendar_id": "primary",
            "summary": "Daily standup",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    ]

    _stub_service(
        monkeypatch,
        read_events=lambda **_: {"status": "success", "events": events},
    )

    response = invoke_agent({"query": "read", "auth_token": "token"})
    assert response["tool"] == "show"
    assert response["id"] == "evt_read"
