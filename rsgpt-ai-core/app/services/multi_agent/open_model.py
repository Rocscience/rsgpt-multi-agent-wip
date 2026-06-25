"""Open model files via MCP before specialists use peer tools (avoids empty-model peer answers)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.activity import ActivityLog
from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_results import format_tool_result, tool_result_looks_failed
from app.services.multi_agent.mcp_tool_registry import McpToolRegistry, read_first_tool_names
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.model_paths import normalize_path
from app.services.multi_agent.workflow_hints import path_is_absent
from app.services.multi_agent.registry import ServerCatalog

if TYPE_CHECKING:
    from app.services.multi_agent.app_context import AppContext

logger = logging.getLogger(__name__)


async def open_model_for_server(
    *,
    catalog: ServerCatalog,
    server_id: str,
    session: ClientSession,
    file_path: str,
    activity: ActivityLog,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    tool_registry: McpToolRegistry | None = None,
    app: AppContext | None = None,
    force: bool = False,
) -> str:
    """Call the configured open_tool if path is usable. Returns status text for the LLM."""
    fp = normalize_path(file_path)
    if path_is_absent(fp):
        activity.emit("open_skipped", server_id=server_id, reason="no file path")
        if evidence:
            evidence.record_open(server_id, ok=False, skipped=True)
        return "No file path configured; skip open."

    if app and not force and app.open_is_ok(server_id, fp):
        cached = app.cached_open_status(server_id) or "Model already open for this workflow."
        activity.emit(
            "open_skipped",
            server_id=server_id,
            reason="already_open",
            file_path=fp,
            cached_status_excerpt=cached[:300],
        )
        return (
            f"Model already open for this workflow (no re-open): {fp}\n"
            f"Prior open result: {cached}"
        )

    entry = catalog.entry(server_id)
    tool = (entry.open_tool or "").strip()
    if not tool:
        activity.emit("open_skipped", server_id=server_id, reason="no open_tool in config")
        if evidence:
            evidence.record_open(server_id, ok=False, skipped=True)
        return f"No open_tool configured for {server_id}."

    activity.emit("open_started", server_id=server_id, file_path=fp, tool_name=tool)
    try:
        arg_name = (entry.open_path_arg or "").strip()
        open_args = {arg_name: fp} if arg_name else {}
        if mcp_guard:
            async with mcp_guard.lock_for(server_id):
                result = await session.call_tool(tool, arguments=open_args)
        else:
            result = await session.call_tool(tool, arguments=open_args)
        text = format_tool_result(result)
        ok = not tool_result_looks_failed(text)
        if evidence:
            evidence.record_open(
                server_id,
                ok=ok,
                tool_name=tool,
                excerpt=text,
            )
        if app:
            app.record_open_session(
                server_id,
                file_path=fp,
                status_text=text,
                ok=ok,
            )
        activity.emit(
            "open_completed",
            server_id=server_id,
            result_excerpt=text[:500],
            ok=ok,
        )
        if tool_registry:
            snap = await tool_registry.refresh(
                session,
                server_id,
                phase="after_open",
                mcp_guard=mcp_guard,
            )
            activity.emit(
                "mcp_tools_registered",
                server_id=server_id,
                phase="after_open",
                tool_count=len(snap.tools),
                tool_names=snap.tool_names,
                read_first=read_first_tool_names(snap.tool_names),
            )
        activity.emit(
            "agent_status",
            server_id=server_id,
            status="open_ok" if ok else "open_unverified",
            detail="Model opened" if ok else "Open completed with warnings",
        )
        return text
    except Exception as e:
        logger.exception("open_model failed for %s", server_id)
        activity.emit("open_failed", server_id=server_id, error=str(e))
        if evidence:
            evidence.record_open(
                server_id, ok=False, tool_name=tool, error=str(e)
            )
        if app:
            app.record_open_session(
                server_id,
                file_path=fp,
                status_text=f"Open failed: {e}",
                ok=False,
            )
        activity.emit(
            "agent_status",
            server_id=server_id,
            status="open_failed",
            detail=str(e)[:300],
        )
        return f"Open failed: {e}"
