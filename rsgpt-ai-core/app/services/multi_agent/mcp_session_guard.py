"""Serialize MCP ClientSession use per server (main work vs inbound peer answers)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class McpSessionGuard:
    """
    One asyncio lock per MCP server id.

    Specialists run in parallel; inbound peer handlers can call MCP tools on the same
    session while the owner is still in main_work. Without this lock, concurrent
    ``call_tool`` / ``list_tools`` corrupts the stdio JSON-RPC stream.
    """

    _locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def lock_for(self, server_id: str) -> asyncio.Lock:
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()
        return self._locks[server_id]
