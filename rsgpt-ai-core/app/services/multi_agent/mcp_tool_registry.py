"""Live MCP tool catalog per server — refreshed on connect, bootstrap, and model open."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.mcp_session_guard import McpSessionGuard

logger = logging.getLogger(__name__)

_READ_TOOL_PATTERNS = (
    "get_model_state",
    "get_model_settings",
    "get_model_results",
    "analyze_model",
    "show_active",
    "get_srf_value",
    "introspect",
)

_DISCOVERY_TOOL_PATTERNS = (
    "grep_tool",
    "get_relevant_functions",
    "bigtool",
)

_ACTIVATE_TOOL_PATTERNS = (
    "activate_function_by_name",
    "call_function",
)

@dataclass
class ToolInfo:
    name: str
    description: str = ""


@dataclass
class ToolCatalogSnapshot:
    server_id: str
    phase: str
    tools: list[ToolInfo] = field(default_factory=list)
    ts: float = field(default_factory=time.time)

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self.tools]


async def fetch_tool_catalog(
    session: ClientSession,
    server_id: str,
    *,
    phase: str,
    mcp_guard: McpSessionGuard | None = None,
) -> ToolCatalogSnapshot:
    if mcp_guard:
        async with mcp_guard.lock_for(server_id):
            lr = await session.list_tools()
    else:
        lr = await session.list_tools()
    tools: list[ToolInfo] = []
    for t in lr.tools:
        desc = (t.description or "").strip()
        if not desc and t.title:
            desc = str(t.title).strip()
        tools.append(ToolInfo(name=t.name, description=desc[:500]))
    tools.sort(key=lambda x: x.name.lower())
    snap = ToolCatalogSnapshot(server_id=server_id, phase=phase, tools=tools)
    logger.info(
        "MCP tools [%s] phase=%s count=%d",
        server_id,
        phase,
        len(tools),
    )
    return snap


def _match_names(names: list[str], patterns: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for name in names:
        lower = name.lower()
        if any(p in lower for p in patterns):
            out.append(name)
    return out


def _state_tool_hint(catalog_entry) -> list[str]:
    tool = (getattr(catalog_entry, "state_tool", None) or "").strip()
    return [tool] if tool else []


def read_first_tool_names(names: list[str]) -> list[str]:
    return _match_names(names, _READ_TOOL_PATTERNS)


def server_playbook(
    server_id: str,
    *,
    yaml_playbook: str = "",
) -> str:
    """Render the product playbook for a server (sourced from config)."""
    text = (yaml_playbook or "").strip()
    if not text:
        return ""
    return "PRODUCT PLAYBOOK:\n" + text


def build_tool_guidance(
    snapshot: ToolCatalogSnapshot | None,
    *,
    server_id: str = "",
    state_tool_names: list[str] | None = None,
    agent_playbook: str = "",
) -> str:
    if not snapshot or not snapshot.tools:
        return (
            "REGISTERED MCP TOOLS: (none discovered yet). "
            "Call list_tools via bootstrap/open before inventing tool names."
        )

    names = snapshot.tool_names
    state_tool_names = state_tool_names or []
    read_first = _match_names(names, _READ_TOOL_PATTERNS)
    for st in state_tool_names:
        if st and st in names and st not in read_first:
            read_first.insert(0, st)

    discovery = _match_names(names, _DISCOVERY_TOOL_PATTERNS)
    activate = _match_names(names, _ACTIVATE_TOOL_PATTERNS)

    lines = [
        "REGISTERED MCP TOOLS — you may ONLY call tool names from this list (never invent names):",
        ", ".join(names),
        "",
    ]
    if read_first:
        read_note = (
            "READ FIRST (open/summary tools; RSPile soil still needs grep+activate+invoke after these): "
            if server_id == "rspile-server"
            else "READ FIRST (prefer these before BigTool / activate_function_by_name): "
        )
        lines.append(read_note + ", ".join(read_first))
    if discovery:
        lines.append(
            "DISCOVERY (use before guessing internal API names): " + ", ".join(discovery)
        )
    if activate:
        lines.append(
            "ACTIVATE (only after discovery; if output says 'Function not found', "
            "use grep/relevant_functions — do not retry guessed names): "
            + ", ".join(activate)
        )
    lines.append(
        "If a tool returns 'Function ... not found' or 'not found on root object', "
        "that name is invalid — discover the correct name, do not hallucinate success."
    )
    playbook = server_playbook(server_id, yaml_playbook=agent_playbook)
    if playbook:
        lines.append("")
        lines.append(playbook)
    return "\n".join(lines)


class McpToolRegistry:
    """Per-run registry of MCP tool snapshots keyed by server_id."""

    def __init__(self) -> None:
        self._latest: dict[str, ToolCatalogSnapshot] = {}

    async def refresh(
        self,
        session: ClientSession,
        server_id: str,
        *,
        phase: str,
        mcp_guard: McpSessionGuard | None = None,
    ) -> ToolCatalogSnapshot:
        snap = await fetch_tool_catalog(
            session, server_id, phase=phase, mcp_guard=mcp_guard
        )
        self._latest[server_id] = snap
        return snap

    def latest(self, server_id: str) -> ToolCatalogSnapshot | None:
        return self._latest.get(server_id)

    def guidance_for(
        self,
        server_id: str,
        *,
        state_tool_names: list[str] | None = None,
        agent_playbook: str = "",
    ) -> str:
        return build_tool_guidance(
            self.latest(server_id),
            server_id=server_id,
            state_tool_names=state_tool_names,
            agent_playbook=agent_playbook,
        )

    def read_first_tools(self, server_id: str) -> list[str]:
        snap = self.latest(server_id)
        if not snap:
            return []
        return read_first_tool_names(snap.tool_names)