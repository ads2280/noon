"""Simple mock tools for local development."""

from datetime import datetime


def ping_tool(_: dict | None = None) -> str:
    """Return a quick heartbeat message."""

    return "pong"


def clock_tool(_: dict | None = None) -> str:
    """Return the current ISO timestamp."""

    return datetime.utcnow().isoformat()
