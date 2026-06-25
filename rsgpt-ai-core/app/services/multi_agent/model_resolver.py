"""Resolve model name strings to Agent SDK model objects (LiteLLM-backed)."""

from __future__ import annotations

from typing import Any

from app.services.agent.agent_config import resolve_model


def agent_model(model_name: str) -> Any:
    """Map a provider/model string to a LitellmModel (or compatible) for Agent()."""
    return resolve_model(model_name).model
