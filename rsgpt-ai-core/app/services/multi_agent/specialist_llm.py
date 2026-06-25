"""OpenAI Agents SDK runner inside AutoGen RoutedAgent specialists."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Sequence

from agents import Agent, Runner, RunHooks
from agents.tool import FunctionTool
from agents.tool_context import ToolContext
from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.activity import ActivityLog
from app.services.multi_agent.model_resolver import agent_model
from app.services.multi_agent.mcp_evidence import McpEvidenceStore
from app.services.multi_agent.mcp_results import tool_result_looks_failed
from app.services.multi_agent.bootstrap import run_bootstrap
from app.services.multi_agent.mcp_function_tools import make_call_mcp_tool, mcp_tools_as_function_tools
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.mcp_tool_registry import McpToolRegistry
from app.services.multi_agent.schema import BootstrapCall

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int) -> str:
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 3] + "..."


class ActivityRunHooks(RunHooks):
    """Emit activity events for future UI (tool + LLM turns)."""

    def __init__(
        self,
        *,
        server_id: str,
        agent_type: str,
        activity: ActivityLog,
        phase: str,
    ) -> None:
        self._server_id = server_id
        self._agent_type = agent_type
        self._activity = activity
        self._phase = phase
        self._llm_turn = 0

    def _base(self) -> dict[str, str]:
        return {
            "server_id": self._server_id,
            "agent_type": self._agent_type,
            "phase": self._phase,
        }

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:  # type: ignore[no-untyped-def]
        self._llm_turn += 1
        self._activity.emit(
            "llm_turn_start",
            **self._base(),
            turn=self._llm_turn,
            input_item_count=len(input_items) if input_items is not None else 0,
        )

    async def on_llm_end(self, context, agent, response) -> None:  # type: ignore[no-untyped-def]
        usage = getattr(response, "usage", None)
        self._activity.emit(
            "llm_turn_end",
            **self._base(),
            turn=self._llm_turn,
            usage=str(usage) if usage is not None else None,
        )

    async def on_tool_start(self, context, agent, tool) -> None:  # type: ignore[no-untyped-def]
        if isinstance(context, ToolContext):
            self._activity.emit(
                "tool_call_start",
                **self._base(),
                tool_name=context.tool_name,
            )
        else:
            name = getattr(tool, "name", "?")
            self._activity.emit("tool_call_start", **self._base(), tool_name=name)

    async def on_tool_end(self, context, agent, tool, result: str) -> None:  # type: ignore[no-untyped-def]
        name = context.tool_name if isinstance(context, ToolContext) else getattr(tool, "name", "?")
        ok = not tool_result_looks_failed(result or "")
        self._activity.emit(
            "tool_call_end",
            **self._base(),
            tool_name=name,
            ok=ok,
        )
        self._activity.emit(
            "agent_status",
            **self._base(),
            status="tool_ok" if ok else "tool_failed",
            tool_name=name,
            detail=name if ok else f"{name} failed",
        )


async def run_specialist_llm(
    *,
    server_id: str,
    agent_type: str,
    session: ClientSession,
    model: str,
    user_prompt: str,
    bootstrap_calls: Sequence[BootstrapCall | dict],
    extra_tools: Sequence[FunctionTool],
    activity: ActivityLog,
    phase: str,
    mcp_guard: McpSessionGuard | None = None,
    evidence: McpEvidenceStore | None = None,
    tool_registry: McpToolRegistry | None = None,
    state_tool_name: str = "",
    agent_playbook: str = "",
    max_turns: int = 35,
    allow_peer_tools: bool = True,
    peer_targets: list[str] | None = None,
    consultant_enabled: bool = False,
) -> str:
    await run_bootstrap(
        session, bootstrap_calls, log_label=server_id, mcp_guard=mcp_guard
    )
    mcp_tools = await mcp_tools_as_function_tools(
        session,
        server_id=server_id,
        mcp_guard=mcp_guard,
        evidence=evidence,
        evidence_phase=phase,
        exclude_lifecycle_tools=True,
    )
    if tool_registry:
        snap = await tool_registry.refresh(
            session,
            server_id,
            phase=f"before_llm_{phase}",
            mcp_guard=mcp_guard,
        )
        activity.emit(
            "mcp_tools_registered",
            server_id=server_id,
            phase=f"before_llm_{phase}",
            tool_count=len(snap.tools),
            tool_names=snap.tool_names,
            read_first=tool_registry.read_first_tools(server_id),
        )
    tools: list[FunctionTool] = list(mcp_tools)
    if server_id == "rspile-server":
        tools.append(
            make_call_mcp_tool(
                session,
                server_id=server_id,
                mcp_guard=mcp_guard,
                evidence=evidence,
                evidence_phase=phase,
            )
        )
    if allow_peer_tools:
        tools.extend(extra_tools)

    names = [t.name for t in tools]
    tool_guidance = ""
    if tool_registry:
        state_hints = [state_tool_name] if state_tool_name else None
        tool_guidance = tool_registry.guidance_for(
            server_id,
            state_tool_names=state_hints,
            agent_playbook=agent_playbook,
        )
    else:
        tool_guidance = (
            "REGISTERED MCP TOOLS (runtime): "
            + (", ".join(names) if names else "(none)")
        )

    peer_hint = ""
    if allow_peer_tools and extra_tools and peer_targets:
        peer_hint = (
            "\nYou may call ask_agent_peer(target_server_id, question) to ask other "
            f"specialists blocking questions. Active peers: {', '.join(peer_targets)}.\n"
            "Ask one peer at a time; wait for the answer before continuing.\n"
            "Cross-product rules:\n"
            "- Read your local model with MCP tools first, then ask peers only for data you cannot obtain.\n"
            "- When comparing products, ask peers for specific parameters (names, E, nu, gamma, Cc, cv, pile length, dip/dip direction).\n"
            "- Report mismatches and 'not available' honestly; do not invent values from peer answers.\n"
            "- If this is a multi-program goal, end with a short bullet list of parameters you supply for cross-checking.\n"
        )
    consultant_hint = ""
    if consultant_enabled:
        consultant_hint = (
            "\nWhen unsure about Rocscience workflow order, menu paths, creating a model "
            "from scratch, or which MCP tool sequence to use, call "
            "ask_software_consultant(question, software) for guidance from the knowledge base. "
            "Do NOT use the consultant for live model values — use MCP tools or ask_agent_peer.\n"
        )

    instructions = (
        f'You are the dedicated AutoGen specialist for MCP server "{server_id}" '
        f'(agent type "{agent_type}").\n'
        "Use only the tools provided. Each MCP tool talks to your Rocscience desktop app.\n"
        "SESSION: The orchestrator already opened the model. Open/close/reset MCP tools are "
        "NOT available — never try to reopen or close the application.\n"
        f"{tool_guidance}\n"
        f"{peer_hint}"
        f"{consultant_hint}\n"
        "Complete the task with minimal tool calls, then give a clear summary.\n"
        "CRITICAL: Only report numbers and model facts that appear in MCP tool output. "
        "If a tool fails or returns empty, say so — do not guess layers, materials, or results.\n"
        "After RSP_activate_function_by_name succeeds, you MUST call the new RSP_* tool in the "
        "registered list — activation alone is not a read.\n"
        + (
            "RSPile SETTERS: always use call_mcp_tool with the required arguments "
            "(e.g. unit_weight for setUnitWeight). Void/empty setter return is OK — "
            "re-read the getter immediately to confirm the new value.\n"
            "RSPile ENUM SETTERS: activate matching getter on the same root path first; "
            "pass the member name or integer from getter output or the Parameter mapping "
            "in the setter tool description — not UI menu text.\n"
            "RSPile FROM-SCRATCH: discover paths via grep/state; after rspile_get_model_results "
            "follow the WORKFLOW HINT (registered Results tools — do not grep get_pile_results).\n"
            "RSPile BEFORE/AFTER: compute → get_pile_results (record numbers) → update param → "
            "re-read getter → compute again → get_pile_results again. Include both in summary.\n"
            if server_id == "rspile-server"
            else (
                "RS2: use rs2_get_model_state and other READ tools first. "
                "If a parameter is missing or placeholder, use grep_tool → activate_function_by_name → "
                "invoke the activated getter — do not guess root paths or infer from rhoS×g.\n"
                if server_id == "rs2-server"
                else ""
            )
        )
    )

    agent = Agent(
        name=f"mcp-{server_id}",
        instructions=instructions,
        tools=tools,
        model=agent_model(model),
    )

    hooks = ActivityRunHooks(
        server_id=server_id,
        agent_type=agent_type,
        activity=activity,
        phase=phase,
    )
    activity.emit("work_llm_start", server_id=server_id, agent_type=agent_type, phase=phase)

    try:
        result = await Runner.run(agent, input=user_prompt, max_turns=max_turns, hooks=hooks)
    except TypeError:
        try:
            result = await Runner.run(agent, input=user_prompt, hooks=hooks)
        except TypeError:
            result = await Runner.run(agent, input=user_prompt, max_turns=max_turns)

    final = getattr(result, "final_output", None)
    out = final if isinstance(final, str) and final.strip() else str(result)
    activity.emit(
        "work_llm_end",
        server_id=server_id,
        agent_type=agent_type,
        phase=phase,
        output_excerpt=_truncate(out, 400),
    )
    return out
