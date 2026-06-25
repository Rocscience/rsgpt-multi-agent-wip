"""MCP bootstrap tool calls before specialist LLM runs."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.schema import BootstrapCall

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int) -> str:
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


def _normalize_bootstrap(calls: Sequence[BootstrapCall | dict]) -> list[BootstrapCall]:
    out: list[BootstrapCall] = []
    for c in calls:
        if isinstance(c, BootstrapCall):
            out.append(c)
        else:
            out.append(BootstrapCall.model_validate(c))
    return out


async def run_bootstrap(
    session: ClientSession,
    calls: Sequence[BootstrapCall | dict],
    *,
    log_label: str = "",
    mcp_guard: McpSessionGuard | None = None,
) -> None:
    tag = f"[{log_label}] " if log_label else ""
    lock = mcp_guard.lock_for(log_label) if mcp_guard and log_label else None
    for c in _normalize_bootstrap(calls):
        args_s = json.dumps(c.arguments, default=str)
        logger.info("%sBootstrap → %s(%s)", tag, c.tool_name, _truncate(args_s, 400))
        if lock:
            async with lock:
                await session.call_tool(c.tool_name, arguments=c.arguments)
        else:
            await session.call_tool(c.tool_name, arguments=c.arguments)
