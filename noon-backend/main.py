"""Minimal backend proxy that streams messages to the LangGraph deployment."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langgraph_sdk import get_sync_client
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Configuration sourced from environment variables / .env."""

    langgraph_url: str = Field(..., alias="LANGGRAPH_URL")
    langsmith_api_key: str = Field(..., alias="LANGSMITH_API_KEY")
    agent_name: str = Field(default="noon-agent", alias="LANGGRAPH_AGENT_NAME")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
client = get_sync_client(url=settings.langgraph_url, api_key=settings.langsmith_api_key)
app = FastAPI(title="Noon Backend", version="0.1.0")


class Message(BaseModel):
    role: Literal["human", "assistant", "system", "tool"]
    content: str
    metadata: Dict[str, Any] | None = None


class AgentRunRequest(BaseModel):
    messages: List[Message]
    thread_id: Optional[str] = None
    stream_mode: Literal["updates", "values"] = "updates"


@app.get("/healthz")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/runs")
def run_agent(payload: AgentRunRequest) -> Dict[str, Any]:
    try:
        stream = client.runs.stream(
            payload.thread_id,
            settings.agent_name,
            input={"messages": [message.model_dump(exclude_none=True) for message in payload.messages]},
            stream_mode=payload.stream_mode,
        )

        events = []
        for chunk in stream:
            events.append({"event": chunk.event, "data": chunk.data})

        return {"events": events}
    except Exception as exc:  # pragma: no cover - surfaced via HTTP
        raise HTTPException(status_code=502, detail=f"Agent invocation failed: {exc}") from exc


@app.post("/agent/test")
def run_agent_test() -> Dict[str, Any]:
    """Trigger a canned test run to verify tracing works end-to-end."""

    payload = AgentRunRequest(
        messages=[Message(role="human", content="Please schedule lunch tomorrow at 1pm")],
    )
    result = run_agent(payload)
    latest = result["events"][-1]["data"] if result["events"] else {}
    return {"response": latest.get("response"), "success": latest.get("success")}
