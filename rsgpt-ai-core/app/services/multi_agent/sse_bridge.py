"""Map ActivityLog events to production SSE events for the frontend."""

from __future__ import annotations

import time
from typing import Any

import uuid

from app.models.agent import (
    AgentPlanningEvent,
    AgentThinkingEvent,
    AgentTransitionEvent,
    TaskProgressEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionFailedEvent,
    ToolExecutionStartedEvent,
    WorkflowStartedEvent,
    WorkflowStatus,
    WorkflowStatusChangedEvent,
)
from app.services.multi_agent.activity import ActivityEvent


def _display_name(server_id: str) -> str:
    """Fallback label when config did not seed a display name for this server."""
    return server_id.replace("-server", "").upper()


class MultiAgentSSEBridge:
    """Convert demo v2 activity events into FE-compatible SSE payloads."""

    def __init__(self) -> None:
        self._sequence = 0
        self._server_display: dict[str, str] = {}

    def set_server_display(self, server_id: str, name: str) -> None:
        self._server_display[server_id] = name

    def _agent_name(self, server_id: str | None) -> str:
        if not server_id:
            return "Orchestrator"
        return self._server_display.get(server_id) or _display_name(server_id)

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    def map_event(self, evt: ActivityEvent) -> list[tuple[str, dict[str, Any]]]:
        kind = evt.kind
        p = evt.payload
        out: list[tuple[str, dict[str, Any]]] = []

        if kind == "planning_started":
            out.append(
                (
                    "agent.workflow.status_changed",
                    WorkflowStatusChangedEvent(
                        sequence_number=self._next_seq(),
                        status=WorkflowStatus.PLANNING,
                        agent_name="Orchestrator",
                    ).model_dump(),
                )
            )
        elif kind == "planner_completed":
            plan_text = p.get("reasoning") or ""
            selected = p.get("selected_servers") or []
            if selected:
                plan_text = (
                    f"Selected specialists: {', '.join(_display_name(s) for s in selected)}\n\n"
                    + plan_text
                )
            tasks = [
                {
                    "id": i + 1,
                    "description": f"{_display_name(s)} specialist",
                    "status": "pending",
                }
                for i, s in enumerate(selected)
            ]
            out.append(
                (
                    "agent.planning",
                    AgentPlanningEvent(
                        sequence_number=self._next_seq(),
                        plan={
                            "goal": plan_text,
                            "tasks": tasks,
                            "notes": plan_text,
                        },
                    ).model_dump(),
                )
            )
        elif kind == "work_dispatched":
            sid = p.get("server_id", "")
            out.append(
                (
                    "agent.workflow.status_changed",
                    WorkflowStatusChangedEvent(
                        sequence_number=self._next_seq(),
                        status=WorkflowStatus.EXECUTING,
                        agent_name=self._agent_name(sid),
                    ).model_dump(),
                )
            )
        elif kind == "work_started":
            sid = p.get("server_id", "")
            out.append(
                (
                    "agent.thinking",
                    AgentThinkingEvent(
                        sequence_number=self._next_seq(),
                        agent_name=self._agent_name(sid),
                        thinking_text=f"Starting work on {self._agent_name(sid)}…",
                        is_complete=False,
                    ).model_dump(),
                )
            )
        elif kind == "tool_call_start":
            sid = p.get("server_id", "")
            tool = p.get("tool_name", "tool")
            tc_id = str(p.get("tool_call_id") or uuid.uuid4())
            out.append(
                (
                    "agent.tool_execution.started",
                    ToolExecutionStartedEvent(
                        sequence_number=self._next_seq(),
                        tool_call_id=tc_id,
                        tool_name=tool,
                        tool_args=p.get("arguments") or {},
                    ).model_dump()
                    | {"agent_name": self._agent_name(sid)},
                )
            )
        elif kind == "tool_call_end":
            sid = p.get("server_id", "")
            tool = p.get("tool_name", "tool")
            ok = p.get("ok", True)
            tc_id = str(p.get("tool_call_id") or uuid.uuid4())
            if ok:
                out.append(
                    (
                        "agent.tool_execution.completed",
                        ToolExecutionCompletedEvent(
                            sequence_number=self._next_seq(),
                            tool_call_id=tc_id,
                            tool_name=tool,
                            output=str(p.get("output_excerpt") or "")[:2000],
                        ).model_dump()
                        | {"agent_name": self._agent_name(sid)},
                    )
                )
            else:
                out.append(
                    (
                        "agent.tool_execution.failed",
                        ToolExecutionFailedEvent(
                            sequence_number=self._next_seq(),
                            tool_call_id=tc_id,
                            tool_name=tool,
                            error=str(p.get("error") or "Tool failed"),
                        ).model_dump()
                        | {"agent_name": self._agent_name(sid)},
                    )
                )
        elif kind in ("peer_query_sent", "peer_query_received"):
            from_s = p.get("from_server", "")
            to_s = p.get("to_server", "")
            out.append(
                (
                    "agent.transition",
                    AgentTransitionEvent(
                        sequence_number=self._next_seq(),
                        from_agent=self._agent_name(from_s),
                        to_agent=self._agent_name(to_s),
                        tool_name="ask_agent_peer",
                        completed=False,
                    ).model_dump(),
                )
            )
        elif kind == "peer_response_sent":
            from_s = p.get("from_server", "")
            to_s = p.get("to_server", "")
            out.append(
                (
                    "agent.transition",
                    AgentTransitionEvent(
                        sequence_number=self._next_seq(),
                        from_agent=self._agent_name(to_s),
                        to_agent=self._agent_name(from_s),
                        tool_name="ask_agent_peer",
                        completed=True,
                    ).model_dump(),
                )
            )
        elif kind == "orchestrator_review":
            out.append(
                (
                    "agent.task_progress",
                    TaskProgressEvent(
                        sequence_number=self._next_seq(),
                        task_id=1,
                        task_description=str(p.get("message") or "")[:500],
                        status=str(p.get("phase") or "review"),
                        current_task_index=0,
                        total_tasks=1,
                    ).model_dump(),
                )
            )
        elif kind == "summarization_started":
            out.append(
                (
                    "agent.workflow.status_changed",
                    WorkflowStatusChangedEvent(
                        sequence_number=self._next_seq(),
                        status=WorkflowStatus.SUMMARIZING,
                        agent_name="Orchestrator",
                    ).model_dump(),
                )
            )
        elif kind == "summarization_completed":
            summary = str(p.get("final_summary") or "")
            if summary:
                out.append(
                    (
                        "agent.message.delta",
                        {
                            "sequence_number": self._next_seq(),
                            "agent_name": "Orchestrator",
                            "delta": summary,
                        },
                    )
                )

        return out

    def workflow_started(self, trace_id: str) -> tuple[str, dict[str, Any]]:
        return (
            "agent.workflow.started",
            WorkflowStartedEvent(
                sequence_number=self._next_seq(),
                trace_id=trace_id,
                timestamp=time.time(),
            ).model_dump(),
        )
