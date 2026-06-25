"""One generic peer tool: ask any other active specialist."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from agents.tool import FunctionTool
from agents.tool_context import ToolContext

if TYPE_CHECKING:
    from app.services.multi_agent.agents.specialist import MCPSpecialistAgent

_ASK_PEER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target_server_id": {
            "type": "string",
            "description": "server_id of the specialist to ask (from active roster)",
        },
        "question": {
            "type": "string",
            "description": "Natural-language question; they answer from their open model via MCP",
        },
    },
    "required": ["target_server_id", "question"],
    "additionalProperties": False,
}


def make_ask_agent_peer_tool(
    agent: MCPSpecialistAgent,
    *,
    allowed_targets: list[str],
) -> FunctionTool:
    allowed_set = set(allowed_targets)

    async def on_invoke(_ctx: ToolContext[Any], arguments: str) -> str:
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        target = (args.get("target_server_id") or "").strip()
        question = (args.get("question") or "").strip()
        if not target or not question:
            return "Provide target_server_id and question."
        if target not in allowed_set:
            return (
                f"Invalid target_server_id '{target}'. "
                f"Active peers: {sorted(allowed_set)}"
            )
        return await agent.request_peer(target, question)

    targets_hint = ", ".join(sorted(allowed_set)) if allowed_set else "(none)"
    return FunctionTool(
        name="ask_agent_peer",
        description=(
            "Ask another specialist agent a blocking question while you work. "
            f"Allowed target_server_id values: {targets_hint}. "
            "Use after your model is open when you need their data."
        ),
        params_json_schema=_ASK_PEER_SCHEMA,
        on_invoke_tool=on_invoke,
        strict_json_schema=False,
    )
