"""Generic MCP specialist — one AutoGen agent class for every registered server."""

from __future__ import annotations

import asyncio
import logging
import uuid

from autogen_core import AgentId, MessageContext, RoutedAgent, rpc
from app.services.multi_agent.mcp_protocol import McpSessionProtocol as ClientSession

from app.services.multi_agent.app_context import AppContext
from app.services.multi_agent.messages import (
    ConsultantQuery,
    ConsultantResponse,
    PeerQuery,
    PeerResponse,
    RunWorkRequest,
    WorkResult,
)
from app.services.multi_agent.bootstrap import run_bootstrap
from app.services.multi_agent.consultant_tools import make_ask_software_consultant_tool
from app.services.multi_agent.model_paths import normalize_path, scratch_model_path_for
from app.services.multi_agent.model_readiness import prepare_model_for_work
from app.services.multi_agent.open_model import open_model_for_server
from app.services.multi_agent.workflow_hints import (
    goal_is_model_creation,
    goal_needs_before_after_comparison,
    path_is_absent,
)
from app.services.multi_agent.peer_guard import MAX_PEER_DEPTH
from app.services.multi_agent.peer_tools import make_ask_agent_peer_tool
from app.services.multi_agent.rs2_live_enrichment import (
    prefetch_rs2_unit_weights_if_missing,
    question_asks_unit_weight,
)
from app.services.multi_agent.specialist_llm import run_specialist_llm
from app.services.multi_agent.validator import apply_validation_to_result

logger = logging.getLogger(__name__)

_AGENT_KEY = "default"


