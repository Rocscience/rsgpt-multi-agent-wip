"""SSE Event Emitter for streaming agent events to clients

This module handles the transformation of OpenAI Agent SDK stream events
into SSE events for the frontend. It uses strongly typed SDK classes
instead of hasattr checks.

Also tracks accumulated text for search results extraction.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import (
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)

from app.models.agent import (
    AgentThinkingEvent,
    HeartbeatEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionFailedEvent,
    ToolExecutionStartedEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class SSEEventQueue:
    """
    Queue for SSE events from context hooks.

    Provides a callback function that can be passed to hooks to queue events
    for later emission during stream processing.
    """

    queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def create_callback(self) -> Callable[[str, Dict[str, Any]], None]:
        """
        Create a callback function for queueing SSE events.

        Returns:
            Callback function that queues (event_type, data) tuples
        """

        def emit_sse_callback(event_type: str, data: dict) -> None:
            """Callback to emit SSE events from context manager hooks"""
            try:
                self.queue.put_nowait((event_type, data))
                logger.info(
                    f"✓ Context hook queued SSE event: {event_type} "
                    f"for session {data.get('session_id')}"
                )
            except Exception as e:
                logger.error(
                    f"❌ Error queueing SSE event {event_type}: {e}", exc_info=True
                )

        return emit_sse_callback


@dataclass
class SSEEventEmitter:
    """
    Transforms Agent SDK stream events into SSE events.

    Uses strongly typed SDK classes (isinstance) instead of hasattr checks
    for better type safety and maintainability.

    Also tracks accumulated text for search results extraction.
    """

    agent_name: str = "RSInsight Agent"
    _thinking_buffer: str = field(default="", init=False)
    _tool_call_names: Dict[str, str] = field(default_factory=dict, init=False)
    _sequence_number: int = field(default=0, init=False)
    _accumulated_text: str = field(default="", init=False)

    def reset(self, initial_sequence: int = 0) -> None:
        """Reset emitter state for a new stream."""
        self._thinking_buffer = ""
        self._tool_call_names = {}
        self._sequence_number = initial_sequence
        self._accumulated_text = ""

    def get_accumulated_text(self) -> str:
        """Get the accumulated message text from the stream."""
        return self._accumulated_text

    def extract_search_results(self) -> List[Dict[str, str]]:
        """
        Extract URLs from accumulated text and convert to search results format.

        Returns:
            List of search result dicts with url, title, and source keys
        """
        text = self._accumulated_text.strip()
        if not text:
            return []

        # Extract URLs from markdown links and plain text
        url_pattern = r"https?://[^\s\)\]>]+"
        extracted_urls = list(set(re.findall(url_pattern, text)))

        if not extracted_urls:
            return []

        # Convert URLs to search results format
        search_results = [
            {
                "url": url,
                "title": url.split("/")[-1] if url.split("/")[-1] else url,
                "source": "extracted_from_response",
            }
            for url in extracted_urls
        ]

        # Deduplicate by URL
        seen_urls: set[str] = set()
        deduplicated_results: List[Dict[str, str]] = []
        for result in search_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduplicated_results.append(result)

        return deduplicated_results

    async def process_stream_with_concurrent_flushing(
        self,
        stream_events: AsyncGenerator[StreamEvent, None],
        emit_callback: Callable[[str, Dict[str, Any]], str],
        sse_event_queue: Optional[asyncio.Queue] = None,
        initial_sequence: int = 0,
        heartbeat_interval: float = 15.0,
    ) -> AsyncGenerator[tuple[str, int], None]:
        """
        Process SDK stream events with concurrent queue flushing and heartbeats.

        This method runs two concurrent tasks:
        1. Agent task: Consumes SDK stream events
        2. Flusher task: Continuously drains the queue (runs during await points in hooks)

        This enables real-time emission of events queued by hooks (like summarization)
        even while the hook is still executing its async operations.

        Args:
            stream_events: Async generator of SDK StreamEvent objects
            emit_callback: Callback to format SSE events (event_type, data) -> str
            sse_event_queue: Optional queue for context hook SSE events
            initial_sequence: Starting sequence number
            heartbeat_interval: Seconds between heartbeats when stream is quiet
                               (must be < Vercel Edge 30s timeout)

        Yields:
            Tuple of (sse_event_string, sequence_number)
        """
        self.reset(initial_sequence)

        # Output queue collects events from both SDK stream and hook queue
        output_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def agent_stream_task():
            """Consume SDK events and forward to output queue."""
            stream_iter = stream_events.__aiter__()
            pending_event_task: Optional[asyncio.Task] = None
            stream_error: Optional[Exception] = None

            try:
                while True:
                    # Create task to get next SDK event if not already waiting
                    if pending_event_task is None:
                        pending_event_task = asyncio.create_task(
                            self._get_next_stream_event(stream_iter)
                        )

                    # Wait for either: SDK event arrives OR heartbeat timeout
                    done, _ = await asyncio.wait(
                        [pending_event_task],
                        timeout=heartbeat_interval,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if pending_event_task in done:
                        # SDK event arrived - check for exceptions
                        try:
                            result = pending_event_task.result()
                        except Exception as e:
                            # Store the exception to propagate after cleanup
                            stream_error = e
                            logger.error(f"Stream error in agent_stream_task: {e}")
                            break
                        pending_event_task = None

                        if result is None:
                            # Stream ended
                            break

                        # Forward SDK event to output queue
                        await output_queue.put(("sdk", result))
                    else:
                        # Timeout - emit heartbeat
                        await output_queue.put(("heartbeat", None))

            except Exception as e:
                # Catch any other unexpected exceptions
                stream_error = e
                logger.error(f"Unexpected error in agent_stream_task: {e}")

            finally:
                if pending_event_task and not pending_event_task.done():
                    pending_event_task.cancel()
                    try:
                        await pending_event_task
                    except asyncio.CancelledError:
                        pass
                
                # Signal completion or error
                if stream_error:
                    await output_queue.put(("error", stream_error))
                else:
                    await output_queue.put(("done", None))

        async def queue_flusher_task():
            """Continuously flush hook events to output queue."""
            if not sse_event_queue:
                return

            try:
                while True:
                    try:
                        # Wait for queue item with short timeout
                        # This allows the task to check for cancellation periodically
                        event_type, event_data = await asyncio.wait_for(
                            sse_event_queue.get(), timeout=0.1
                        )
                        await output_queue.put(("hook", (event_type, event_data)))
                    except asyncio.TimeoutError:
                        # No item in queue, continue checking
                        continue
            except asyncio.CancelledError:
                # Drain any remaining items before exiting
                while not sse_event_queue.empty():
                    try:
                        event_type, event_data = sse_event_queue.get_nowait()
                        await output_queue.put(("hook", (event_type, event_data)))
                    except asyncio.QueueEmpty:
                        break

        # Start both tasks
        agent_task = asyncio.create_task(agent_stream_task())
        flusher_task = asyncio.create_task(queue_flusher_task())

        try:
            while True:
                source, data = await output_queue.get()

                if source == "done":
                    break

                elif source == "error":
                    # Re-raise the exception to propagate to outer handlers
                    # This ensures stream_workflow can emit proper error events
                    raise data

                elif source == "sdk":
                    # Process SDK event
                    async for sse_event in self._process_event(data, emit_callback):
                        yield sse_event

                elif source == "hook":
                    # Process hook event
                    event_type, event_data = data
                    self._sequence_number += 1
                    event_data["sequence_number"] = self._sequence_number
                    yield emit_callback(event_type, event_data), self._sequence_number

                elif source == "heartbeat":
                    # Emit heartbeat
                    self._sequence_number += 1
                    heartbeat = HeartbeatEvent(
                        sequence_number=self._sequence_number,
                        timestamp=time.time(),
                        message="keepalive",
                    )
                    yield emit_callback(
                        "agent.heartbeat", heartbeat.model_dump()
                    ), self._sequence_number
                    logger.debug(
                        f"Emitted heartbeat (seq={self._sequence_number}) "
                        f"during stream silence"
                    )

        finally:
            # Cancel flusher task
            flusher_task.cancel()
            try:
                await flusher_task
            except asyncio.CancelledError:
                pass

            # Wait for agent task if still running
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass

    async def _get_next_stream_event(
        self, stream_iter: AsyncGenerator[StreamEvent, None]
    ) -> Optional[StreamEvent]:
        """
        Get the next event from the stream, returning None on StopAsyncIteration.

        This wrapper allows us to handle stream exhaustion gracefully in the
        heartbeat loop without raising exceptions.
        """
        try:
            return await stream_iter.__anext__()
        except StopAsyncIteration:
            return None

    async def _process_queue(
        self,
        queue: Optional[asyncio.Queue],
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """Process queued SSE events from context hooks."""
        if not queue:
            return

        try:
            while not queue.empty():
                event_type, event_data = queue.get_nowait()
                self._sequence_number += 1
                event_data["sequence_number"] = self._sequence_number
                yield emit_callback(event_type, event_data), self._sequence_number
        except asyncio.QueueEmpty:
            pass

    async def _process_event(
        self,
        event: StreamEvent,
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """
        Process a single SDK stream event.

        Uses isinstance checks against SDK types for type safety.
        """
        # RunItemStreamEvent - tool calls, tool outputs, messages
        if isinstance(event, RunItemStreamEvent):
            async for sse_event in self._handle_run_item_event(event, emit_callback):
                yield sse_event

        # RawResponsesStreamEvent - reasoning, content deltas
        elif isinstance(event, RawResponsesStreamEvent):
            async for sse_event in self._handle_raw_response_event(
                event, emit_callback
            ):
                yield sse_event

    async def _handle_run_item_event(
        self,
        event: RunItemStreamEvent,
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """Handle RunItemStreamEvent (tool calls, tool outputs)."""
        item = event.item

        # Tool call started
        if event.name == "tool_called" and isinstance(item, ToolCallItem):
            async for sse_event in self._emit_tool_started(item, emit_callback):
                yield sse_event

        # Tool output
        elif event.name == "tool_output" and isinstance(item, ToolCallOutputItem):
            async for sse_event in self._emit_tool_completed(item, emit_callback):
                yield sse_event

    async def _emit_tool_started(
        self,
        item: ToolCallItem,
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """Emit tool execution started event."""
        # If we have pending thinking content, emit it as complete first
        # This handles models that call tools immediately after thinking
        if self._thinking_buffer:
            self._sequence_number += 1
            yield emit_callback(
                "agent.thinking",
                AgentThinkingEvent(
                    sequence_number=self._sequence_number,
                    agent_name=self.agent_name,
                    thinking_text=self._thinking_buffer,
                    is_complete=True,
                ).model_dump(),
            ), self._sequence_number
            self._thinking_buffer = ""

        raw_item = item.raw_item
        tool_call_id = self._extract_tool_call_id(raw_item)
        tool_name = getattr(raw_item, "name", "unknown")
        tool_args = self._extract_tool_args(raw_item)

        # Store for later output matching
        self._tool_call_names[tool_call_id] = tool_name

        logger.info(f"[Tool Call] {tool_name} started (id: {tool_call_id})")

        self._sequence_number += 1
        yield emit_callback(
            "agent.tool_execution.started",
            ToolExecutionStartedEvent(
                sequence_number=self._sequence_number,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_args=tool_args,
            ).model_dump(),
        ), self._sequence_number

    async def _emit_tool_completed(
        self,
        item: ToolCallOutputItem,
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """Emit tool execution completed or failed event."""
        output = item.output
        raw_item = item.raw_item
        tool_call_id = self._extract_tool_call_id(raw_item)
        tool_name = self._tool_call_names.get(tool_call_id, "unknown")

        # Check for errors
        error = self._extract_error(output)

        logger.info(f"[Tool Call] {tool_name} completed (id: {tool_call_id})")

        self._sequence_number += 1
        if error:
            logger.error(f"[Tool Call] {tool_name} failed: {error}")
            yield emit_callback(
                "agent.tool_execution.failed",
                ToolExecutionFailedEvent(
                    sequence_number=self._sequence_number,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    error=error,
                ).model_dump(),
            ), self._sequence_number
        else:
            yield emit_callback(
                "agent.tool_execution.completed",
                ToolExecutionCompletedEvent(
                    sequence_number=self._sequence_number,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    output=output,
                ).model_dump(),
            ), self._sequence_number

    async def _handle_raw_response_event(
        self,
        event: RawResponsesStreamEvent,
        emit_callback: Callable[[str, Dict[str, Any]], str],
    ) -> AsyncGenerator[tuple[str, int], None]:
        """Handle RawResponsesStreamEvent (reasoning, content)."""
        raw_data = event.data
        raw_type = getattr(raw_data, "type", None)

        # Reasoning deltas
        if raw_type in [
            "response.reasoning_text.delta",
            "response.reasoning_summary_text.delta",
        ]:
            delta = getattr(raw_data, "delta", None)
            if delta:
                self._thinking_buffer += delta
                self._sequence_number += 1
                yield emit_callback(
                    "agent.thinking",
                    AgentThinkingEvent(
                        sequence_number=self._sequence_number,
                        agent_name=self.agent_name,
                        thinking_text=delta,
                        is_complete=False,
                    ).model_dump(),
                ), self._sequence_number

        # Reasoning completion (OpenAI and Claude/Anthropic via LiteLLM)
        elif raw_type in [
            "response.reasoning_text.done",
            "response.reasoning_summary_text.done",
            # Claude/Anthropic extended thinking completion events
            "response.thinking.done",
            "content_block_stop",
        ]:
            text = getattr(raw_data, "text", None)
            if text:
                self._thinking_buffer = text

            if self._thinking_buffer:
                self._sequence_number += 1
                yield emit_callback(
                    "agent.thinking",
                    AgentThinkingEvent(
                        sequence_number=self._sequence_number,
                        agent_name=self.agent_name,
                        thinking_text=self._thinking_buffer,
                        is_complete=True,
                    ).model_dump(),
                ), self._sequence_number
                self._thinking_buffer = ""

        # Output text delta
        elif raw_type == "response.output_text.delta":
            delta = getattr(raw_data, "delta", None)
            if delta:
                # If we have pending thinking content, emit it as complete first
                # This handles models that don't send explicit thinking completion events
                if self._thinking_buffer:
                    self._sequence_number += 1
                    yield emit_callback(
                        "agent.thinking",
                        AgentThinkingEvent(
                            sequence_number=self._sequence_number,
                            agent_name=self.agent_name,
                            thinking_text=self._thinking_buffer,
                            is_complete=True,
                        ).model_dump(),
                    ), self._sequence_number
                    self._thinking_buffer = ""

                # Accumulate text for search results extraction
                self._accumulated_text += delta
                self._sequence_number += 1
                yield emit_callback(
                    "agent.message.delta",
                    {
                        "sequence_number": self._sequence_number,
                        "agent_name": self.agent_name,
                        "delta": delta,
                    },
                ), self._sequence_number

        # Content part delta
        elif raw_type == "response.content_part.delta":
            delta = getattr(raw_data, "delta", None)
            if delta:
                delta_text = (
                    getattr(delta, "text", None)
                    if hasattr(delta, "text")
                    else delta if isinstance(delta, str) else None
                )
                if delta_text:
                    # If we have pending thinking content, emit it as complete first
                    # This handles models that don't send explicit thinking completion events
                    if self._thinking_buffer:
                        self._sequence_number += 1
                        yield emit_callback(
                            "agent.thinking",
                            AgentThinkingEvent(
                                sequence_number=self._sequence_number,
                                agent_name=self.agent_name,
                                thinking_text=self._thinking_buffer,
                                is_complete=True,
                            ).model_dump(),
                        ), self._sequence_number
                        self._thinking_buffer = ""

                    # Accumulate text for search results extraction
                    self._accumulated_text += delta_text
                    self._sequence_number += 1
                    yield emit_callback(
                        "agent.message.delta",
                        {
                            "sequence_number": self._sequence_number,
                            "agent_name": self.agent_name,
                            "delta": delta_text,
                        },
                    ), self._sequence_number

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_tool_call_id(self, raw_item: Any) -> str:
        """Extract tool call ID from raw item."""
        tool_call_id = None

        # Try Pydantic model_dump first
        if hasattr(raw_item, "model_dump"):
            item_dict = raw_item.model_dump()
            if isinstance(item_dict, dict):
                tool_call_id = item_dict.get("call_id") or item_dict.get("id")

        # Try direct attribute access
        if not tool_call_id:
            for attr in ["call_id", "id", "function_call_id", "tool_call_id"]:
                val = getattr(raw_item, attr, None)
                if val:
                    tool_call_id = val
                    break

        # Try dict access
        if not tool_call_id and isinstance(raw_item, dict):
            tool_call_id = (
                raw_item.get("call_id")
                or raw_item.get("id")
                or raw_item.get("function_call_id")
                or raw_item.get("tool_call_id")
            )

        if not tool_call_id:
            logger.warning(f"Could not extract tool_call_id from {type(raw_item)}")

        return tool_call_id or "unknown"

    def _extract_tool_args(self, raw_item: Any) -> Dict[str, Any]:
        """Extract tool arguments from raw item."""
        arguments = getattr(raw_item, "arguments", None)
        if not arguments:
            return {}

        if isinstance(arguments, str):
            try:
                return json.loads(arguments)
            except (json.JSONDecodeError, TypeError):
                return {}
        elif isinstance(arguments, dict):
            return arguments
        return {}

    def _extract_error(self, output: Any) -> Optional[str]:
        """Extract error from tool output if present."""
        if hasattr(output, "error") and output.error:
            return str(output.error)
        if isinstance(output, dict) and "error" in output:
            return str(output["error"])
        return None
