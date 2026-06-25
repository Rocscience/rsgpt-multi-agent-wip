"""Map MCP list_tools() to openai-agents FunctionTool instances."""

from __future__ import annotations

import copy
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from agents.tool import FunctionTool
from agents.tool_context import ToolContext
from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession
from app.services.multi_agent.mcp_protocol import McpTool as MCPTool

from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_results import (
    format_tool_result,
    is_setter_tool_name,
    tool_result_looks_failed,
)
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.enum_tool_args import (
    normalize_enum_tool_arguments,
    parse_enum_mappings,
)

logger = logging.getLogger(__name__)

_ACTIVATE_TOOL_RE = re.compile(r"activate_function_by_name", re.I)
_ACTIVATED_AS_TOOL_RE = re.compile(r"as tool '([^']+)'")
_GETTER_TOOL_RE = re.compile(r"(^|_)get[A-Z]", re.I)
_EMPTY_ACTIVE_PILES_RE = re.compile(
    r"""['"]active_piles['"]\s*:\s*\[\s*\]""",
    re.I,
)

_RSPILE_COMPUTE_BLOCKED_MSG = (
    "Blocked rspile_compute: rspile_get_model_state shows active_piles=[] — "
    "no pile is placed in the borehole. RSPile would show 'No files in the queue'. "
    "Complete from-scratch setup first:\n"
    "1) grep/set Pile Section (pipe OD, wall thickness, depth ~20 m)\n"
    "2) grep/set Pile Type and assign section\n"
    "3) grep 'Soil Property' roots — setName/setUnitWeight/setLateralType "
    "(use Property N paths from grep, not soil-name grep alone)\n"
    "4) place pile at borehole (grep fieldpoint/setLength/setLoading on pile roots)\n"
    "5) apply lateral load Fx at pile head\n"
    "6) re-call rspile_get_model_state until active_piles is non-empty, then compute."
)

# Tools that relaunch or tear down the desktop app — orchestrator opens once; LLM must not call these.
_LIFECYCLE_TOOL_PATTERNS = (
    re.compile(r"open_.*_model$", re.I),
    re.compile(r".*_open_model$", re.I),
    re.compile(r"close_.*", re.I),
    re.compile(r".*_close_model$", re.I),
    re.compile(r"reset_server$", re.I),
    re.compile(r"cleanup_tools$", re.I),
    re.compile(r"open_.*_interpreter$", re.I),
    re.compile(r"close_.*_interpreter$", re.I),
)

_LIFECYCLE_BLOCKED_MSG = (
    "Blocked: open/close/reset tools are disabled during this workflow. "
    "The orchestrator already opened the model — use read/compute/analyze tools only."
)


def is_lifecycle_tool(tool_name: str) -> bool:
    """True for MCP tools that open, close, or reset the desktop application."""
    name = (tool_name or "").strip()
    if not name:
        return False
    return any(p.search(name) for p in _LIFECYCLE_TOOL_PATTERNS)

_EMPTY_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}


def normalize_mcp_input_schema(schema: object) -> dict[str, Any]:
    if not isinstance(schema, dict) or not schema:
        return copy.deepcopy(_EMPTY_PARAMS)
    out = copy.deepcopy(schema)
    if out.get("type") != "object":
        return out
    if "properties" not in out or not isinstance(out["properties"], dict):
        out["properties"] = {}
    if "additionalProperties" not in out:
        out["additionalProperties"] = False
    if "required" not in out:
        out["required"] = []
    return out


def _tool_description(mcp_tool: MCPTool, server_id: str) -> str:
    parts: list[str] = []
    title = None
    annotations = getattr(mcp_tool, "annotations", None)
    if annotations and getattr(annotations, "title", None):
        title = annotations.title
    elif mcp_tool.title:
        title = mcp_tool.title
    if title:
        parts.append(title)
    doc = (mcp_tool.description or "").strip()
    if doc:
        parts.append(doc)
    if not parts:
        parts.append(f"MCP tool `{mcp_tool.name}` on server `{server_id}`.")
    parts.append(f"(MCP server id: {server_id})")
    return "\n\n".join(parts)


