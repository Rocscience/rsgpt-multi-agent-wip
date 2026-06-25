"""Minimal MCP-like protocol types (no mcp SDK dependency)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class McpTool:
    name: str
    description: str = ""
    title: str = ""
    inputSchema: dict[str, Any] = field(default_factory=dict)


@dataclass
class McpContentBlock:
    text: str = ""
    type: str = "text"


@dataclass
class ListToolsResult:
    tools: list[McpTool] = field(default_factory=list)


@dataclass
class CallToolResult:
    content: list[McpContentBlock] = field(default_factory=list)
    structured_content: Any | None = None
    isError: bool = False


@runtime_checkable
class McpSessionProtocol(Protocol):
    async def list_tools(self) -> ListToolsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> CallToolResult: ...
