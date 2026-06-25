"""Agent Orchestration Service

This service orchestrates the execution of the RSInsight agent with tools,
handling the complete workflow lifecycle including streaming, tracing,
and event emission.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import litellm
from agents import Runner, RunResult, RunResultStreaming, trace
from agents.exceptions import (
    MaxTurnsExceeded,
    ModelBehaviorError,
    OutputGuardrailTripwireTriggered,
    ToolInputGuardrailTripwireTriggered,
    ToolOutputGuardrailTripwireTriggered,
    UserError,
)
from agents.tracing.util import gen_trace_id
from agents.usage import RequestUsage, Usage
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import async_engine
from app.models.agent import (
    AgentContext,
    AgentMode,
    AgentRequest,
    AgentRunInfo,
    AgentRunStatus,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowStartedEvent,
    WorkflowStatus,
    WorkflowStatusChangedEvent,
)
from app.models.chat import ResponseSearchResultsEvent
from app.services.agent.agent_config import build_run_config, create_context_hooks
from app.services.agent.main_agent import create_main_agent, get_mode_config
from app.services.agent.session_factory import create_sdk_session
from app.services.agent.sse_event_emitter import SSEEventEmitter, SSEEventQueue
from app.services.agent.tools import tool_initializer, update_agent_tools
from app.services.context_manager import (
    load_token_count_from_db,
    persist_token_count_to_db,
)
from app.services.context_manager.token_counter import TokenCounter
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


# =============================================================================
# Orchestration Service
# =============================================================================


class OrchestrationService:
    """
    Service for agent workflow execution with complete lifecycle management.

    Responsibilities:
    - Workflow lifecycle (run started/completed/failed events)
    - Agent execution orchestration
    - SSE event streaming
    - Search results extraction
    """

    def __init__(self):
        """Initialize the service with active runs tracking."""
        self.active_runs: Dict[str, AgentRunInfo] = {}

    # =========================================================================
    # Public API
    # =========================================================================

    async def stream_workflow(
        self, request: AgentRequest, http_request: Optional[Request] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a complete agent workflow execution.

        This is the main entry point that handles:
        - Run lifecycle events
        - Tracing setup
        - Agent execution
        - Search results extraction
        - Error handling

        Args:
            request: The agent request with messages and configuration
            http_request: Optional FastAPI request for disconnect detection

        Yields:
            Server-sent event strings
        """
        run_id = str(uuid.uuid4())
        created_at = time.time()
        sequence_number = 0
        trace_id = gen_trace_id()
        emitter: Optional[SSEEventEmitter] = None

        try:
            # Create and track run info
            run_info = self._create_run_info(run_id)
            self.active_runs[run_id] = run_info

            # Emit run started
            sequence_number += 1
            start_event = RunStartedEvent(sequence_number=sequence_number, run=run_info)
            yield self._emit_event("agent.run.started", start_event.model_dump())

            # Setup tracing with session linking and device metadata
            trace_metadata = {"run_id": run_id}
            if request.device_id:
                trace_metadata["device_id"] = request.device_id

            with trace(
                workflow_name="rsinsight-agent",
                trace_id=trace_id,
                group_id=request.session_id,  # Links traces from same conversation
                metadata=trace_metadata,
            ) as trace_context:
                logger.info(
                    f"Workflow started - run_id: {run_id}, trace_id: {trace_context.trace_id}, "
                    f"session_id: {request.session_id}"
                )

                # Emit workflow started
                sequence_number += 1
                workflow_started = WorkflowStartedEvent(
                    sequence_number=sequence_number,
                    trace_id=trace_id,
                    timestamp=created_at,
                )
                yield self._emit_event(
                    "agent.workflow.started", workflow_started.model_dump()
                )

                # Create agent context
                agent_context = self._create_agent_context(request)

                # Execute agent workflow with user input
                emitter = SSEEventEmitter(agent_name="RSInsight Agent")
                async for event_str, seq_num in self._run_agent(
                    request=request,
                    agent_context=agent_context,
                    sequence_number=sequence_number,
                    emitter=emitter,
                ):
                    sequence_number = seq_num
                    yield event_str

                # Extract and emit search results
                search_results = emitter.extract_search_results()
                if search_results:
                    sequence_number += 1
                    search_event = ResponseSearchResultsEvent(
                        sequence_number=sequence_number,
                        response_id=run_id,
                        search_results=search_results,
                    )
                    yield self._emit_event(
                        "response.search_results", search_event.model_dump()
                    )
                    logger.info(
                        f"Emitted {len(search_results)} search results for {run_id}"
                    )

                # Emit workflow status changed
                sequence_number += 1
                yield self._emit_event(
                    "agent.workflow.status_changed",
                    WorkflowStatusChangedEvent(
                        sequence_number=sequence_number,
                        status=WorkflowStatus.COMPLETED,
                        agent_name="RSInsight Agent",
                    ).model_dump(),
                )

                # Emit workflow completed with usage
                sequence_number += 1
                usage_breakdown = getattr(agent_context, "usage_breakdown", None)
                total_tokens = getattr(agent_context, "total_tokens", None)
                workflow_completed = WorkflowCompletedEvent(
                    sequence_number=sequence_number,
                    trace_id=trace_id,
                    timestamp=time.time(),
                    usage_breakdown=usage_breakdown,
                    total_tokens=total_tokens,
                )
                yield self._emit_event(
                    "agent.workflow.completed", workflow_completed.model_dump()
                )

                # Emit run completed
                run_info.status = AgentRunStatus.COMPLETED
                sequence_number += 1
                completed_event = RunCompletedEvent(
                    sequence_number=sequence_number, run=run_info, final_output=None
                )
                yield self._emit_event(
                    "agent.run.completed", completed_event.model_dump()
                )

                logger.info(f"Workflow completed - run_id: {run_id}")

        except asyncio.CancelledError:
            logger.warning(f"Workflow cancelled - run_id: {run_id}")
            run_info = self.active_runs.get(run_id) or self._create_run_info(
                run_id, AgentRunStatus.FAILED
            )
            run_info.status = AgentRunStatus.FAILED

            if trace_id:
                sequence_number += 1
                workflow_failed = WorkflowFailedEvent(
                    sequence_number=sequence_number,
                    trace_id=trace_id,
                    error="Workflow cancelled by client",
                    timestamp=time.time(),
                )
                yield self._emit_event(
                    "agent.workflow.failed", workflow_failed.model_dump()
                )

            sequence_number += 1
            failed_event = RunFailedEvent(
                sequence_number=sequence_number,
                run=run_info,
                error="Workflow cancelled by client",
            )
            yield self._emit_event("agent.run.failed", failed_event.model_dump())

        except Exception as e:
            # Only log full traceback for unexpected errors, not for re-raised ValueErrors
            if isinstance(e, ValueError):
                logger.error(f"Workflow error - run_id: {run_id}: {e}")
            else:
                logger.error(f"Workflow error - run_id: {run_id}: {e}", exc_info=True)

            run_info = self.active_runs.get(run_id) or self._create_run_info(
                run_id, AgentRunStatus.FAILED
            )
            run_info.status = AgentRunStatus.FAILED

            if trace_id:
                sequence_number += 1
                workflow_failed = WorkflowFailedEvent(
                    sequence_number=sequence_number,
                    trace_id=trace_id,
                    error=str(e),
                    timestamp=time.time(),
                )
                yield self._emit_event(
                    "agent.workflow.failed", workflow_failed.model_dump()
                )

            sequence_number += 1
            failed_event = RunFailedEvent(
                sequence_number=sequence_number, run=run_info, error=str(e)
            )
            yield self._emit_event("agent.run.failed", failed_event.model_dump())

        finally:
            if run_id in self.active_runs:
                del self.active_runs[run_id]

    async def get_active_runs(self) -> Dict[str, AgentRunInfo]:
        """Get information about active workflow runs."""
        return self.active_runs.copy()

    # =========================================================================
    # Lifecycle Helpers (testable)
    # =========================================================================

    def _create_run_info(
        self,
        run_id: str,
        status: AgentRunStatus = AgentRunStatus.RUNNING,
    ) -> AgentRunInfo:
        """Create initial run info for a workflow."""
        return AgentRunInfo(
            id=run_id,
            agent_name="RSInsight Agent",
            status=status,
            turn_count=0,
            created_at=time.time(),
            completed_at=None,
        )

    def _create_agent_context(self, request: AgentRequest) -> AgentContext:
        """Create agent context from request."""
        device_connected = False
        if request.device_id:
            device_connected = connection_manager.is_device_connected(request.device_id)

        return AgentContext(
            user_permission=request.user_permission,
            source_channels=request.source_channels,
            device_id=request.device_id,
            session_id=request.session_id,
            device_connected=device_connected,
        )

    # =========================================================================
    # Agent Execution
    # =========================================================================

    async def _run_agent(
        self,
        request: AgentRequest,
        agent_context: AgentContext,
        sequence_number: int,
        emitter: SSEEventEmitter,
    ) -> AsyncGenerator[tuple[str, int], None]:
        """
        Execute agent workflow and stream events.

        Handles:
        - Tool initialization
        - Agent creation
        - SDK session for conversation persistence
        - Streaming execution
        - Exception handling

        Args:
            request: The agent request with user input
            agent_context: Agent context with permissions
            sequence_number: Current sequence number
            emitter: SSE event emitter for stream processing

        Yields:
            Tuple of (event_string, sequence_number)
        """
        # Get mode-specific configuration
        mode_config = get_mode_config(request.mode)
        max_turns = mode_config["max_turns"]

        try:
            # Initialize tools based on mode
            # Ask mode: limited tools with usage tracking (search_knowledge=4, search_web=3)
            # Agent mode: unlimited base tools (device tools added separately)
            base_tools = tool_initializer.get_tools_for_mode(
                mode=request.mode,
                agent_context=agent_context,
            )
            logger.info(
                f"Initialized {len(base_tools)} tools for mode={request.mode.value}"
            )

            # MCP servers (currently disabled)
            mcp_servers: list = []

            # Create SDK session for conversation persistence (optional)
            # Must be created BEFORE context hooks so hooks can reference it
            sdk_session = None
            if request.use_sdk_session:
                sdk_session = create_sdk_session(
                    session_id=request.session_id,
                    create_tables=False,  # Use Alembic migrations in production
                )
                logger.info(f"SDK session created for session_id: {request.session_id}")

            # Create SSE event queue for context hook events
            sse_event_queue = SSEEventQueue()

            # Load initial token count from database for pre-turn threshold checking
            # Add estimate of user input to get accurate pre-run context size
            initial_token_count = 0
            if request.use_sdk_session:
                try:
                    async with AsyncSession(async_engine) as db_session:
                        initial_token_count, _ = await load_token_count_from_db(
                            session_id=request.session_id,
                            db_session=db_session,
                        )
                    # Add estimate of user's new input to the stored token count
                    # This gives us accurate pre-run context size without re-estimating
                    if initial_token_count > 0:
                        try:
                            input_tokens = TokenCounter.count_tokens(
                                request.input, request.model or "gpt-5"
                            )
                            initial_token_count += input_tokens
                            logger.info(
                                f"Pre-run token estimate: {initial_token_count:,} "
                                f"(DB: {initial_token_count - input_tokens:,} \
                                + input: {input_tokens:,})"
                            )
                        except ValueError:
                            # Model not supported for token counting, use rough estimate
                            input_tokens = len(request.input) // 4  # ~4 chars per token
                            initial_token_count += input_tokens
                except Exception as e:
                    logger.warning(f"Failed to load initial token count: {e}")

            # Create context hooks for pruning (with session for persistence)
            # Must be created BEFORE agent so hooks can be passed to agent
            context_hooks = None
            if request.use_sdk_session and sdk_session:
                context_hooks = create_context_hooks(
                    session_id=request.session_id,
                    model=request.model or "gpt-5",
                    session=sdk_session,
                    emit_sse_callback=sse_event_queue.create_callback(),
                    initial_token_count=initial_token_count,
                )
                logger.info(
                    f"Context hooks created with session for pruning persistence "
                    f"(initial tokens: {initial_token_count:,})"
                )

            # Create agent with mode-specific configuration
            # Pass context_hooks so on_start/on_llm_end/on_end are called
            main_agent = create_main_agent(
                model=request.model or "gpt-5",
                tools=base_tools,
                mode=request.mode,
                mcp_servers=mcp_servers,
                reasoning_effort=request.reasoning_effort,
                hooks=context_hooks,
                agent_context=agent_context,
            )

            # Add device tools only in agent mode (ask mode is knowledge-only)
            if request.mode == AgentMode.AGENT and request.device_id:
                device_result = await tool_initializer.add_device_tools_to_agent(
                    agent=main_agent,
                    device_id=request.device_id,
                    update_callback=update_agent_tools,
                )
                agent_context.device_connected = device_result.device_connected
            elif request.mode == AgentMode.ASK and request.device_id:
                logger.info(
                    f"Device '{request.device_id}' provided but ignored in ask mode"
                )

            # Build run config with context hooks
            run_config = build_run_config(context_hooks)
            agent_result = Runner.run_streamed(
                main_agent,
                input=request.input,
                context=agent_context,
                max_turns=max_turns,
                run_config=run_config,
                session=sdk_session,  # None if SDK session disabled
            )

            # Stream events with concurrent queue flushing and heartbeats
            # - Heartbeats keep SSE connection alive during long tool executions
            # - Concurrent flushing enables real-time emission of hook events
            #   (like summarization progress) even while hooks are still executing
            # NOTE: Heartbeat interval must be LESS than Vercel Edge timeout (30s)
            # to prevent race conditions where Vercel kills connection before heartbeat
            try:
                async for (
                    sse_event,
                    seq_num,
                ) in emitter.process_stream_with_concurrent_flushing(
                    stream_events=agent_result.stream_events(),  # type: ignore[arg-type]
                    emit_callback=self._emit_event,
                    sse_event_queue=sse_event_queue.queue,  # Pass queue for context hook events
                    initial_sequence=sequence_number,
                    heartbeat_interval=15.0,  # Must be < Vercel Edge 30s timeout
                ):
                    yield sse_event, seq_num
                    sequence_number = seq_num

            except MaxTurnsExceeded as e:
                raise ValueError(
                    "The AI assistant took too many steps to complete your request. "
                    "Please try breaking your request into smaller tasks."
                ) from e

            except ModelBehaviorError as e:
                error_str = str(e.message)
                if "Tool" in error_str and "not found in agent" in error_str:
                    raise ValueError(
                        "The requested tool is not available. "
                        "Please check your device connection and try again."
                    ) from e
                raise ValueError(
                    "The AI assistant encountered an issue. "
                    "Please try rephrasing your question."
                ) from e

            except UserError as e:
                raise ValueError(
                    "There was an issue with the request configuration. "
                    "Please check your input and try again."
                ) from e

            except OutputGuardrailTripwireTriggered as e:
                raise ValueError(
                    "The response was flagged by content safety filters. "
                    "Please try a different approach."
                ) from e

            except ToolInputGuardrailTripwireTriggered as e:
                raise ValueError(
                    "The tool parameters were flagged by safety filters. "
                    "Please check your input."
                ) from e

            except ToolOutputGuardrailTripwireTriggered as e:
                raise ValueError(
                    "The tool output was flagged by safety filters. "
                    "Please try again."
                ) from e

            # Extract final usage data
            self._extract_usage_data(agent_result, agent_context)

            # Persist token count to database for next request's pre-turn check
            # Use shield to protect from cancellation during DB operations
            if context_hooks and request.use_sdk_session:
                try:
                    await asyncio.shield(
                        self._persist_token_count(
                            session_id=request.session_id,
                            input_tokens=context_hooks._last_input_tokens,
                            model_name=request.model or "gpt-5",
                        )
                    )
                except asyncio.CancelledError:
                    logger.debug("Token persistence interrupted by cancellation")
                except Exception as e:
                    logger.warning(f"Failed to persist token count: {e}")

        except litellm.exceptions.BadRequestError as e:
            # Invalid request (bad params, unsupported features, etc.)
            logger.error(f"LiteLLM BadRequestError: {e}")
            raise ValueError(
                "The request to the AI model was invalid. "
                "Please check your input or try a different model."
            ) from e

        except litellm.exceptions.AuthenticationError as e:
            logger.error(f"LiteLLM AuthenticationError: {e}")
            raise ValueError(
                "Authentication with the AI provider failed. "
                "Please check API key configuration."
            ) from e

        except litellm.exceptions.RateLimitError as e:
            logger.warning(f"LiteLLM RateLimitError: {e}")
            raise ValueError(
                "The AI service is currently rate limited. "
                "Please wait a moment and try again."
            ) from e

        except litellm.exceptions.ServiceUnavailableError as e:
            logger.error(f"LiteLLM ServiceUnavailableError: {e}")
            raise ValueError(
                "The AI service is temporarily unavailable. "
                "Please try again in a few moments."
            ) from e

        except litellm.exceptions.Timeout as e:
            logger.warning(f"LiteLLM Timeout: {e}")
            raise ValueError(
                "The request to the AI model timed out. "
                "Please try again or simplify your request."
            ) from e

        except litellm.exceptions.APIConnectionError as e:
            logger.error(f"LiteLLM APIConnectionError: {e}")
            raise ValueError(
                "Failed to connect to the AI service. "
                "Please check your network connection."
            ) from e

        except litellm.exceptions.APIError as e:
            # Catch-all for other LiteLLM API errors
            logger.error(f"LiteLLM APIError: {e}")
            raise ValueError(
                "An error occurred with the AI service. " "Please try again."
            ) from e

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _persist_token_count(
        self, session_id: str, input_tokens: int, model_name: str
    ) -> None:
        """Persist token count to database (cancellation-safe)."""
        async with AsyncSession(async_engine) as db_session:
            await persist_token_count_to_db(
                session_id=session_id,
                input_tokens=input_tokens,
                model_name=model_name,
                db_session=db_session,
            )

    @staticmethod
    def _emit_event(event_type: str, data: dict) -> str:
        """Format a server-sent event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    def _extract_usage_data(
        self,
        agent_result: Union[RunResult, RunResultStreaming],
        agent_context: AgentContext,
    ) -> None:
        """Extract and store final usage data from agent result."""
        logger.info(
            f"[Usage] Retrieving final usage for session {agent_context.session_id}"
        )

        if not agent_result.context_wrapper:
            logger.warning(
                f"[Usage] No context_wrapper for session {agent_context.session_id}"
            )
            return

        usage: Optional[Usage] = agent_result.context_wrapper.usage
        if not usage:
            logger.warning(
                f"[Usage] Usage object is None for session {agent_context.session_id}"
            )
            return

        logger.info(
            f"[Usage] Final - Input: {usage.input_tokens}, "
            f"Output: {usage.output_tokens}, \
            Total: {usage.total_tokens}"
        )

        if usage.total_tokens == 0:
            logger.warning(
                f"[Usage] Usage data is zeros for session {agent_context.session_id}"
            )
            return

        # Store total tokens for the response
        agent_context.total_tokens = usage.total_tokens

        if usage.request_usage_entries:
            usage_breakdown: List[Dict[str, Any]] = []
            for idx, req in enumerate[RequestUsage](usage.request_usage_entries, 1):
                entry: Dict[str, Any] = {
                    "request_number": idx,
                    "input_tokens": req.input_tokens,
                    "output_tokens": req.output_tokens,
                    "total_tokens": req.total_tokens,
                }

                if req.input_tokens_details:
                    cached: int = req.input_tokens_details.cached_tokens
                    if cached > 0:
                        entry["cached_tokens"] = cached

                if req.output_tokens_details:
                    reasoning: int = req.output_tokens_details.reasoning_tokens
                    if reasoning > 0:
                        entry["reasoning_tokens"] = reasoning

                usage_breakdown.append(entry)

            agent_context.usage_breakdown = usage_breakdown

            # Log full usage summary with raw API data for cache debugging
            logger.info(
                f"[Usage] ═══════════════════════════════════════════════\n"
                f"  Session: {agent_context.session_id}\n"
                f"  Total: {usage.total_tokens:,} tokens "
                f"(input={usage.input_tokens:,}, output={usage.output_tokens:,})\n"
                f"  Requests: {len(usage_breakdown)}\n"
                + "\n".join(
                    f"    #{e['request_number']}: "
                    f"in={e['input_tokens']:,} | out={e['output_tokens']:,} | "
                    f"cached={e.get('cached_tokens', 0):,} | "
                    f"reasoning={e.get('reasoning_tokens', 0):,}"
                    for e in usage_breakdown
                )
                + f"\n  ═══════════════════════════════════════════════"
            )

    # =========================================================================
    # MCP Server (currently disabled)
    # =========================================================================

    async def _initialize_rslog_mcp_server(
        self,
        rslog_mcp_url: str,
        rslog_mcp_token: str | None,
        timeout: int,
    ):
        """
        Initialize RSLog MCP server connection.

        Currently disabled - kept for future use.
        """
        from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

        try:
            params_kwargs: dict[str, object] = {
                "url": rslog_mcp_url,
                "timeout": float(timeout),
            }
            if rslog_mcp_token:
                params_kwargs["headers"] = {
                    "Authorization": f"Bearer {rslog_mcp_token}"
                }

            params = MCPServerStreamableHttpParams(**params_kwargs)  # type: ignore[typeddict-item]

            rslog_server = MCPServerStreamableHttp(
                name="RSLog MCP Server",
                params=params,
                cache_tools_list=True,
                max_retry_attempts=3,
                use_structured_content=True,
            )

            await rslog_server.connect()
            logger.info(f"RSLog MCP server connected to {rslog_mcp_url}")
            return rslog_server

        except Exception as e:
            logger.error(f"Failed to connect RSLog MCP server: {e}", exc_info=True)
            return None


# =============================================================================
# Singleton Instance
# =============================================================================

orchestration_service = OrchestrationService()
