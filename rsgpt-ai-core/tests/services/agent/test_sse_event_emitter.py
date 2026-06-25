"""Unit tests for SSE event emitter"""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from app.services.agent.sse_event_emitter import SSEEventEmitter


class TestSSEEventEmitter:
    """Test SSEEventEmitter class"""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter instance"""
        return SSEEventEmitter(agent_name="Test Agent")

    def test_initialization(self, emitter):
        """Test emitter initializes correctly"""
        assert emitter.agent_name == "Test Agent"
        assert emitter._thinking_buffer == ""
        assert emitter._tool_call_names == {}
        assert emitter._sequence_number == 0
        assert emitter._accumulated_text == ""

    def test_reset(self, emitter):
        """Test reset clears state"""
        emitter._thinking_buffer = "some text"
        emitter._tool_call_names = {"id1": "tool1"}
        emitter._sequence_number = 10
        emitter._accumulated_text = "accumulated"

        emitter.reset(initial_sequence=5)

        assert emitter._thinking_buffer == ""
        assert emitter._tool_call_names == {}
        assert emitter._sequence_number == 5
        assert emitter._accumulated_text == ""

    def test_get_accumulated_text(self, emitter):
        """Test getting accumulated text"""
        emitter._accumulated_text = "Hello World"

        assert emitter.get_accumulated_text() == "Hello World"

    def test_get_accumulated_text_empty(self, emitter):
        """Test getting accumulated text when empty"""
        assert emitter.get_accumulated_text() == ""


class TestSearchResultsExtraction:
    """Test search results extraction from accumulated text"""

    @pytest.fixture
    def emitter(self):
        return SSEEventEmitter()

    def test_extract_search_results(self, emitter):
        """Test extracting search results from text"""
        emitter._accumulated_text = (
            "Check out https://example.com and https://test.com/page"
        )

        results = emitter.extract_search_results()

        assert len(results) == 2
        urls = [r["url"] for r in results]
        assert "https://example.com" in urls
        assert "https://test.com/page" in urls
        assert all("title" in r for r in results)
        assert all(r["source"] == "extracted_from_response" for r in results)

    def test_extract_search_results_deduplicates(self, emitter):
        """Test that duplicate URLs are deduplicated"""
        emitter._accumulated_text = (
            "See https://example.com and also https://example.com again"
        )

        results = emitter.extract_search_results()

        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"

    def test_extract_search_results_empty_text(self, emitter):
        """Test extracting from empty text"""
        emitter._accumulated_text = ""

        results = emitter.extract_search_results()

        assert results == []

    def test_extract_search_results_no_urls(self, emitter):
        """Test extracting when no URLs present"""
        emitter._accumulated_text = "This is just plain text with no URLs"

        results = emitter.extract_search_results()

        assert results == []

    def test_extract_search_results_markdown_links(self, emitter):
        """Test extracting URLs from markdown links"""
        emitter._accumulated_text = "Check [this link](https://example.com/page) out"

        results = emitter.extract_search_results()

        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/page"

    def test_extract_search_results_multiple_protocols(self, emitter):
        """Test extracting both http and https URLs"""
        emitter._accumulated_text = "Visit http://example.com or https://secure.com"

        results = emitter.extract_search_results()

        assert len(results) == 2
        urls = [r["url"] for r in results]
        assert "http://example.com" in urls
        assert "https://secure.com" in urls


class TestExtractToolCallId:
    """Test tool call ID extraction"""

    @pytest.fixture
    def emitter(self):
        return SSEEventEmitter()

    def test_extract_from_model_dump(self, emitter):
        """Test extracting tool call ID using model_dump"""
        raw_item = SimpleNamespace()
        raw_item.model_dump = lambda: {"call_id": "test-call-123"}

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-123"

    def test_extract_from_model_dump_with_id(self, emitter):
        """Test extracting tool call ID using model_dump with 'id' field"""
        raw_item = SimpleNamespace()
        raw_item.model_dump = lambda: {"id": "test-call-456"}

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-456"

    def test_extract_from_attributes(self, emitter):
        """Test extracting tool call ID from attributes"""
        raw_item = SimpleNamespace()
        raw_item.call_id = "test-call-789"

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-789"

    def test_extract_from_id_attribute(self, emitter):
        """Test extracting tool call ID from id attribute"""
        raw_item = SimpleNamespace()
        raw_item.id = "test-call-abc"

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-abc"

    def test_extract_from_dict(self, emitter):
        """Test extracting tool call ID from dict"""
        raw_item = {"id": "test-call-def"}

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-def"

    def test_extract_from_dict_call_id(self, emitter):
        """Test extracting tool call ID from dict with call_id"""
        raw_item = {"call_id": "test-call-ghi"}

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "test-call-ghi"

    def test_extract_not_found(self, emitter):
        """Test extracting tool call ID when not found"""
        raw_item = {}

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "unknown"

    def test_extract_empty_namespace(self, emitter):
        """Test extracting from empty namespace"""
        raw_item = SimpleNamespace()

        tool_call_id = emitter._extract_tool_call_id(raw_item)

        assert tool_call_id == "unknown"


class TestExtractToolArgs:
    """Test tool arguments extraction"""

    @pytest.fixture
    def emitter(self):
        return SSEEventEmitter()

    def test_extract_from_json_string(self, emitter):
        """Test extracting args from JSON string"""
        raw_item = SimpleNamespace()
        raw_item.arguments = '{"key": "value", "num": 42}'

        args = emitter._extract_tool_args(raw_item)

        assert args == {"key": "value", "num": 42}

    def test_extract_from_dict(self, emitter):
        """Test extracting args from dict"""
        raw_item = SimpleNamespace()
        raw_item.arguments = {"key": "value"}

        args = emitter._extract_tool_args(raw_item)

        assert args == {"key": "value"}

    def test_extract_no_arguments(self, emitter):
        """Test extracting when no arguments attribute"""
        raw_item = SimpleNamespace()

        args = emitter._extract_tool_args(raw_item)

        assert args == {}

    def test_extract_invalid_json(self, emitter):
        """Test extracting from invalid JSON string"""
        raw_item = SimpleNamespace()
        raw_item.arguments = "not json"

        args = emitter._extract_tool_args(raw_item)

        assert args == {}


class TestExtractError:
    """Test error extraction from tool output"""

    @pytest.fixture
    def emitter(self):
        return SSEEventEmitter()

    def test_extract_error_from_attribute(self, emitter):
        """Test extracting error from attribute"""
        output = SimpleNamespace()
        output.error = "Something went wrong"

        error = emitter._extract_error(output)

        assert error == "Something went wrong"

    def test_extract_error_from_dict(self, emitter):
        """Test extracting error from dict"""
        output = {"error": "Dict error message"}

        error = emitter._extract_error(output)

        assert error == "Dict error message"

    def test_extract_no_error(self, emitter):
        """Test extracting when no error"""
        output = {"result": "success"}

        error = emitter._extract_error(output)

        assert error is None

    def test_extract_empty_error(self, emitter):
        """Test extracting when error is empty/falsy"""
        output = SimpleNamespace()
        output.error = ""

        error = emitter._extract_error(output)

        assert error is None


class TestConcurrentEventFlushing:
    """Test concurrent event flushing for real-time hook event emission."""

    @pytest.fixture
    def emitter(self):
        return SSEEventEmitter(agent_name="Test Agent")

    @pytest.fixture
    def emit_callback(self):
        """Create a simple emit callback that formats events as JSON"""

        def callback(event_type: str, data: dict) -> str:
            return json.dumps({"event": event_type, "data": data})

        return callback

    @pytest.mark.asyncio
    async def test_concurrent_flushing_processes_queue_during_await(
        self, emitter, emit_callback
    ):
        """Test that queued events are processed immediately during long operations."""
        queue = asyncio.Queue()

        async def slow_stream():
            """Simulate a hook that queues events during a long await."""
            event = SimpleNamespace()
            event.name = "start"
            yield event

            # Simulate hook behavior: queue event, then do long operation
            await queue.put(("context.summarizing", {"session_id": "test"}))
            await asyncio.sleep(0.3)  # Simulate summarization work
            await queue.put(("context.pruning_completed", {"session_id": "test"}))

            event2 = SimpleNamespace()
            event2.name = "end"
            yield event2

        events_received = []
        async for event_str, seq_num in emitter.process_stream_with_concurrent_flushing(
            stream_events=slow_stream(),
            emit_callback=emit_callback,
            sse_event_queue=queue,
            heartbeat_interval=1.0,  # Longer than our test
        ):
            events_received.append(json.loads(event_str))

        # Find the summarizing and pruning_completed events
        summarizing_events = [
            e for e in events_received if e["event"] == "context.summarizing"
        ]
        pruning_events = [
            e for e in events_received if e["event"] == "context.pruning_completed"
        ]

        assert len(summarizing_events) == 1, "Should have one summarizing event"
        assert len(pruning_events) == 1, "Should have one pruning_completed event"

    @pytest.mark.asyncio
    async def test_concurrent_flushing_with_heartbeats(self, emitter, emit_callback):
        """Test that heartbeats work correctly with concurrent flushing."""
        queue = asyncio.Queue()

        async def slow_stream():
            """Stream with long gap to trigger heartbeats."""
            event = SimpleNamespace()
            event.name = "start"
            yield event
            await asyncio.sleep(2.5)  # Long enough for 2+ heartbeats
            event2 = SimpleNamespace()
            event2.name = "end"
            yield event2

        events = []
        async for event_str, seq_num in emitter.process_stream_with_concurrent_flushing(
            stream_events=slow_stream(),
            emit_callback=emit_callback,
            sse_event_queue=queue,
            heartbeat_interval=1.0,
        ):
            events.append(json.loads(event_str))

        # Should have heartbeats
        heartbeat_events = [e for e in events if e["event"] == "agent.heartbeat"]
        assert (
            len(heartbeat_events) >= 2
        ), f"Expected at least 2 heartbeats, got {len(heartbeat_events)}"

    @pytest.mark.asyncio
    async def test_concurrent_flushing_handles_empty_queue(
        self, emitter, emit_callback
    ):
        """Test that concurrent flushing works fine with no queued events."""
        queue = asyncio.Queue()

        async def simple_stream():
            """Simple stream with no queued events."""
            for i in range(3):
                event = SimpleNamespace()
                event.name = f"event_{i}"
                yield event
                await asyncio.sleep(0.05)

        events = []
        async for event_str, seq_num in emitter.process_stream_with_concurrent_flushing(
            stream_events=simple_stream(),
            emit_callback=emit_callback,
            sse_event_queue=queue,
            heartbeat_interval=1.0,
        ):
            events.append(json.loads(event_str))

        # Should complete without error
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_concurrent_flushing_sequence_numbers(self, emitter, emit_callback):
        """Test that sequence numbers are correct across all event types."""
        queue = asyncio.Queue()

        async def mixed_stream():
            """Stream that will have SDK events, queued events, and heartbeats."""
            event = SimpleNamespace()
            event.name = "start"
            yield event

            await queue.put(("queued.event", {"msg": "first"}))
            await asyncio.sleep(1.5)  # Trigger heartbeat
            await queue.put(("queued.event", {"msg": "second"}))

            event2 = SimpleNamespace()
            event2.name = "end"
            yield event2

        sequence_numbers = []
        async for event_str, seq_num in emitter.process_stream_with_concurrent_flushing(
            stream_events=mixed_stream(),
            emit_callback=emit_callback,
            sse_event_queue=queue,
            heartbeat_interval=1.0,
        ):
            sequence_numbers.append(seq_num)

        # Verify sequence numbers are strictly increasing
        for i in range(1, len(sequence_numbers)):
            assert (
                sequence_numbers[i] > sequence_numbers[i - 1]
            ), f"Sequence numbers not strictly increasing: {sequence_numbers}"
