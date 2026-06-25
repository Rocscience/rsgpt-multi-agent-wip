"""Device WebSocket MCP pool — one adapter per logical server_id."""

from __future__ import annotations

import logging

from app.services.multi_agent.device_mcp_adapter import DeviceMcpSessionAdapter
from app.services.multi_agent.mcp_protocol import McpSessionProtocol
from app.services.multi_agent.schema import ServerEntry
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


class DeviceMcpPool:
    """Cache DeviceMcpSessionAdapter instances per server_id (no process spawn)."""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.sessions: dict[str, McpSessionProtocol] = {}

    async def ensure_connected(self, server_id: str, entry: ServerEntry) -> None:
        if server_id in self.sessions:
            return
        if not connection_manager.is_device_connected(self.device_id):
            raise ValueError(
                f"Device {self.device_id} not connected — "
                "open RSInsight desktop and sign in."
            )
        adapter = DeviceMcpSessionAdapter(
            device_id=self.device_id,
            server_id=server_id,
            entry=entry,
        )
        await adapter.list_tools()
        self.sessions[server_id] = adapter
        logger.info("DeviceMcpPool connected %s via device %s", server_id, self.device_id)

    async def refresh_tools(self, server_id: str) -> None:
        session = self.sessions.get(server_id)
        if session and isinstance(session, DeviceMcpSessionAdapter):
            session.invalidate_cache()
            await session.list_tools()

    async def aclose(self) -> None:
        """No-op — desktop owns MCP lifecycle."""
        self.sessions.clear()
