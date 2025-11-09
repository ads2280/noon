"""Backend that handles Supabase auth and forwards requests to LangGraph deployment."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import uvicorn

from app import create_app as create_supabase_app

load_dotenv()

# Create the Supabase auth app (includes /auth/* and /google-accounts routes)
app = create_supabase_app()


# LangGraph configuration (optional - only if env vars present)
class Settings(BaseSettings):
    """Configuration sourced from environment variables / .env."""

    langgraph_url: Optional[str] = Field(default=None, alias="LANGGRAPH_URL")
    langsmith_api_key: Optional[str] = Field(default=None, alias="LANGSMITH_API_KEY")
    agent_name: str = Field(default="noon-agent", alias="LANGGRAPH_AGENT_NAME")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# Only set up LangGraph client if credentials are provided
if settings.langgraph_url and settings.langsmith_api_key:
    from langgraph_sdk import get_sync_client

    client = get_sync_client(
        url=settings.langgraph_url, api_key=settings.langsmith_api_key
    )
else:
    client = None


class Message(BaseModel):
    role: Literal["human", "assistant", "system", "tool"]
    content: str
    metadata: Dict[str, Any] | None = None


class AgentRunRequest(BaseModel):
    messages: List[Message]
    thread_id: Optional[str] = None
    stream_mode: Literal["updates", "values"] = "updates"


@app.post("/agent/runs")
def run_agent(payload: AgentRunRequest) -> Dict[str, Any]:
    if not client:
        raise HTTPException(status_code=503, detail="LangGraph not configured")

    try:
        stream = client.runs.stream(
            payload.thread_id,
            settings.agent_name,
            input={
                "messages": [
                    message.model_dump(exclude_none=True)
                    for message in payload.messages
                ]
            },
            stream_mode=payload.stream_mode,
        )

        event = []
        for chunk in stream:
            events.append({"event": chunk.event, "data": chunk.data})

        return {"events": events}
    except Exception as exc:  # pragma: no cover - surfaced via HTTP
        raise HTTPException(
            status_code=502, detail=f"Agent invocation failed: {exc}"
        ) from exc


@app.post("/agent/test")
def run_agent_test() -> Dict[str, Any]:
    """Trigger a canned test run to verify tracing works end-to-end."""

    payload = AgentRunRequest(
        messages=[
            Message(role="human", content="Please schedule lunch tomorrow at 1pm")
        ],
    )
    result = run_agent(payload)
    latest = result["events"][-1]["data"] if result["events"] else {}
    return {"response": latest.get("response"), "success": latest.get("success")}


def run() -> None:
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
    )


if __name__ == "__main__":
    run()
