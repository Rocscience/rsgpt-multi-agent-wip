"""Record MCP tool outcomes per specialist for validation against LLM summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.multi_agent.mcp_results import tool_result_looks_failed


@dataclass
class ToolRecord:
    tool_name: str
    ok: bool
    excerpt: str
    phase: str = ""


@dataclass
class OpenRecord:
    ok: bool
    skipped: bool = False
    tool_name: str = ""
    excerpt: str = ""
    error: str = ""


class McpEvidenceStore:
    """Per-server MCP call history for one workflow run."""

    def __init__(self) -> None:
        self._tools: dict[str, list[ToolRecord]] = {}
        self._open: dict[str, OpenRecord] = {}

    def record_open(
        self,
        server_id: str,
        *,
        ok: bool,
        skipped: bool = False,
        tool_name: str = "",
        excerpt: str = "",
        error: str = "",
    ) -> None:
        self._open[server_id] = OpenRecord(
            ok=ok,
            skipped=skipped,
            tool_name=tool_name,
            excerpt=excerpt[:1200],
            error=error,
        )

    def record_tool(
        self,
        server_id: str,
        tool_name: str,
        result_text: str,
        *,
        phase: str = "",
    ) -> bool:
        ok = not tool_result_looks_failed(result_text, tool_name=tool_name)
        self._tools.setdefault(server_id, []).append(
            ToolRecord(
                tool_name=tool_name,
                ok=ok,
                excerpt=(result_text or "")[:1200],
                phase=phase,
            )
        )
        return ok

    def open_record(self, server_id: str) -> OpenRecord | None:
        return self._open.get(server_id)

    def tool_records(self, server_id: str) -> list[ToolRecord]:
        return list(self._tools.get(server_id, []))

    def clear_server(self, server_id: str) -> None:
        """Drop tool history for one server (e.g. orchestrator retry — validate attempt only)."""
        self._tools.pop(server_id, None)

    def server_summary(self, server_id: str) -> dict[str, Any]:
        tools = self.tool_records(server_id)
        open_rec = self.open_record(server_id)
        ok_tools = [t.tool_name for t in tools if t.ok]
        fail_tools = [t.tool_name for t in tools if not t.ok]
        return {
            "open_ok": open_rec.ok if open_rec and not open_rec.skipped else None,
            "open_skipped": open_rec.skipped if open_rec else None,
            "open_tool": open_rec.tool_name if open_rec else "",
            "open_error": open_rec.error if open_rec else "",
            "tool_calls_total": len(tools),
            "tool_calls_ok": len(ok_tools),
            "tool_calls_failed": len(fail_tools),
            "successful_tools": ok_tools,
            "failed_tools": fail_tools,
            "recent_excerpts": [
                {"tool": t.tool_name, "ok": t.ok, "excerpt": t.excerpt[:400]}
                for t in tools[-5:]
            ],
        }
