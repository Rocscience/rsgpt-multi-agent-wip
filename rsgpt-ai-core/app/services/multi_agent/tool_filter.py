"""Filter unified desktop MCP tool list per logical server_id."""

from __future__ import annotations

import re
from typing import Any

from app.services.multi_agent.schema import ServerEntry

# Shared landing-server tools — never assigned to product specialists.
_EXCLUDED = frozenset({"read_file", "grep_search", "get_server_statuses"})


def _server_patterns(server_id: str, entry: ServerEntry) -> tuple[str, ...]:
    """Tool-name patterns for a server: config-declared, else derived from id.

    The desktop gateway aggregates every product's tools onto one device, so we
    need to know which tool names route to which logical server. Patterns live in
    ``ServerEntry.tool_patterns`` (config). As a fallback for products that follow
    the conventional ``<prefix>_tool`` naming, derive ``^<prefix>_`` from the id.
    """
    if entry.tool_patterns:
        return tuple(entry.tool_patterns)
    base = (server_id or "").split("-server")[0].strip()
    return (rf"^{re.escape(base)}_",) if base else ()


def tool_belongs_to_server(name: str, server_id: str, entry: ServerEntry) -> bool:
    """Return True if tool name belongs to the given logical MCP server."""
    tool = (name or "").strip()
    if not tool or tool in _EXCLUDED:
        return False
    if entry.open_tool and tool == entry.open_tool:
        return True
    state = (entry.state_tool or "").strip()
    if state and tool == state:
        return True
    for bc in entry.bootstrap_tools:
        if tool == bc.tool_name:
            return True
    for pat in _server_patterns(server_id, entry):
        if re.search(pat, tool, re.I):
            return True
    return False


def filter_tools_for_server(
    tools: list[dict[str, Any]],
    server_id: str,
    entry: ServerEntry,
) -> list[dict[str, Any]]:
    return [
        t
        for t in tools
        if tool_belongs_to_server(str(t.get("name", "")), server_id, entry)
    ]
