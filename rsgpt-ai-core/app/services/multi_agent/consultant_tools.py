"""Tool for MCP specialists to query the RAG software consultant."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from agents.tool import FunctionTool
from agents.tool_context import ToolContext

if TYPE_CHECKING:
    from app.services.multi_agent.agents.specialist import MCPSpecialistAgent

_ASK_CONSULTANT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": (
                "What you need guidance on: workflow order, menu paths, parameter meaning, "
                "or how to create/configure a model from scratch"
            ),
        },
        "software": {
            "type": "string",
            "description": (
                "Optional product hint (e.g. RS2, RSPile). Defaults to your specialist product."
            ),
        },
    },
    "required": ["question"],
    "additionalProperties": False,
}


def make_ask_software_consultant_tool(agent: MCPSpecialistAgent) -> FunctionTool:
    default_software = agent._app.catalog.entry(agent.server_id).display_name or agent.server_id

    async def on_invoke(_ctx: ToolContext[Any], arguments: str) -> str:
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        question = (args.get("question") or "").strip()
        software = (args.get("software") or default_software).strip()
        if not question:
            return "Provide a question describing what workflow guidance you need."
        return await agent.request_consultant(question, software=software)

    return FunctionTool(
        name="ask_software_consultant",
        description=(
            "Ask the software consultant (RAG knowledge base) when you are unsure about "
            "Rocscience workflow order, menu paths, parameter meaning, or how to create a "
            "model from scratch instead of opening an existing file. "
            "Use for HOW-TO guidance — not for live model data (use MCP tools or ask_agent_peer)."
        ),
        params_json_schema=_ASK_CONSULTANT_SCHEMA,
        on_invoke_tool=on_invoke,
        strict_json_schema=False,
    )
