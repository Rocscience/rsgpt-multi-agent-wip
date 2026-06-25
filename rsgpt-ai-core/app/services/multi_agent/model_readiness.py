"""Ensure a specialist has a live model session before MCP configuration work."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.activity import ActivityLog
from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_results import format_tool_result, tool_result_looks_failed
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.mcp_tool_registry import McpToolRegistry
from pathlib import Path

from app.services.multi_agent.model_paths import normalize_path, scratch_model_path_for
from app.services.multi_agent.open_model import open_model_for_server
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.workflow_hints import goal_is_model_creation, path_is_absent

if TYPE_CHECKING:
    from app.services.multi_agent.app_context import AppContext

logger = logging.getLogger(__name__)

# MCP tools that would open software or create/open an empty model (none on RSPile today).
_EMPTY_OR_LAUNCH_TOOL_RE = re.compile(
    r"(?:^|_)(?:new|create|launch|start)_(?:empty_)?(?:model|project|file|application|software)"
    r"|open_(?:empty|blank|new)_"
    r"|(?:new|create)_file$",
    re.I,
)

_PROBE_TOOL_SUFFIXES = (
    "get_model_settings",
    "get_model_state",
    "show_active_traverse",
    "analyze_model",
)

_MANUAL_PREP_BY_DISPLAY = {
    "rspile": (
        "RSPile MCP has no new/empty-model tool. Manual prep required:\n"
        "1) In RSPile: File > New (blank model).\n"
        "2) File > Save As … to a new .rspile2 path (keep RSPile open).\n"
        "3) Then configure via MCP (rspile_get_model_settings, BigTool setters).\n"
        "If you saved a path, re-run with that .rspile2 path so the agent can open it."
    ),
    "rs2": (
        "RS2 MCP has no new/empty-model tool. Manual prep required:\n"
        "1) In RS2: File > New Project.\n"
        "2) Set Project Settings (units, analysis type) then save a .fez path.\n"
        "3) Configure geometry/materials via MCP or re-run with that .fez path."
    ),
}


def discover_empty_or_launch_tools(tool_names: list[str]) -> list[str]:
    """Return catalog tools that might open software or create/open an empty model."""
    out: list[str] = []
    for name in tool_names:
        if _EMPTY_OR_LAUNCH_TOOL_RE.search(name):
            out.append(name)
    return out


def pick_model_probe_tool(tool_names: list[str], *, preferred: str = "") -> str:
    """Pick a read-only tool that fails when no model is open."""
    if preferred and preferred in tool_names:
        return preferred
    lower_map = {n.lower(): n for n in tool_names}
    for suffix in _PROBE_TOOL_SUFFIXES:
        for lower, original in lower_map.items():
            if lower.endswith(suffix) or suffix in lower:
                return original
    return ""


def model_probe_succeeded(text: str) -> bool:
    """True when probe output indicates a model is loaded."""
    if tool_result_looks_failed(text):
        return False
    lower = (text or "").lower()
    if "no model is currently open" in lower:
        return False
    if '"status": "ok"' in lower or "'status': 'ok'" in lower:
        return True
    if "pile_state" in lower or "model_state" in lower:
        return True
    if "formatted_settings" in lower or "raw_settings" in lower:
        return True
    if "successfully opened" in lower:
        return True
    return not tool_result_looks_failed(text)


async def _call_probe_tool(
    *,
    session: ClientSession,
    server_id: str,
    tool_name: str,
    arguments: dict,
    mcp_guard: McpSessionGuard | None,
) -> str:
    if mcp_guard:
        async with mcp_guard.lock_for(server_id):
            result = await session.call_tool(tool_name, arguments=arguments)
    else:
        result = await session.call_tool(tool_name, arguments=arguments)
    return format_tool_result(result, tool_name=tool_name)


async def probe_model_open(
    *,
    session: ClientSession,
    server_id: str,
    tool_name: str,
    arguments: dict | None,
    mcp_guard: McpSessionGuard | None,
    evidence: McpEvidenceStore | None,
) -> tuple[bool, str]:
    """Call a read tool to see whether a model is already open in the desktop app."""
    if not tool_name:
        return False, "No probe tool available in MCP catalog."
    args = dict(arguments or {})
    try:
        text = await _call_probe_tool(
            session=session,
            server_id=server_id,
            tool_name=tool_name,
            arguments=args,
            mcp_guard=mcp_guard,
        )
        ok = model_probe_succeeded(text)
        if evidence:
            evidence.record_tool(
                server_id,
                tool_name,
                text,
                ok=ok,
            )
        return ok, text
    except Exception as e:
        logger.exception("model probe failed for %s", server_id)
        return False, f"Model probe failed: {e}"


def _manual_prep_message(catalog: ServerCatalog, server_id: str) -> str:
    entry = catalog.entry(server_id)
    display = (entry.display_name or server_id).lower()
    for key, msg in _MANUAL_PREP_BY_DISPLAY.items():
        if key in display or key in server_id:
            return msg
    return (
        f"{entry.display_name or server_id} MCP has no new/empty-model tool. "
        "Create and save a blank model in the desktop app, keep it open, "
        "or re-run with the saved file path."
    )


async def prepare_model_for_work(
    *,
    catalog: ServerCatalog,
    server_id: str,
    session: ClientSession,
    file_path: str,
    goal: str,
    activity: ActivityLog,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    tool_registry: McpToolRegistry | None = None,
    app: AppContext | None = None,
    force: bool = False,
) -> str:
    """
    Open a model file when a path exists; otherwise probe for an open session or
    instruct manual File > New / Save As when MCP cannot bootstrap an empty model.
    """
    fp = normalize_path(file_path)
    creation_goal = goal_is_model_creation(goal, fp)

    if path_is_absent(fp) and creation_goal:
        scratch = scratch_model_path_for(catalog, server_id)
        if scratch:
            fp = scratch
            activity.emit(
                "scratch_template_selected",
                server_id=server_id,
                scratch_path=scratch,
                exists=Path(scratch).is_file(),
            )
            if not Path(scratch).is_file():
                msg = (
                    f"Scratch template file not found: {scratch}\n\n"
                    "One-time setup: open RSPile → File > New → Save As that exact path "
                    "(blank model). Re-run the workflow; MCP will open it as the starting point."
                )
                activity.emit(
                    "model_manual_prep_required",
                    server_id=server_id,
                    creation_goal=True,
                    reason="scratch_template_missing",
                )
                if evidence:
                    evidence.record_open(server_id, ok=False, skipped=True)
                if app:
                    app.record_open_session(
                        server_id,
                        file_path=scratch,
                        status_text=msg,
                        ok=False,
                    )
                return msg

    if fp and not path_is_absent(fp):
        return await open_model_for_server(
            catalog=catalog,
            server_id=server_id,
            session=session,
            file_path=fp,
            activity=activity,
            mcp_guard=mcp_guard,
            evidence=evidence,
            tool_registry=tool_registry,
            app=app,
            force=force,
        )

    tool_names: list[str] = []
    if tool_registry:
        snap = tool_registry.latest(server_id)
        if snap:
            tool_names = snap.tool_names

    bootstrap_tools = discover_empty_or_launch_tools(tool_names)
    activity.emit(
        "model_readiness_check",
        server_id=server_id,
        creation_goal=creation_goal,
        bootstrap_tools=bootstrap_tools,
        path_absent=True,
    )

    entry = catalog.entry(server_id)
    probe_tool = pick_model_probe_tool(
        tool_names,
        preferred=(entry.state_tool or "").strip(),
    )
    probe_args = dict(entry.state_tool_arguments or {})
    if "__FILE_PATH__" in str(probe_args.values()):
        probe_args = {
            k: (fp if v == "__FILE_PATH__" else v) for k, v in probe_args.items()
        }

    for tool in bootstrap_tools:
        activity.emit(
            "model_bootstrap_attempt",
            server_id=server_id,
            tool_name=tool,
        )
        try:
            text = await _call_probe_tool(
                session=session,
                server_id=server_id,
                tool_name=tool,
                arguments={},
                mcp_guard=mcp_guard,
            )
            if not tool_result_looks_failed(text):
                open_ok, probe_text = await probe_model_open(
                    session=session,
                    server_id=server_id,
                    tool_name=probe_tool,
                    arguments=probe_args,
                    mcp_guard=mcp_guard,
                    evidence=evidence,
                )
                if open_ok:
                    if evidence:
                        evidence.record_open(
                            server_id,
                            ok=True,
                            tool_name=tool,
                            excerpt=probe_text[:500],
                        )
                    if app:
                        app.record_open_session(
                            server_id,
                            file_path="",
                            status_text=probe_text,
                            ok=True,
                        )
                    activity.emit(
                        "model_ready",
                        server_id=server_id,
                        method="bootstrap_tool",
                        tool_name=tool,
                    )
                    return (
                        f"Model session ready via {tool}.\n"
                        f"Probe ({probe_tool}): {probe_text[:800]}"
                    )
        except Exception as e:
            logger.warning("Bootstrap tool %s failed: %s", tool, e)

    open_ok, probe_text = await probe_model_open(
        session=session,
        server_id=server_id,
        tool_name=probe_tool,
        arguments=probe_args,
        mcp_guard=mcp_guard,
        evidence=evidence,
    )
    if open_ok:
        if evidence:
            evidence.record_open(
                server_id,
                ok=True,
                tool_name=probe_tool,
                excerpt=probe_text[:500],
            )
        if app:
            app.record_open_session(
                server_id,
                file_path="",
                status_text=probe_text,
                ok=True,
            )
        activity.emit(
            "model_ready",
            server_id=server_id,
            method="probe",
            tool_name=probe_tool,
        )
        return (
            "Model already open in desktop session (no file path provided).\n"
            f"Probe ({probe_tool}): {probe_text[:800]}"
        )

    manual = _manual_prep_message(catalog, server_id)
    activity.emit(
        "model_manual_prep_required",
        server_id=server_id,
        creation_goal=creation_goal,
    )
    if evidence:
        evidence.record_open(server_id, ok=False, skipped=True)
    status = (
        "No model is open and MCP cannot create one automatically.\n\n"
        f"{manual}\n\n"
        f"Probe ({probe_tool or 'none'}): {probe_text[:500]}"
    )
    if app:
        app.record_open_session(
            server_id,
            file_path="",
            status_text=status,
            ok=False,
        )
    return status
