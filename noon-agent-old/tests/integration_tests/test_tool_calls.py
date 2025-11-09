from datetime import datetime, timedelta
from types import SimpleNamespace

from noon_agent import AgentQuery, invoke_agent
from noon_agent import main as agent_main
from noon_agent.schemas import ParsedIntent


class DummyIntentChain:
    def __init__(self, parsed_intent):
        self._intent = parsed_intent

    def invoke(self, _):
        return self._intent


def test_invoke_agent_accepts_agent_query(monkeypatch):
    start = datetime(2024, 8, 1, 9, 0, 0)
    end = start + timedelta(days=1)
    parsed_intent = ParsedIntent(
        action="schedule",
        start_time=start,
        end_time=end,
        summary="Show my schedule",
    )

    monkeypatch.setattr(agent_main, "get_intent_chain", lambda: DummyIntentChain(parsed_intent))
    monkeypatch.setattr(
        agent_main,
        "calendar_service",
        SimpleNamespace(
            get_schedule=lambda **_: {
                "status": "success",
                "events": [
                    {"event_id": "evt_1", "summary": "Sync"},
                ],
            }
        ),
    )

    response = invoke_agent(AgentQuery(query="show me tomorrow", auth_token="token"))
    assert response == {
        "tool": "show-schedule",
        "start_day": start.date().isoformat(),
        "end_day": end.date().isoformat(),
        "events": [{"event_id": "evt_1", "summary": "Sync"}],
    }
