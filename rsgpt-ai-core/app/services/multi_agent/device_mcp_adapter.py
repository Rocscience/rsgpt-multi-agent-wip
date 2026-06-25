"""WebSocket-backed MCP session adapter for desktop device tools."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.services.multi_agent.mcp_protocol import (
    CallToolResult,
    ListToolsResult,
    McpContentBlock,
    McpTool,
)
from app.services.multi_agent.schema import ServerEntry
from app.services.multi_agent.tool_filter import filter_tools_for_server
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)

_INVOKE_TIMEOUT = 1800.0
_LIST_TIMEOUT = 60.0

# Serialize concurrent invokes per device (single stdio MCP gateway on desktop).
_device_locks: dict[str, asyncio.Lock] = {}


def get_device_invoke_lock(device_id: str) -> asyncio.Lock:
    if device_id not in _device_locks:
        _device_locks[device_id] = asyncio.Lock()
    return _device_locks[device_id]


class DeviceMcpSessionAdapter:
    """
    Presents a subset of desktop MCP tools as an isolated session per server_id.
    """

    def __init__(
        self,
        *,
        device_id: str,
        server_id: str,
        entry: ServerEntry,
    ) -> None:
        self.device_id = device_id
        self.server_id = server_id
        self.entry = entry
        self._cached_tools: list[McpTool] | None = None

    async def _fetch_all_tools_raw(self) -> list[dict[str, Any]]:
        response = await connection_manager.request_list_tools(
            self.device_id, timeout=_LIST_TIMEOUT
        )
        tools = response.get("tools") or []
        if not isinstance(tools, list):
            return []
        return tools

    async def list_tools(self) -> ListToolsResult:
        raw = await self._fetch_all_tools_raw()
        filtered = filter_tools_for_server(raw, self.server_id, self.entry)
        mcp_tools = [
            McpTool(
                name=str(t.get("name", "")),
                description=str(t.get("description") or ""),
                title=str(t.get("title") or ""),
                inputSchema=dict(t.get("input_schema") or t.get("inputSchema") or {}),
            )
            for t in filtered
            if t.get("name")
        ]
        self._cached_tools = mcp_tools
        logger.info(
            "DeviceMcpSession [%s] list_tools: %d tools (device=%s)",
            self.server_id,
            len(mcp_tools),
            self.device_id,
        )
        return ListToolsResult(tools=mcp_tools)

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> CallToolResult:
        args = arguments or {}
        lock = get_device_invoke_lock(self.device_id)
        async with lock:
            try:
                response = await connection_manager.request_invoke_tool(
                    self.device_id,
                    name,
                    args,
                    timeout=_INVOKE_TIMEOUT,
                )
            except Exception as exc:
                logger.exception("Device invoke failed: %s", name)
                return CallToolResult(
                    content=[McpContentBlock(text=f"Error calling {name}: {exc}")],
                    isError=True,
                )

        if response.get("error"):
            err = response["error"]
            text = err if isinstance(err, str) else json.dumps(err, default=str)
            return CallToolResult(
                content=[McpContentBlock(text=text)],
                isError=True,
            )

        result = response.get("result") or response
        content_blocks: list[McpContentBlock] = []
        raw_content = result.get("content") if isinstance(result, dict) else None
        if isinstance(raw_content, list):
            for item in raw_content:
                if isinstance(item, str):
                    content_blocks.append(McpContentBlock(text=item))
                elif isinstance(item, dict) and item.get("text") is not None:
                    content_blocks.append(McpContentBlock(text=str(item["text"])))
                else:
                    content_blocks.append(McpContentBlock(text=str(item)))
        elif isinstance(result, dict):
            content_blocks.append(
                McpContentBlock(text=json.dumps(result, default=str, indent=2))
            )
        else:
            content_blocks.append(McpContentBlock(text=str(result)))

        is_error = bool(
            isinstance(result, dict) and result.get("is_error")
        )
        structured = result.get("structured") if isinstance(result, dict) else None
        return CallToolResult(
            content=content_blocks,
            structured_content=structured,
            isError=is_error,
        )

    def invalidate_cache(self) -> None:
        self._cached_tools = None
