"""Multi-agent orchestration service — streams SSE for production FE/BE."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from agents.tracing.util import gen_trace_id
from fastapi import Request

from app.config import settings
from app.models.agent import (
    AgentRequest,
    AgentRunInfo,
    AgentRunStatus,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowStatus,
    WorkflowStatusChangedEvent,
)
from app.models.channels import SourceChannel
from app.services.multi_agent.activity import ActivityEvent
from app.services.multi_agent.schema import load_default_config
from app.services.multi_agent.sse_bridge import MultiAgentSSEBridge
from app.services.multi_agent.workflow import run_multi_agent_workflow
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


class MultiAgentOrchestrationService:
    """Runs demo v2 workflow and maps activity events to production SSE."""

    @staticmethod
    def _emit(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    async def stream_workflow(
        self, request: AgentRequest, http_request: Optional[Request] = None
    ) -> AsyncGenerator[str, None]:
        run_id = str(uuid.uuid4())
        trace_id = gen_trace_id()
        sequence_number = 0
        bridge = MultiAgentSSEBridge()
        event_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

        cfg = load_default_config()
        for sid, entry in cfg.servers.items():
            if entry.display_name:
                bridge.set_server_display(sid, entry.display_name)

        def on_activity(evt: ActivityEvent) -> None:
            for event_type, payload in bridge.map_event(evt):
                event_queue.put_nowait((event_type, payload))

        try:
            sequence_number += 1
            run_info = RunStartedEvent(
                sequence_number=sequence_number,
                run=AgentRunInfo(
                    id=run_id,
                    agent_name="Multi-Agent Orchestrator",
                    status=AgentRunStatus.RUNNING,
                    created_at=time.time(),
                ),
            )
            yield self._emit("agent.run.started", run_info.model_dump())

            ws_type, ws_data = bridge.workflow_started(trace_id)
            yield self._emit(ws_type, ws_data)

            if not request.device_id:
                raise ValueError("device_id is required for multi-agent agent mode")

            if not connection_manager.is_device_connected(request.device_id):
                raise ValueError(
                    f"Device {request.device_id} is not connected. "
                    "Open RSInsight desktop and sign in."
                )

            model = request.model or cfg.model
            user_permission = request.user_permission
            source_channels = request.source_channels or [SourceChannel.ROC]

            async def _run_workflow() -> dict:
                return await run_multi_agent_workflow(
                    goal=request.input,
                    device_id=request.device_id,
                    model=model,
                    user_permission=user_permission,
                    source_channels=source_channels,
                    on_event=on_activity,
                )

            workflow_task = asyncio.create_task(_run_workflow())

            while not workflow_task.done():
                try:
                    event_type, payload = await asyncio.wait_for(
                        event_queue.get(), timeout=1.0
                    )
                    yield self._emit(event_type, payload)
                except asyncio.TimeoutError:
                    if http_request and await http_request.is_disconnected():
                        workflow_task.cancel()
                        break
                    yield self._emit(
                        "agent.heartbeat",
                        {"sequence_number": bridge._next_seq(), "timestamp": time.time()},
                    )

            while not event_queue.empty():
                event_type, payload = event_queue.get_nowait()
                yield self._emit(event_type, payload)

            result = await workflow_task
            final_summary = str(result.get("final_summary") or "")

            if final_summary:
                yield self._emit(
                    "agent.message.delta",
                    {
                        "sequence_number": bridge._next_seq(),
                        "agent_name": "Orchestrator",
                        "delta": final_summary,
                    },
                )

            sequence_number = bridge._next_seq()
            yield self._emit(
                "agent.workflow.status_changed",
                WorkflowStatusChangedEvent(
                    sequence_number=sequence_number,
                    status=WorkflowStatus.COMPLETED,
                    agent_name="Orchestrator",
                ).model_dump(),
            )

            yield self._emit(
                "agent.workflow.completed",
                WorkflowCompletedEvent(
                    sequence_number=bridge._next_seq(),
                    trace_id=trace_id,
                    timestamp=time.time(),
                ).model_dump(),
            )

            yield self._emit(
                "agent.run.completed",
                RunCompletedEvent(
                    sequence_number=bridge._next_seq(),
                    run=AgentRunInfo(
                        id=run_id,
                        agent_name="Multi-Agent Orchestrator",
                        status=AgentRunStatus.COMPLETED,
                        created_at=time.time(),
                        completed_at=time.time(),
                    ),
                    final_output=final_summary,
                ).model_dump(),
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Multi-agent workflow failed")
            yield self._emit(
                "agent.workflow.failed",
                WorkflowFailedEvent(
                    sequence_number=bridge._next_seq(),
                    trace_id=trace_id,
                    error=str(exc),
                    timestamp=time.time(),
                ).model_dump(),
            )
            yield self._emit(
                "agent.run.failed",
                RunFailedEvent(
                    sequence_number=bridge._next_seq(),
                    run=AgentRunInfo(
                        id=run_id,
                        agent_name="Multi-Agent Orchestrator",
                        status=AgentRunStatus.FAILED,
                        created_at=time.time(),
                        completed_at=time.time(),
                    ),
                    error=str(exc),
                ).model_dump(),
            )


multi_agent_orchestration_service = MultiAgentOrchestrationService()


def should_use_multi_agent(request: AgentRequest) -> bool:
    """Route to multi-agent when enabled and device is present."""
    from app.models.agent import AgentMode

    if not settings.multi_agent_enabled:
        return False
    return request.mode == AgentMode.AGENT and bool(request.device_id)
