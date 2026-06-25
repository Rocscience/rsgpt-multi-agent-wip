"""Post-specialist orchestrator review: retry, warn, stop, or proceed."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.schema import OrchestratorSettings
from app.services.multi_agent.workflow_hints import goal_is_model_creation
from app.services.multi_agent.workflow_timeline import timeline_retry_notes


@dataclass
class ReviewDecision:
    proceed_to_summarize: bool
    stopped: bool
    user_action_required: bool
    message: str
    per_server: dict[str, str] = field(default_factory=dict)
    retry_servers: list[str] = field(default_factory=list)


def _should_retry(result: WorkResult, settings: OrchestratorSettings) -> bool:
    if not settings.retry_on_validation_failure:
        return False
    if result.validation_issues:
        return True
    return not result.validation_ok


def review_workflow_results(
    results: list[WorkResult],
    *,
    settings: OrchestratorSettings,
) -> ReviewDecision:
    """Rule-based orchestrator pass after validation."""
    per_server: dict[str, str] = {}
    retry: list[str] = []
    hard_failures: list[str] = []
    soft_warnings: list[str] = []

    for r in results:
        if not r.ok:
            per_server[r.server_id] = "failed"
            hard_failures.append(r.server_id)
            if _should_retry(r, settings):
                retry.append(r.server_id)
            continue
        if not r.validation_ok:
            per_server[r.server_id] = "unverified"
            soft_warnings.append(r.server_id)
            if _should_retry(r, settings):
                retry.append(r.server_id)
        else:
            per_server[r.server_id] = "verified"

    user_action = False
    stopped = False
    proceed = True
    lines: list[str] = []

    if hard_failures:
        lines.append(
            f"Specialists failed: {', '.join(hard_failures)}. "
            "Results below are not fully verified."
        )

    if soft_warnings:
        lines.append(
            f"Unverified summaries (MCP evidence mismatch): {', '.join(soft_warnings)}. "
            "The briefing will flag these; do not treat numeric tables as confirmed."
        )
        user_action = True

    if settings.stop_on_validation_failure and soft_warnings and not hard_failures:
        if not settings.retry_on_validation_failure or not retry:
            stopped = True
            proceed = False
            lines.append(
                "Workflow stopped before final merge: specialist output could not be "
                "verified against MCP tools. Re-run with clearer file paths or a narrower goal."
            )
            user_action = True

    if hard_failures and settings.stop_on_specialist_failure:
        stopped = True
        proceed = False
        lines.append("Workflow stopped due to specialist failure(s).")

    if retry:
        lines.append(
            f"Retrying once with corrective guidance: {', '.join(retry)}."
        )

    if not lines:
        lines.append("All specialists completed with MCP-backed evidence.")

    return ReviewDecision(
        proceed_to_summarize=proceed,
        stopped=stopped,
        user_action_required=user_action,
        message="\n".join(lines),
        per_server=per_server,
        retry_servers=retry,
    )


def _diagnose_retry_actions(result: WorkResult, *, goal: str = "") -> list[str]:
    """Turn validation issues + MCP evidence into concrete retry steps (not hardcoded paths)."""
    issues = result.validation_issues or []
    issue_blob = " ".join(issues).lower()
    summary = (result.summary or "").lower()
    evidence = result.mcp_evidence or {}
    success = [str(t).lower() for t in (evidence.get("successful_tools") or [])]
    failed = evidence.get("failed_tools") or []

    actions: list[str] = []

    if "no model open" in issue_blob or "manual prep" in issue_blob:
        actions.append(
            "RSPile/RS2 MCP cannot create an empty model. In the desktop app: File > New, "
            "Save As to a new file, keep the app open, then call get_model_settings (or "
            "equivalent) to confirm before configuring via BigTool."
        )
    creation = goal_is_model_creation(goal)
    if creation and ("pile result" in issue_blob or "from-scratch goal" in issue_blob):
        actions.append(
            "From-scratch results: rspile_compute → rspile_get_model_results → follow the "
            "WORKFLOW HINT it returns (registered list_graphing_options tool, then "
            "get_pile_results with graphing_options as a string array). Do not grep."
        )
    elif creation:
        actions.append(
            "From-scratch goal: use grep root paths from rspile_get_model_state / grep_tool "
            "(not menu labels). Enum setters: getter on same path first, then copy its value."
        )
    if "active_piles=[]" in issue_blob or "no files in the queue" in issue_blob:
        actions.append(
            "Model has no pile in the borehole. Before rspile_compute: configure Pile Section "
            "(e.g. Pipe D/t), Pile Type length (~20 m), place pile at borehole (0,0), apply "
            "Fx lateral load, then rspile_get_model_state until active_piles is non-empty."
        )
    elif "pile result" in issue_blob or "before update" in issue_blob or "before setunitweight" in issue_blob:
        actions.append(
            "Mandatory order: rspile_compute → get_pile_results (BEFORE numbers) → "
            "read getUnitWeight → setUnitWeight from RS2 → re-read getUnitWeight → "
            "rspile_compute → get_pile_results (AFTER numbers). "
            "Call RSPile_Results_list_graphing_options first; pass graphing_options as an array."
        )
    if "re-read" in issue_blob or (
        "getunitweight" in issue_blob and not creation
    ):
        actions.append(
            "After any setter (setUnitWeight, etc.), activate and invoke the matching "
            "getter again to confirm the updated value before summarizing."
        )
    if "setsaturatedunitweight" in issue_blob or "ui field" in issue_blob:
        actions.append(
            "RS2 gamma (getUnitWeight) must be written with RSPile setUnitWeight on the "
            "soil layer — not setSaturatedUnitWeight. Re-read getUnitWeight after the setter."
        )
    if result.server_id == "rs2-server":
        cites_gamma = bool(
            re.search(r"unit weight|gamma|ρ|rho\s*s|gravity|21\.5|kN/m", summary, re.I)
        )
        has_unit_weight_getter = any("getunitweight" in t for t in success)
        only_file_state = any("rs2_get_model_state" in t for t in success)
        if cites_gamma and only_file_state and not has_unit_weight_getter:
            actions.append(
                "Unit weight was not read from live model tools — use grep_tool to find "
                "getUnitWeight on the material's InitialConditions path, activate it, "
                "invoke the getter, and report that numeric result (not rhoS×g)."
            )
    if "incomplete" in issue_blob or any(
        p in summary
        for p in (
            "cannot proceed",
            "unable to",
            "without rs2",
            "not proceed with updating",
            "could not retrieve",
        )
    ):
        actions.append(
            "The prior attempt stopped before completing the user goal — retry the missing "
            "MCP steps (update, recompute, read-back) instead of asking the user to continue."
        )
    if failed:
        actions.append(
            f"Previous tool failures: {', '.join(str(t) for t in failed[:5])}. "
            "Discover correct tool/root paths via grep_tool before retrying guessed names."
        )
    if "hallucination" in issue_blob or "no mcp" in issue_blob:
        actions.append(
            "Call READ tools first (get_model_state, etc.) and quote only values from tool output."
        )
    if "function not found" in issue_blob:
        actions.append(
            "Use grep_tool / get_relevant_functions to discover valid function names and root paths."
        )

    # De-dupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            unique.append(a)
    return unique


def build_retry_hint(
    result: WorkResult,
    *,
    goal: str = "",
    prior_timeline: dict[str, Any] | None = None,
) -> str:
    issues = result.validation_issues or ["Output could not be verified against MCP tools."]
    evidence = result.mcp_evidence or {}
    failed = evidence.get("failed_tools") or []
    failed_line = f" Failed tools: {', '.join(failed)}." if failed else ""
    actions = _diagnose_retry_actions(result, goal=goal)
    timeline_actions = timeline_retry_notes(prior_timeline)
    for note in reversed(timeline_actions):
        actions.insert(0, note)
    action_block = ""
    if actions:
        action_block = "\nCorrective actions for this retry:\n" + "\n".join(
            f"- {a}" for a in actions
        )
    goal_line = f"\nUser goal (complete your part): {goal[:500]}\n" if goal.strip() else ""
    return (
        "ORCHESTRATOR RETRY — diagnose the failure and adjust your approach.\n"
        f"Issues: {'; '.join(issues)}.{failed_line}\n"
        "Think about WHY the step failed (missing tool call, wrong read path, skipped read-back, "
        "placeholder data treated as real) and fix that on this attempt."
        f"{action_block}"
        f"{goal_line}\n"
        "You MUST call MCP tools and base your summary only on tool output. "
        "If tools fail after one corrected attempt, report the failure honestly."
    )


def build_stopped_summary(goal: str, decision: ReviewDecision, results: list[WorkResult]) -> str:
    lines = [
        "## Workflow stopped (verification failed)",
        "",
        f"**Goal:** {goal}",
        "",
        decision.message,
        "",
        "### Specialist status",
    ]
    for r in results:
        status = "OK" if r.ok and r.validation_ok else "UNVERIFIED" if r.ok else "FAILED"
        lines.append(f"- **{r.server_id}** ({status})")
        if r.validation_issues:
            for issue in r.validation_issues:
                lines.append(f"  - {issue}")
        if r.error:
            lines.append(f"  - Error: {r.error}")
        if r.summary:
            lines.append("")
            lines.append(r.summary.strip()[:2000])
        lines.append("")
    lines.append(
        "**Next steps:** Fix model file paths, simplify the goal, or re-run with one specialist. "
        "Do not treat unverified numbers as engineering results."
    )
    return "\n".join(lines)
