"""Plan → connect selected MCP servers → parallel specialists → validate → summarize."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from autogen_core import SingleThreadedAgentRuntime

from collections.abc import Callable

from app.services.multi_agent.activity import ActivityEvent, ActivityLog
from app.services.multi_agent.agents.consultant import register_consultant
from app.services.multi_agent.agents.specialist import register_specialists
from app.services.multi_agent.app_context import AppContext
from app.services.multi_agent.messages import RunWorkRequest, WorkResult
from app.services.multi_agent.bootstrap import run_bootstrap
from app.services.multi_agent.device_mcp_pool import DeviceMcpPool
from app.services.multi_agent.model_paths import resolve_specialist_paths
from app.services.multi_agent.mcp_tool_registry import McpToolRegistry, read_first_tool_names
from app.services.multi_agent.mcp_session_guard import McpSessionGuard
from app.services.multi_agent.orchestrator_review import (
    build_retry_hint,
    build_stopped_summary,
    review_workflow_results,
)
from app.services.multi_agent.workflow_timeline import (
    format_verified_timeline_lead,
    specialist_result_score,
)
from app.services.multi_agent.peer_guard import PeerGuard
from app.services.multi_agent.planner import RunPlan, run_planner
from app.services.multi_agent.registry import ServerCatalog
from app.services.multi_agent.schema import V2DemoConfig, resolve_paths
from app.services.multi_agent.summarizer import summarize_workflow
logger = logging.getLogger(__name__)


def _record_specialist_attempt(
    app: AppContext,
    result: WorkResult,
    *,
    retry_attempt: int,
) -> None:
    """Persist MCP tool history for this attempt before retry clears per-attempt evidence."""
    app.timeline.record_attempt(
        result.server_id,
        attempt=retry_attempt,
        tool_records=app.evidence.tool_records(result.server_id),
        result=result,
    )
    app.activity.emit(
        "timeline_recorded",
        server_id=result.server_id,
        attempt=retry_attempt,
        tool_calls=len(app.evidence.tool_records(result.server_id)),
        validation_ok=result.validation_ok,
    )


def _fallback_summary(
    goal: str,
    plan: RunPlan,
    results: list[WorkResult],
    *,
    error: str | None = None,
    workflow_timeline: dict | None = None,
) -> str:
    """If the LLM summarizer fails, still return a usable briefing from specialist outputs."""
    lines = [
        "## Workflow briefing (fallback)",
        "",
        f"**Goal:** {goal}",
        "",
        f"**Planned specialists:** {', '.join(plan.selected_servers)}",
        "",
    ]
    if error:
        lines.extend([f"**Note:** Summarizer error: {error}", ""])
    if workflow_timeline:
        lines.append("**Cross-attempt timeline (authoritative for baseline vs updated values):**")
        lines.append("")
        for sid, tl in workflow_timeline.items():
            lines.append(f"#### {sid}")
            for hint in tl.get("narrative_hints") or []:
                lines.append(f"- {hint}")
            for pu in tl.get("parameter_updates") or []:
                if pu.get("baseline_value"):
                    lines.append(
                        f"- {pu.get('material', 'material')} unit weight: "
                        f"baseline {pu['baseline_value']} → "
                        f"{pu.get('updated_value') or pu.get('final_read_value', '?')} kN/m³"
                    )
            lines.append("")
    for r in results:
        verified = "verified" if r.validation_ok else "UNVERIFIED"
        status = "OK" if r.ok else "FAILED"
        lines.append(f"### {r.server_id} ({status}, {verified})")
        if r.validation_issues:
            lines.append("- Validation: " + "; ".join(r.validation_issues))
        if r.error:
            lines.append(f"- Error: {r.error}")
        if r.summary:
            lines.append(r.summary.strip())
        else:
            lines.append("- _(no summary)_")
        lines.append("")
    lines.append(
        "Peer timeouts or tool errors may appear above. Re-run with fewer parallel "
        "peer calls or increase peer_rpc_timeout_seconds in configs/default.yaml."
    )
    return "\n".join(lines)


async def run_orchestrated_workflow(
    *,
    pool: DeviceMcpPool,
    cfg: V2DemoConfig,
    catalog: ServerCatalog,
    goal: str,
    plan: RunPlan,
    activity: ActivityLog,
    file_path_overrides: dict[str, str] | None = None,
    user_model_file: str | None = None,
    uploaded_files: list[str] | None = None,
    tool_registry: McpToolRegistry | None = None,
    user_permission=None,
    source_channels=None,
) -> dict[str, Any]:
    """
    Execute a validated RunPlan: register only selected specialists, run in parallel, synthesize.
    """
    selected = catalog.validate_selection(plan.selected_servers)
    paths, path_meta = resolve_specialist_paths(
        catalog,
        selected,
        plan.file_paths_map(),
        goal=goal,
        uploaded_files=uploaded_files,
        user_model_file=user_model_file,
        path_overrides=file_path_overrides,
    )

    log = activity
    orch = cfg.orchestrator
    log.emit(
        "workflow_started",
        goal=goal,
        selected_servers=selected,
        file_paths=paths,
        file_path_resolution=path_meta,
        model=cfg.model,
        planner_reasoning=plan.reasoning,
    )

    from app.models.channels import SourceChannel, UserPermission

    app = AppContext(
        cfg=cfg,
        catalog=catalog,
        activity=log,
        device_id=pool.device_id,
        user_permission=user_permission or UserPermission.BASIC,
        source_channels=source_channels or [SourceChannel.ROC],
        tool_registry=tool_registry or McpToolRegistry(),
        peer_guard=PeerGuard(),
        mcp_guard=McpSessionGuard(),
        active_servers=selected,
        sessions={sid: pool.sessions[sid] for sid in selected},
    )

    runtime = SingleThreadedAgentRuntime()
    if cfg.consultant.enabled:
        await register_consultant(runtime, app)
        log.emit("consultant_ready", backend="pinecone_cohere")
    await register_specialists(runtime, app, selected)

    async def dispatch(
        server_id: str,
        *,
        task_hint: str = "",
        validation_feedback: str = "",
        retry_attempt: int = 0,
    ) -> WorkResult:
        agent_id = app.agent_ids[server_id]
        req = RunWorkRequest(
            goal=goal,
            file_path=paths[server_id],
            server_id=server_id,
            task_hint=task_hint or plan.task_hints_map().get(server_id, ""),
            validation_feedback=validation_feedback,
            retry_attempt=retry_attempt,
        )
        log.emit(
            "work_dispatched",
            server_id=server_id,
            agent_id=str(agent_id),
            file_path=paths[server_id],
            retry_attempt=retry_attempt,
        )
        result = await runtime.send_message(req, recipient=agent_id)
        if not isinstance(result, WorkResult):
            return WorkResult(
                server_id=server_id,
                summary="",
                ok=False,
                error=f"Unexpected result type: {type(result)}",
            )
        return result

    runtime.start()
    try:
        raw = await asyncio.gather(
            *[dispatch(sid) for sid in selected], return_exceptions=True
        )
    finally:
        await runtime.stop_when_idle()

    results: list[WorkResult] = []
    for sid, item in zip(selected, raw):
        if isinstance(item, BaseException):
            logger.exception("Specialist dispatch failed for %s", sid)
            log.emit("work_completed", server_id=sid, ok=False, error=str(item))
            results.append(
                WorkResult(server_id=sid, summary="", ok=False, error=str(item))
            )
        else:
            results.append(item)

    for r in results:
        _record_specialist_attempt(app, r, retry_attempt=0)

    by_id = {r.server_id: r for r in results}
    max_retries = max(0, orch.max_specialist_retries)
    for attempt in range(1, max_retries + 1):
        decision = review_workflow_results(list(by_id.values()), settings=orch)
        if not decision.retry_servers:
            break
        log.emit(
            "orchestrator_review",
            phase="retry",
            attempt=attempt,
            retry_servers=decision.retry_servers,
            message=decision.message,
            per_server=decision.per_server,
        )
        log.emit(
            "agent_status",
            server_id="orchestrator",
            status="retrying",
            detail=f"Retry {attempt}: {', '.join(decision.retry_servers)}",
        )
        runtime.start()
        try:
            retry_raw = await asyncio.gather(
                *[
                    dispatch(
                        sid,
                        validation_feedback=build_retry_hint(
                            by_id[sid],
                            goal=goal,
                            prior_timeline=app.timeline.consolidated(sid),
                        ),
                        retry_attempt=attempt,
                    )
                    for sid in decision.retry_servers
                ],
                return_exceptions=True,
            )
        finally:
            await runtime.stop_when_idle()
        for sid, item in zip(decision.retry_servers, retry_raw):
            if isinstance(item, BaseException):
                by_id[sid] = WorkResult(
                    server_id=sid, summary="", ok=False, error=str(item)
                )
            else:
                prev = by_id[sid]
                prev_tl = app.timeline.consolidated(sid)
                prev_score = specialist_result_score(prev, prev_tl)
                new_score = specialist_result_score(item, prev_tl)
                _record_specialist_attempt(app, item, retry_attempt=attempt)
                if item.validation_ok or new_score >= prev_score:
                    by_id[sid] = item
    results = [by_id[sid] for sid in selected]

    workflow_timeline = app.timeline.all_consolidated(selected)

    decision = review_workflow_results(results, settings=orch)
    log.emit(
        "orchestrator_review",
        phase="final",
        proceed=decision.proceed_to_summarize,
        stopped=decision.stopped,
        user_action_required=decision.user_action_required,
        message=decision.message,
        per_server=decision.per_server,
    )
    log.emit(
        "agent_status",
        server_id="orchestrator",
        status="stopped" if decision.stopped else "review_complete",
        detail=decision.message[:500],
    )

    if decision.stopped:
        final_summary = build_stopped_summary(goal, decision, results)
        log.emit(
            "summarization_skipped",
            reason="verification_stop",
            message=decision.message,
        )
    else:
        log.emit("summarization_started", model=cfg.effective_summarizer_model)
        try:
            final_summary = await summarize_workflow(
                goal=goal,
                plan=plan,
                results=list(results),
                cfg=cfg,
                orchestrator_message=decision.message,
                user_action_required=decision.user_action_required,
                workflow_timeline=workflow_timeline,
            )
        except Exception as e:
            logger.exception("Summarizer failed")
            log.emit("summarization_failed", error=str(e))
            final_summary = _fallback_summary(
                goal, plan, results, error=str(e), workflow_timeline=workflow_timeline
            )

    timeline_lead = format_verified_timeline_lead(workflow_timeline)
    if timeline_lead and not decision.stopped:
        final_summary = timeline_lead + final_summary
        log.emit("timeline_prepended", length=len(timeline_lead))

    if not decision.stopped:
        log.emit(
            "summarization_completed",
            length=len(final_summary),
            final_summary=final_summary,
        )

    out: dict[str, Any] = {
        "goal": goal,
        "plan": plan.model_dump(),
        "file_paths": paths,
        "specialists": {
            r.server_id: {
                "ok": r.ok,
                "summary": r.summary,
                "error": r.error,
                "validation_ok": r.validation_ok,
                "validation_issues": r.validation_issues,
                "mcp_evidence": r.mcp_evidence,
            }
            for r in results
        },
        "orchestrator_review": {
            "stopped": decision.stopped,
            "proceed": decision.proceed_to_summarize,
            "user_action_required": decision.user_action_required,
            "message": decision.message,
            "per_server": decision.per_server,
        },
        "final_summary": final_summary,
        "workflow_timeline": workflow_timeline,
        "activity": [e.to_dict() for e in log.events],
    }
    log.emit(
        "workflow_completed",
        specialist_ok=all(r.ok for r in results),
        validation_ok=all(r.validation_ok for r in results),
        final_summary=final_summary,
        had_failures=not all(r.ok and r.validation_ok for r in results),
        stopped=decision.stopped,
        user_action_required=decision.user_action_required,
    )
    out["activity"] = [e.to_dict() for e in log.events]
    return out


def _subscribe_activity(
    activity: ActivityLog,
    *,
    emit_json_events: bool = False,
    on_event: Callable[[ActivityEvent], None] | None = None,
) -> None:
    import json
    import sys

    if on_event is not None:
        activity.subscribe(on_event)
    if emit_json_events:

        def _print_evt(evt: ActivityEvent) -> None:
            sys.stdout.write(json.dumps(evt.to_dict(), default=str) + "\n")
            sys.stdout.flush()

        activity.subscribe(_print_evt)


async def run_multi_agent_workflow(
    *,
    goal: str,
    device_id: str,
    model: str | None = None,
    user_permission=None,
    source_channels=None,
    on_event=None,
) -> dict[str, Any]:
    """Production entry: plan → specialists → summarize via desktop WebSocket MCP."""
    from app.services.multi_agent.schema import load_default_config

    cfg = load_default_config()
    if model:
        cfg = cfg.model_copy(update={"model": model})

    catalog = ServerCatalog(cfg)
    activity = ActivityLog()
    if on_event:
        activity.subscribe(on_event)

    activity.emit(
        "planning_started",
        goal=goal,
        model=cfg.effective_planner_model,
        agent_role="orchestrator",
    )
    plan = await run_planner(user_goal=goal, cfg=cfg, catalog=catalog)
    activity.emit(
        "planner_completed",
        selected_servers=plan.selected_servers,
        reasoning=plan.reasoning,
        file_paths=plan.file_paths_map(),
    )

    selected = plan.selected_servers
    pool = DeviceMcpPool(device_id)
    tool_registry = McpToolRegistry()
    activity.emit("mcp_connecting", servers=selected)
    for sid in selected:
        entry = cfg.servers[sid]
        await pool.ensure_connected(sid, entry)
        activity.emit("mcp_connected", server_id=sid)
        session = pool.sessions[sid]
        snap = await tool_registry.refresh(session, sid, phase="connected")
        activity.emit(
            "mcp_tools_registered",
            server_id=sid,
            phase="connected",
            tool_count=len(snap.tools),
            tool_names=snap.tool_names,
            read_first=read_first_tool_names(snap.tool_names),
        )
        bootstrap = cfg.bootstrap_tool_calls.get(sid, [])
        if bootstrap:
            await run_bootstrap(session, bootstrap, log_label=sid)
            snap = await tool_registry.refresh(session, sid, phase="after_bootstrap")
            activity.emit(
                "mcp_tools_registered",
                server_id=sid,
                phase="after_bootstrap",
                tool_count=len(snap.tools),
                tool_names=snap.tool_names,
                read_first=read_first_tool_names(snap.tool_names),
            )

    result = await run_orchestrated_workflow(
        pool=pool,
        cfg=cfg,
        catalog=catalog,
        goal=goal,
        plan=plan,
        activity=activity,
        tool_registry=tool_registry,
        user_permission=user_permission,
        source_channels=source_channels,
    )
    return result


async def run_from_config_path(
    config_path: str,
    *,
    goal: str,
    device_id: str,
    file_path_overrides: dict[str, str] | None = None,
    user_model_file: str | None = None,
    uploaded_files: list[str] | None = None,
    emit_json_events: bool = False,
    on_event: Callable[[ActivityEvent], None] | None = None,
    server_filter: list[str] | None = None,
    mcp_pool: DeviceMcpPool | None = None,
) -> dict[str, Any]:
    import os
    from pathlib import Path

    from app.services.multi_agent.schema import load_demo_config

    cfg_path = Path(config_path).expanduser().resolve()
    cfg = resolve_paths(load_demo_config(cfg_path), cfg_path)
    for key in ("DEMO_MODEL", "PLANNER_MODEL", "SUMMARIZER_MODEL"):
        env_val = os.getenv(key)
        if not env_val:
            continue
        if key == "DEMO_MODEL":
            cfg = cfg.model_copy(update={"model": env_val})
        elif key == "PLANNER_MODEL":
            cfg = cfg.model_copy(update={"planner_model": env_val})
        elif key == "SUMMARIZER_MODEL":
            cfg = cfg.model_copy(update={"summarizer_model": env_val})

    catalog = ServerCatalog(cfg)
    activity = ActivityLog()
    _subscribe_activity(activity, emit_json_events=emit_json_events, on_event=on_event)

    activity.emit(
        "planning_started",
        goal=goal,
        model=cfg.effective_planner_model,
        agent_role="orchestrator",
    )
    plan = await run_planner(user_goal=goal, cfg=cfg, catalog=catalog)
    activity.emit(
        "planner_completed",
        selected_servers=plan.selected_servers,
        reasoning=plan.reasoning,
        file_paths=plan.file_paths_map(),
    )
    if server_filter:
        plan.selected_servers = [s for s in plan.selected_servers if s in server_filter]
        catalog.validate_selection(plan.selected_servers)

    selected = plan.selected_servers
    servers_to_connect = {sid: cfg.servers[sid] for sid in selected}

    pool = mcp_pool if mcp_pool is not None else DeviceMcpPool(device_id)
    owns_pool = mcp_pool is None
    tool_registry = McpToolRegistry()
    try:
        activity.emit("mcp_connecting", servers=selected)
        for sid in selected:
            await pool.ensure_connected(sid, servers_to_connect[sid])
            activity.emit("mcp_connected", server_id=sid)
            session = pool.sessions[sid]
            snap = await tool_registry.refresh(session, sid, phase="connected")
            activity.emit(
                "mcp_tools_registered",
                server_id=sid,
                phase="connected",
                tool_count=len(snap.tools),
                tool_names=snap.tool_names,
                read_first=read_first_tool_names(snap.tool_names),
            )
            bootstrap = cfg.bootstrap_tool_calls.get(sid, [])
            if bootstrap:
                await run_bootstrap(session, bootstrap, log_label=sid)
                snap = await tool_registry.refresh(session, sid, phase="after_bootstrap")
                activity.emit(
                    "mcp_tools_registered",
                    server_id=sid,
                    phase="after_bootstrap",
                    tool_count=len(snap.tools),
                    tool_names=snap.tool_names,
                    read_first=read_first_tool_names(snap.tool_names),
                )
        return await run_orchestrated_workflow(
            pool=pool,
            cfg=cfg,
            catalog=catalog,
            goal=goal,
            plan=plan,
            activity=activity,
            file_path_overrides=file_path_overrides,
            user_model_file=user_model_file,
            uploaded_files=uploaded_files,
            tool_registry=tool_registry,
        )
    finally:
        keep_open = cfg.orchestrator.keep_desktop_apps_open
        if owns_pool and not keep_open:
            await pool.aclose()
        elif keep_open:
            activity.emit(
                "mcp_kept_alive",
                message=(
                    "Rocscience desktop apps were left open for inspection. "
                    "Close RS2/RSPile/etc. manually when finished, or stop the UI server "
                    "to end MCP background processes."
                ),
                connected_servers=list(pool.sessions.keys()),
            )