class MCPSpecialistAgent(RoutedAgent):
    def __init__(
        self,
        app: AppContext,
        server_id: str,
        session: ClientSession,
    ) -> None:
        super().__init__(f"MCP specialist ({server_id})")
        self._app = app
        self._server_id = server_id
        self._session = session
        self._agent_type = app.agent_type_for(server_id)
        self._file_path: str = ""
        self._open_status: str = ""

    @property
    def server_id(self) -> str:
        return self._server_id

    def _state_tool_name(self) -> str:
        return (self._app.catalog.entry(self._server_id).state_tool or "").strip()

    def _agent_playbook(self) -> str:
        return (self._app.catalog.entry(self._server_id).agent_playbook or "").strip()

    async def _maybe_prefetch_rs2_unit_weights(self, *, phase: str) -> str:
        """Deterministic BigTool fallback when get_model_state lacks unit weight."""
        if self._server_id != "rs2-server":
            return ""
        try:
            block = await prefetch_rs2_unit_weights_if_missing(
                self._session,
                evidence=self._app.evidence,
                server_id=self._server_id,
                phase=phase,
            )
            if block:
                self._app.activity.emit(
                    "rs2_unit_weight_prefetch",
                    server_id=self._server_id,
                    phase=phase,
                    excerpt=block[:400],
                )
            return block
        except Exception:
            logger.exception("RS2 unit weight prefetch failed")
            return ""

    def _llm_max_turns(self, phase: str) -> int:
        if self._server_id == "rspile-server":
            return 40 if phase == "main_work" else 28
        return 35 if phase == "main_work" else 18

    async def request_peer(self, to_server: str, question: str) -> str:
        guard = self._app.peer_guard

        if to_server not in self._app.agent_ids:
            return f"Unknown or inactive peer: {to_server}"

        async def _send() -> str:
            return await self._execute_outbound_peer_rpc(to_server, question)

        if guard.should_queue_outbound(self._server_id):
            depth = guard.outbound_queue_depth(self._server_id)
            self._app.activity.emit(
                "peer_query_queued",
                from_server=self._server_id,
                to_server=to_server,
                question=question,
                queue_position=depth + 1,
            )
            job = guard.enqueue_outbound(
                self._server_id,
                to_server=to_server,
                question=question,
                run=_send,
            )
            return await job

        return await guard.run_outbound(self._server_id, _send)

    async def _execute_outbound_peer_rpc(self, to_server: str, question: str) -> str:
        request_id = str(uuid.uuid4())
        recipient = self._app.agent_ids[to_server]
        self._app.activity.emit(
            "peer_query_sent",
            from_server=self._server_id,
            to_server=to_server,
            request_id=request_id,
            question=question,
        )
        try:
            coro = self.send_message(
                PeerQuery(
                    question=question,
                    from_server=self._server_id,
                    to_server=to_server,
                    request_id=request_id,
                    depth=0,
                ),
                recipient=recipient,
            )
            resp = await asyncio.wait_for(
                coro,
                timeout=self._app.cfg.peer_rpc_timeout_seconds,
            )
        except TimeoutError:
            self._app.activity.emit(
                "peer_query_failed",
                from_server=self._server_id,
                to_server=to_server,
                request_id=request_id,
                question=question,
                error="timeout",
            )
            return (
                f"Peer query timed out after {self._app.cfg.peer_rpc_timeout_seconds}s"
            )
        except Exception as e:
            self._app.activity.emit(
                "peer_query_failed",
                from_server=self._server_id,
                to_server=to_server,
                request_id=request_id,
                question=question,
                error=str(e),
            )
            return f"Peer query failed: {e}"

        if not isinstance(resp, PeerResponse):
            return f"Unexpected peer response type: {type(resp)}"
        if not resp.ok:
            return resp.answer

        self._app.activity.emit(
            "peer_response_received",
            from_server=to_server,
            to_server=self._server_id,
            request_id=request_id,
            answer_excerpt=(resp.answer or "")[:800],
        )
        return resp.answer

    async def request_consultant(self, question: str, *, software: str = "") -> str:
        agent_id = self._app.consultant_agent_id
        if agent_id is None:
            return (
                "Software consultant is disabled. Enable consultant in configs/default.yaml."
            )
        request_id = str(uuid.uuid4())
        self._app.activity.emit(
            "consultant_query_sent",
            from_server=self._server_id,
            request_id=request_id,
            question=question,
            software=software,
        )
        try:
            coro = self.send_message(
                ConsultantQuery(
                    question=question,
                    from_server=self._server_id,
                    request_id=request_id,
                    software=software,
                ),
                recipient=agent_id,
            )
            resp = await asyncio.wait_for(
                coro,
                timeout=self._app.cfg.peer_rpc_timeout_seconds,
            )
        except TimeoutError:
            self._app.activity.emit(
                "consultant_query_failed",
                from_server=self._server_id,
                request_id=request_id,
                question=question,
                error="timeout",
            )
            return (
                f"Consultant query timed out after "
                f"{self._app.cfg.peer_rpc_timeout_seconds}s"
            )
        except Exception as e:
            self._app.activity.emit(
                "consultant_query_failed",
                from_server=self._server_id,
                request_id=request_id,
                question=question,
                error=str(e),
            )
            return f"Consultant query failed: {e}"

        if not isinstance(resp, ConsultantResponse):
            return f"Unexpected consultant response type: {type(resp)}"
        if not resp.ok:
            return resp.answer

        self._app.activity.emit(
            "consultant_response_received",
            from_server="software-consultant",
            to_server=self._server_id,
            request_id=request_id,
            answer_excerpt=(resp.answer or "")[:800],
            sources=resp.sources[:5],
        )
        return resp.answer

    @rpc
    async def handle_peer_query(
        self,
        message: PeerQuery,
        ctx: MessageContext,
    ) -> PeerResponse:
        guard = self._app.peer_guard
        if message.depth > MAX_PEER_DEPTH:
            return PeerResponse(
                answer="Peer depth limit exceeded.",
                request_id=message.request_id,
                from_server=self._server_id,
                ok=False,
            )

        def _on_inbound_wait() -> None:
            self._app.activity.emit(
                "peer_inbound_queued",
                from_server=message.from_server,
                to_server=self._server_id,
                request_id=message.request_id,
                question=message.question,
            )

        return await guard.run_inbound_exclusive(
            self._server_id,
            lambda: self._answer_peer_query(message),
            on_wait=_on_inbound_wait,
        )

    async def _ensure_model_open_for_peer(self) -> None:
        """Peer can arrive before main-work open finishes; open once if needed."""
        fp = (self._file_path or "").strip()
        if path_is_absent(fp):
            return
        if self._app.open_is_ok(self._server_id, fp):
            if not self._open_status:
                self._open_status = self._app.cached_open_status(self._server_id) or ""
            return
        self._open_status = await open_model_for_server(
            catalog=self._app.catalog,
            server_id=self._server_id,
            session=self._session,
            file_path=fp,
            activity=self._app.activity,
            mcp_guard=self._app.mcp_guard,
            evidence=self._app.evidence,
            tool_registry=self._app.tool_registry,
            app=self._app,
        )

    async def _answer_peer_query(self, message: PeerQuery) -> PeerResponse:
        self._app.activity.emit(
            "peer_query_received",
            from_server=message.from_server,
            to_server=self._server_id,
            request_id=message.request_id,
            question=message.question,
        )
        await self._ensure_model_open_for_peer()
        prefetch_block = ""
        if self._server_id == "rs2-server" and question_asks_unit_weight(message.question):
            prefetch_block = await self._maybe_prefetch_rs2_unit_weights(phase="peer_prefetch")
        try:
            path_block = (
                f"Model file path (use exactly for open/analyze tools):\n{self._file_path or 'n/a'}\n\n"
            )
            prompt = (
                f"Peer specialist ({message.from_server}) asks:\n{message.question}\n\n"
                f"{path_block}"
                f"{prefetch_block}"
                f"Model open result:\n{self._open_status or '(not opened yet)'}\n\n"
                f"The model is ALREADY OPEN for this workflow — do not call open/close tools.\n\n"
                f"{self._app.tool_registry.guidance_for(self._server_id, state_tool_names=[self._state_tool_name()] or None, agent_playbook=self._agent_playbook())}\n\n"
                "Answer using MCP tools on YOUR model only. Be concise. "
                "For Settle3 use analyze_model with model_file_path set to the path above. "
                "Do not ask other peers — this is a direct answer turn."
            )
            answer = await run_specialist_llm(
                server_id=self._server_id,
                agent_type=self._agent_type,
                session=self._session,
                model=self._app.cfg.model,
                user_prompt=prompt,
                bootstrap_calls=self._app.bootstrap_for(self._server_id),
                extra_tools=[],
                activity=self._app.activity,
                phase="peer_answer",
                mcp_guard=self._app.mcp_guard,
                evidence=self._app.evidence,
                tool_registry=self._app.tool_registry,
                state_tool_name=self._state_tool_name(),
                agent_playbook=self._agent_playbook(),
                max_turns=self._llm_max_turns("peer_answer"),
                allow_peer_tools=False,
                peer_targets=[],
            )
        except Exception as e:
            logger.exception("Peer answer failed for %s", self._server_id)
            answer = f"Could not answer peer query: {e}"

        self._app.activity.emit(
            "peer_response_sent",
            from_server=self._server_id,
            to_server=message.from_server,
            request_id=message.request_id,
            answer_excerpt=(answer or "")[:800],
        )
        return PeerResponse(
            answer=answer,
            request_id=message.request_id,
            from_server=self._server_id,
            ok=True,
        )

    @rpc
    async def handle_run_work(
        self,
        message: RunWorkRequest,
        ctx: MessageContext,
    ) -> WorkResult:
        self._file_path = (message.file_path or "").strip()
        self._app.activity.emit(
            "work_started",
            server_id=self._server_id,
            agent_type=self._agent_type,
            file_path=self._file_path,
            goal_excerpt=message.goal[:300],
        )

        guard = self._app.mcp_guard
        await run_bootstrap(
            self._session,
            self._app.bootstrap_for(self._server_id),
            log_label=self._server_id,
            mcp_guard=guard,
        )
        open_failed_before = (
            message.retry_attempt > 0
            and not self._app.open_is_ok(self._server_id, self._file_path)
        )
        if self._app.open_is_ok(self._server_id, self._file_path) and not open_failed_before:
            self._open_status = (
                self._app.cached_open_status(self._server_id)
                or self._open_status
                or "Model already open for this workflow."
            )
            self._app.activity.emit(
                "open_skipped",
                server_id=self._server_id,
                reason="already_open",
                file_path=self._file_path,
                retry_attempt=message.retry_attempt,
            )
        else:
            self._open_status = await prepare_model_for_work(
                catalog=self._app.catalog,
                server_id=self._server_id,
                session=self._session,
                file_path=self._file_path,
                goal=message.goal,
                activity=self._app.activity,
                mcp_guard=guard,
                evidence=self._app.evidence,
                tool_registry=self._app.tool_registry,
                app=self._app,
                force=open_failed_before,
            )
        self._app.open_status_by_server[self._server_id] = self._open_status

        prefetch_block = await self._maybe_prefetch_rs2_unit_weights(phase="prefetch")

        peer_targets = self._app.peer_targets_for(self._server_id)
        extra: list = []
        if self._app.consultant_agent_id is not None:
            extra.append(make_ask_software_consultant_tool(self))
        if peer_targets:
            extra.append(make_ask_agent_peer_tool(self, allowed_targets=peer_targets))

        hint = (message.task_hint or "").strip()
        feedback = (message.validation_feedback or "").strip()
        task_block = f"\nFocus for this specialist:\n{hint}\n" if hint else ""
        if feedback:
            task_block += f"\n{feedback}\n"
        if message.retry_attempt > 0:
            self._app.evidence.clear_server(self._server_id)
            self._app.activity.emit(
                "specialist_retry",
                server_id=self._server_id,
                attempt=message.retry_attempt,
                evidence_reset=True,
            )
            if goal_needs_before_after_comparison(message.goal):
                task_block += (
                    "\nThis is a RETRY attempt — prior MCP tool evidence for this server was "
                    "cleared. Follow the corrective actions using only tools you call now. "
                    "If a parameter already matches the peer value, still complete two pile "
                    "result reads (before/after compute) and report honestly; do not skip "
                    "get_pile_results because no setter is needed.\n"
                )
            else:
                task_block += (
                    "\nThis is a RETRY attempt — prior MCP tool evidence for this server was "
                    "cleared. Follow the corrective actions using only tools you call now.\n"
                )
        peer_block = ""
        if peer_targets:
            peer_block = (
                "\nOther active specialists (use ask_agent_peer with target_server_id):\n"
                + ", ".join(peer_targets)
                + "\nAsk them only when you need data from their open model.\n"
            )
        consultant_block = ""
        if self._app.consultant_agent_id is not None:
            consultant_block = (
                "\nIf you are unsure about workflow order, menu paths, creating a model from "
                "scratch, or which MCP steps to run next, call ask_software_consultant "
                "before guessing. Use it for HOW-TO guidance — not for live model values.\n"
            )

        cross_product_block = ""
        if self._server_id == "rspile-server" and goal_needs_before_after_comparison(
            message.goal
        ):
            cross_product_block = (
                "MANDATORY WORKFLOW (cross-product before/after):\n"
                "1) rspile_compute → rspile_get_model_results → "
                "RSPile_Results_list_graphing_options → RSPile_Results_get_pile_results "
                "(record numeric max/min as BEFORE).\n"
                "2) getUnitWeight on soil layer → setUnitWeight from RS2 → getUnitWeight read-back.\n"
                "3) rspile_compute → get_pile_results again (record AFTER numbers).\n"
                "Do not call setUnitWeight before the first get_pile_results. "
                "Do not claim 'already aligned' without both pile result reads.\n\n"
            )

        model_open_block = ""
        scratch = scratch_model_path_for(self._app.catalog, self._server_id)
        using_scratch = (
            scratch
            and normalize_path(message.file_path or "") == scratch
            and goal_is_model_creation(message.goal)
        )
        if using_scratch:
            model_open_block = (
                "Starting from the configured BLANK scratch template (not a tutorial example). "
                "Configure project settings, soils, pile, loads via MCP, then compute, read pile "
                "results (follow WORKFLOW HINT after rspile_get_model_results), and rspile_save_model. "
                "Discover paths via grep/state — not menu words like borehole. "
                "Enum setters: getter first on same path, then copy its value. "
                "Do not call open/close again.\n"
            )
        elif path_is_absent(message.file_path) or goal_is_model_creation(message.goal):
            if "model already open" in (self._open_status or "").lower():
                model_open_block = (
                    "Model session is open in the desktop app (verified by MCP probe). "
                    "Do not call open/close tools.\n"
                )
            elif "no model is open" in (self._open_status or "").lower():
                model_open_block = (
                    "No model is open yet. Follow the manual prep steps in the open result "
                    "below, then call rspile_get_model_settings (or equivalent) to confirm "
                    "before configuring. Do not invent model values.\n"
                )
            else:
                model_open_block = (
                    "No example file path — create/configure in the open session per the "
                    "open result below. Do not call open/close with a fake path.\n"
                )
        else:
            model_open_block = (
                "The model is ALREADY OPEN for this workflow. Do not attempt to open or close it.\n"
            )

        prompt = (
            f"User goal:\n{message.goal}\n"
            f"{task_block}\n"
            f"Model file path:\n{message.file_path}\n\n"
            f"{cross_product_block}"
            f"{prefetch_block}"
            f"Model open result:\n{self._open_status}\n"
            f"{peer_block}"
            f"{consultant_block}\n"
            f"{model_open_block}"
            "Complete your part of the goal using MCP tools, then summarize."
        )
        try:
            summary = await run_specialist_llm(
                server_id=self._server_id,
                agent_type=self._agent_type,
                session=self._session,
                model=self._app.cfg.model,
                user_prompt=prompt,
                bootstrap_calls=self._app.bootstrap_for(self._server_id),
                extra_tools=extra,
                activity=self._app.activity,
                phase="main_work",
                mcp_guard=self._app.mcp_guard,
                evidence=self._app.evidence,
                tool_registry=self._app.tool_registry,
                state_tool_name=self._state_tool_name(),
                agent_playbook=self._agent_playbook(),
                max_turns=self._llm_max_turns("main_work"),
                allow_peer_tools=bool(peer_targets or self._app.consultant_agent_id),
                peer_targets=peer_targets,
                consultant_enabled=self._app.consultant_agent_id is not None,
            )
            result = WorkResult(server_id=self._server_id, summary=summary, ok=True)
            if self._app.cfg.orchestrator.validate_specialist_outputs:
                result = apply_validation_to_result(
                    result,
                    open_status=self._open_status,
                    file_path=self._file_path,
                    evidence=self._app.evidence,
                    settings=self._app.cfg.orchestrator,
                    goal=message.goal,
                )
            self._app.activity.emit(
                "validation_completed",
                server_id=self._server_id,
                validation_ok=result.validation_ok,
                issues=result.validation_issues,
                mcp_evidence=result.mcp_evidence,
            )
            self._app.activity.emit(
                "agent_status",
                server_id=self._server_id,
                status="verified" if result.validation_ok else "unverified",
                detail="; ".join(result.validation_issues)[:400]
                if result.validation_issues
                else "MCP evidence matches summary",
            )
            self._app.activity.emit(
                "work_completed",
                server_id=self._server_id,
                agent_type=self._agent_type,
                ok=result.ok,
                validation_ok=result.validation_ok,
                summary_excerpt=(summary or "")[:1200],
            )
            return result
        except Exception as e:
            logger.exception("Work failed for %s", self._server_id)
            self._app.activity.emit(
                "work_completed",
                server_id=self._server_id,
                agent_type=self._agent_type,
                ok=False,
                error=str(e),
                summary_excerpt=str(e)[:400],
            )
            return WorkResult(
                server_id=self._server_id,
                summary="",
                ok=False,
                error=str(e),
            )


async def register_specialists(
    runtime,
    app: AppContext,
    server_ids: list[str],
) -> dict[str, AgentId]:
    ids: dict[str, AgentId] = {}
    for server_id in server_ids:
        session = app.sessions[server_id]
        agent_type = app.agent_type_for(server_id)
        agent_id = AgentId(type=agent_type, key=_AGENT_KEY)
        agent = MCPSpecialistAgent(app, server_id, session)
        await agent.register_instance(runtime, agent_id)
        ids[server_id] = agent_id
        app.activity.emit(
            "agent_registered",
            server_id=server_id,
            agent_type=agent_type,
            agent_id=str(agent_id),
        )
    app.agent_ids = ids
    return ids
