"""Final user-facing summary from all specialist WorkResults."""

from __future__ import annotations

import json
import logging
from typing import Any

from agents import Agent, Runner

from app.services.multi_agent.model_resolver import agent_model

from app.services.multi_agent.messages import WorkResult
from app.services.multi_agent.planner import RunPlan
from app.services.multi_agent.schema import V2DemoConfig

logger = logging.getLogger(__name__)


def _summarizer_instructions() -> str:
    return """You are the summarizer for a multi-agent geotechnical workflow.

You receive the user's goal, which specialists ran, and each specialist's report.
Produce ONE clear final answer for the user:
- Answer the goal directly (comparison table, list, recommendation, etc.).
- If two or more specialists ran, include a markdown table: rows = parameters or topics,
  columns = each server_id, cells = values or 'not available'.
- Note agreements, mismatches, and gaps between products (e.g. RS2 materials vs Settle3 layers vs RSPile soils).
- State which cross-product links are conceptual only (e.g. Dips orientations vs RS2 elasticity).
- Do not invent data missing from specialist reports.
- If validation_ok is false for a specialist, mark their table cells as "unverified" and quote validation_issues.
- If mcp_evidence.failed_tools is non-empty, say which tools failed and do not treat related claims as confirmed.
- If a specialist summary claims "updated/changed" but validation_issues mention setter failure or unverified after-read, report the update as NOT confirmed.
- If orchestrator_message warns about unverified output, lead with that warning.
- Never present unverified numeric values as confirmed engineering results.
- When workflow_timeline is provided, treat it as the authoritative cross-attempt timeline.
  Use parameter_updates.baseline_value for the ORIGINAL value (before any setter), even if
  the final specialist summary says the value was already aligned.
  Use parameter_updates.updated_value or final_read_value for the value after setUnitWeight.
  Use pile_results sequence/role for before vs after pile metrics; prefer timeline over
  a single attempt's summary when they disagree.
  Quote narrative_hints when they clarify retry or baseline vs final-read confusion.
- Keep structure readable (headings or bullets)."""


async def summarize_workflow(
    *,
    goal: str,
    plan: RunPlan,
    results: list[WorkResult],
    cfg: V2DemoConfig,
    orchestrator_message: str = "",
    user_action_required: bool = False,
    workflow_timeline: dict[str, dict[str, Any]] | None = None,
) -> str:
    payload = {
        "user_goal": goal,
        "planner_reasoning": plan.reasoning,
        "selected_servers": plan.selected_servers,
        "file_paths": plan.file_paths_map(),
        "task_hints": plan.task_hints_map(),
        "orchestrator_message": orchestrator_message,
        "user_action_required": user_action_required,
        "workflow_timeline": workflow_timeline or {},
        "specialists": [
            {
                "server_id": r.server_id,
                "ok": r.ok,
                "error": r.error,
                "validation_ok": r.validation_ok,
                "validation_issues": r.validation_issues,
                "mcp_evidence": r.mcp_evidence,
                "summary": r.summary,
            }
            for r in results
        ],
    }
    summarizer_model = cfg.effective_summarizer_model
    agent = Agent(
        name="workflow-summarizer",
        instructions=_summarizer_instructions(),
        model=agent_model(summarizer_model),
    )
    user_input = (
        "Synthesize the following workflow output for the user:\n\n"
        f"{json.dumps(payload, indent=2, default=str)}"
    )
    logger.info("Summarizer running (model=%s)", cfg.effective_summarizer_model)
    try:
        result = await Runner.run(agent, input=user_input, max_turns=10)
    except TypeError:
        result = await Runner.run(agent, input=user_input)

    final = getattr(result, "final_output", None)
    if isinstance(final, str) and final.strip():
        return final.strip()
    return str(result)