def resolve_registered_tool_name(requested: str, available: list[str]) -> str | None:
    """Match MCP tool name; RSPile exposes activated tools with RSP_ prefix."""
    if requested in available:
        return requested
    prefixed = f"RSP_{requested}"
    if prefixed in available:
        return prefixed
    candidates = [n for n in available if requested in n or n.endswith(requested)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _is_getter_tool_name(tool_name: str) -> bool:
    return bool(_GETTER_TOOL_RE.search(tool_name))


async def _list_tool_names(
    session: ClientSession,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None,
) -> list[str]:
    if mcp_guard:
        async with mcp_guard.lock_for(server_id):
            lr = await session.list_tools()
    else:
        lr = await session.list_tools()
    return [t.name for t in lr.tools]


async def _lookup_tool_description(
    session: ClientSession,
    tool_name: str,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None,
) -> str:
    if mcp_guard:
        async with mcp_guard.lock_for(server_id):
            lr = await session.list_tools()
    else:
        lr = await session.list_tools()
    for t in lr.tools:
        if t.name == tool_name:
            return _tool_description(t, server_id)
    return ""


def _prepare_rspile_tool_args(
    server_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
    tool_description: str,
) -> dict[str, Any]:
    if server_id != "rspile-server" or not tool_args:
        return tool_args
    return normalize_enum_tool_arguments(
        tool_name,
        tool_args,
        tool_description=tool_description,
    )


def rspile_state_text_has_no_piles(state_text: str) -> bool:
    """True when model-state output reports zero piles in the borehole."""
    return bool(_EMPTY_ACTIVE_PILES_RE.search(state_text or ""))


async def _guard_rspile_compute(
    session: ClientSession,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None,
) -> str | None:
    """Block compute when no pile is in the model (prevents RSPile queue error dialog)."""
    if server_id != "rspile-server":
        return None
    try:
        if mcp_guard:
            async with mcp_guard.lock_for(server_id):
                result = await session.call_tool(
                    "rspile_get_model_state", arguments={}
                )
        else:
            result = await session.call_tool("rspile_get_model_state", arguments={})
        state_text = format_tool_result(result, tool_name="rspile_get_model_state")
    except Exception as e:
        logger.warning("Could not pre-check rspile state before compute: %s", e)
        return None
    if rspile_state_text_has_no_piles(state_text):
        return _RSPILE_COMPUTE_BLOCKED_MSG
    return None


async def _enrich_rspile_tool_output(
    session: ClientSession,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None,
    tool_name: str,
    out: str,
    tool_description: str = "",
) -> str:
    """Append dynamic workflow hints based on registered tools (no hardcoded paths)."""
    if server_id != "rspile-server":
        return out

    failed = tool_result_looks_failed(out, tool_name=tool_name)
    if failed and is_setter_tool_name(tool_name):
        lower = out.lower()
        if ("input validation" in lower or "has no attribute" in lower) and parse_enum_mappings(
            tool_description
        ):
            out += (
                "\n\n--- HINT ---\n"
                "Enum setter failed. On the same root path: activate/call the matching getter, "
                "then pass the member name or integer from that output (or from the Parameter "
                "mapping in this tool description). Do not pass UI menu labels."
            )
        return out

    if failed:
        return out

    if tool_name == "rspile_get_model_state" and rspile_state_text_has_no_piles(out):
        out += (
            "\n\n--- WORKFLOW HINT ---\n"
            "active_piles is empty — do NOT call rspile_compute yet. "
            "Configure pile section, pile type, borehole layers, place pile at borehole, "
            "apply lateral load, then re-read state until active_piles is non-empty."
        )
        return out

    if tool_name == "rspile_get_model_results" and "mounted successfully" in out.lower():
        names = await _list_tool_names(
            session, server_id=server_id, mcp_guard=mcp_guard
        )
        list_opts = sorted(n for n in names if "list_graphing" in n.lower())
        get_pile = sorted(n for n in names if "get_pile_results" in n.lower())
        if list_opts or get_pile:
            lines = [
                "--- WORKFLOW HINT ---",
                "Do not grep for get_pile_results — call these tools already in the registered list:",
            ]
            if list_opts:
                lines.append(
                    f"1) call_mcp_tool {list_opts[0]} {{}} — read graphing option name strings"
                )
            if get_pile:
                lines.append(
                    f"2) call_mcp_tool {get_pile[0]} "
                    '{{"graphing_options": ["<option from step 1>"]}}'
                )
            out += "\n\n" + "\n".join(lines)
        return out

    if tool_name.endswith("_compute") and "successfully computed" in out.lower():
        out += (
            "\n\n--- WORKFLOW HINT ---\n"
            "Compute finished. Next: rspile_get_model_results (mounts Results tools), "
            "then follow the hint it returns — list_graphing_options → get_pile_results."
        )
    return out


async def _auto_invoke_activated_getter(
    session: ClientSession,
    activate_output: str,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None,
    evidence: McpEvidenceStore | None,
    evidence_phase: str,
) -> str:
    m = _ACTIVATED_AS_TOOL_RE.search(activate_output)
    if not m:
        return activate_output
    activated = m.group(1)
    if not _is_getter_tool_name(activated):
        return activate_output
    names = await _list_tool_names(session, server_id=server_id, mcp_guard=mcp_guard)
    invoke_name = resolve_registered_tool_name(activated, names)
    if not invoke_name:
        return (
            activate_output
            + f"\n\n(GETTER '{activated}' activated but not in tool list yet — "
            f"use call_mcp_tool with tool_name '{activated}' or RSP_{activated}.)"
        )
    try:
        if mcp_guard:
            async with mcp_guard.lock_for(server_id):
                inv = await session.call_tool(invoke_name, arguments={})
        else:
            inv = await session.call_tool(invoke_name, arguments={})
        inv_text = format_tool_result(inv)
    except Exception as e:
        inv_text = f"Error auto-invoking {invoke_name}: {e}"
    if evidence:
        evidence.record_tool(
            server_id, invoke_name, inv_text, phase=evidence_phase
        )
    return activate_output + f"\n\n--- ACTIVATED GETTER RESULT ({invoke_name}) ---\n" + inv_text


def _make_on_invoke(
    session: ClientSession,
    mcp_tool_name: str,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    evidence_phase: str = "",
    auto_invoke_getters: bool = False,
) -> Callable[[ToolContext[Any], str], Awaitable[Any]]:
    async def on_invoke(_ctx: ToolContext[Any], arguments: str) -> str:
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            out = f"Invalid tool arguments JSON: {e}"
            if evidence:
                evidence.record_tool(
                    server_id, mcp_tool_name, out, phase=evidence_phase
                )
            return out
        if not isinstance(args, dict):
            out = "Tool arguments must deserialize to a JSON object."
            if evidence:
                evidence.record_tool(
                    server_id, mcp_tool_name, out, phase=evidence_phase
                )
            return out
        tool_desc = ""
        try:
            if mcp_tool_name == "rspile_compute":
                blocked = await _guard_rspile_compute(
                    session, server_id=server_id, mcp_guard=mcp_guard
                )
                if blocked:
                    if evidence:
                        evidence.record_tool(
                            server_id, mcp_tool_name, blocked, phase=evidence_phase
                        )
                    return blocked
            tool_desc = await _lookup_tool_description(
                session,
                mcp_tool_name,
                server_id=server_id,
                mcp_guard=mcp_guard,
            )
            call_args = _prepare_rspile_tool_args(
                server_id, mcp_tool_name, args, tool_desc
            )
            if mcp_guard:
                async with mcp_guard.lock_for(server_id):
                    result = await session.call_tool(mcp_tool_name, arguments=call_args)
            else:
                result = await session.call_tool(mcp_tool_name, arguments=call_args)
            out = format_tool_result(result, tool_name=mcp_tool_name)
        except Exception as e:
            logger.exception("MCP call_tool failed: %s", mcp_tool_name)
            out = f"Error calling {mcp_tool_name}: {e}"
        if auto_invoke_getters and "Successfully activated" in out:
            out = await _auto_invoke_activated_getter(
                session,
                out,
                server_id=server_id,
                mcp_guard=mcp_guard,
                evidence=evidence,
                evidence_phase=evidence_phase,
            )
        if evidence:
            evidence.record_tool(server_id, mcp_tool_name, out, phase=evidence_phase)
        out = await _enrich_rspile_tool_output(
            session,
            server_id=server_id,
            mcp_guard=mcp_guard,
            tool_name=mcp_tool_name,
            out=out,
            tool_description=tool_desc,
        )
        return out

    return on_invoke


def make_call_mcp_tool(
    session: ClientSession,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    evidence_phase: str = "",
) -> FunctionTool:
    """Proxy for dynamically registered MCP tools (e.g. RSPile BigTool setters)."""

    async def on_invoke(_ctx: ToolContext[Any], arguments: str) -> str:
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            out = f"Invalid tool arguments JSON: {e}"
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        if not isinstance(args, dict):
            out = "Arguments must be a JSON object with tool_name and optional arguments."
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        requested = str(args.get("tool_name") or "").strip()
        tool_args = args.get("arguments") or {}
        if not requested:
            out = "tool_name is required."
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        if is_lifecycle_tool(requested):
            out = _LIFECYCLE_BLOCKED_MSG
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        if not isinstance(tool_args, dict):
            out = "arguments must be a JSON object."
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        names = await _list_tool_names(session, server_id=server_id, mcp_guard=mcp_guard)
        resolved = resolve_registered_tool_name(requested, names)
        if not resolved:
            out = (
                f"Tool '{requested}' not in registered MCP tools. "
                f"Activate it first or check RSP_ prefix. Available ({len(names)}): "
                + ", ".join(names[:40])
            )
            if evidence:
                evidence.record_tool(server_id, "call_mcp_tool", out, phase=evidence_phase)
            return out
        tool_desc = ""
        try:
            tool_desc = await _lookup_tool_description(
                session,
                resolved,
                server_id=server_id,
                mcp_guard=mcp_guard,
            )
            call_args = _prepare_rspile_tool_args(
                server_id, resolved, tool_args, tool_desc
            )
            if mcp_guard:
                async with mcp_guard.lock_for(server_id):
                    result = await session.call_tool(resolved, arguments=call_args)
            else:
                result = await session.call_tool(resolved, arguments=call_args)
            out = format_tool_result(result, tool_name=resolved)
        except Exception as e:
            logger.exception("call_mcp_tool failed: %s", resolved)
            out = f"Error calling {resolved}: {e}"
        if evidence:
            evidence.record_tool(server_id, resolved, out, phase=evidence_phase)
        out = await _enrich_rspile_tool_output(
            session,
            server_id=server_id,
            mcp_guard=mcp_guard,
            tool_name=resolved,
            out=out,
            tool_description=tool_desc,
        )
        return out

    return FunctionTool(
        name="call_mcp_tool",
        description=(
            f"Call any tool currently registered on MCP server `{server_id}` by exact name. "
            "Use after RSP_activate_function_by_name for SETTER tools (setUnitWeight, etc.): "
            'pass tool_name (e.g. RSP_Soft_Clay_setUnitWeight) and arguments object '
            '(e.g. {"unit_weight": 21.5}). Getter tools are auto-invoked on activate.'
        ),
        params_json_schema={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Registered MCP tool name (try RSP_ prefix if needed).",
                },
                "arguments": {
                    "type": "object",
                    "description": "JSON object of arguments for that tool (use {} for getters).",
                    "additionalProperties": True,
                },
            },
            "required": ["tool_name"],
            "additionalProperties": False,
        },
        on_invoke_tool=on_invoke,
        strict_json_schema=False,
    )


async def mcp_tools_as_function_tools(
    session: ClientSession,
    *,
    server_id: str,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    evidence_phase: str = "",
    exclude_lifecycle_tools: bool = True,
) -> list[FunctionTool]:
    if mcp_guard:
        async with mcp_guard.lock_for(server_id):
            lr = await session.list_tools()
    else:
        lr = await session.list_tools()
    out: list[FunctionTool] = []
    for mcp_tool in lr.tools:
        if exclude_lifecycle_tools and is_lifecycle_tool(mcp_tool.name):
            continue
        params = normalize_mcp_input_schema(mcp_tool.inputSchema)
        desc = _tool_description(mcp_tool, server_id)
        is_activate = bool(_ACTIVATE_TOOL_RE.search(mcp_tool.name))
        on_invoke = _make_on_invoke(
            session,
            mcp_tool.name,
            server_id=server_id,
            mcp_guard=mcp_guard,
            evidence=evidence,
            evidence_phase=evidence_phase,
            auto_invoke_getters=is_activate,
        )
        out.append(
            FunctionTool(
                name=mcp_tool.name,
                description=desc,
                params_json_schema=params,
                on_invoke_tool=on_invoke,
                strict_json_schema=False,
            )
        )
    return out
