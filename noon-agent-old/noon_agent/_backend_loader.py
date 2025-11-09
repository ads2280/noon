"""Utilities for importing shared backend services."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_backend_on_path() -> None:
    """
    Add the noon-backend directory to sys.path so noon-agent can import shared services.

    This lets the agent reuse calendar client modules that now live under
    ``noon-backend/services`` without requiring a packaged dependency.
    """

    backend_dir = Path(__file__).resolve().parents[2] / "noon-backend"
    backend_path = str(backend_dir)
    if backend_dir.exists() and backend_path not in sys.path:
        sys.path.insert(0, backend_path)


ensure_backend_on_path()
