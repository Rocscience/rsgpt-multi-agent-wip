"""Integration tests for Context Pruning and Summarization.

These tests verify the complete flow of context window management:
1. Token tracking across turns
2. Post-turn threshold detection
3. Pre-turn threshold detection for large inputs
4. Session persistence of pruned history
5. Summary creation and formatting
6. SSE event emission
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from agents.run import CallModelData, ModelInputData

from app.services.context_manager.context_manager_hooks import (
    SUMMARIZATION_THRESHOLD,
    ContextManagerHooks,
    create_context_manager_hooks,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock SDK session that tracks calls."""
    session = AsyncMock()
    session.session_id = "test-session-123"
    session.clear_session = AsyncMock()
    session.add_items = AsyncMock()
    session.get_items = AsyncMock(return_value=[])
    return session


@pytest.fixture
def mock_sse_callback():
    """Create a mock SSE callback that records events."""
    callback = Mock()
    callback.events = []

    def record_event(event_type, data):
        callback.events.append({"type": event_type, "data": data})

    callback.side_effect = record_event
    return callback


@pytest.fixture
def sample_conversation_items():
    """Generate a sample conversation with many messages."""
    items = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(20):
        items.append({"role": "user", "content": f"User message {i}: " + "x" * 100})
        items.append(
            {"role": "assistant", "content": f"Assistant response {i}: " + "y" * 200}
        )
    return items


@pytest.fixture
def large_input_item():
    """Create a large user input that would trigger pre-turn pruning."""
    return {"role": "user", "content": "Analyze this: " + "z" * 50000}


# =============================================================================
# Test: Normal Turn (No Pruning)
# =============================================================================


class TestNormalTurnNoPruning:
    """Test normal operation when context is below threshold."""

    @pytest.mark.asyncio
    async def test_no_pruning_when_below_threshold(
        self, mock_session, mock_sse_callback
    ):
        """Verify no pruning occurs when usage is below threshold."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        hooks._max_context_tokens = 128000

        # Simulate LLM response with low usage (~10%)
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=12800, output_tokens=500)
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_context = Mock()

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Verify tokens tracked (input + output for accurate next-turn prediction)
        assert hooks._last_input_tokens == 13300  # 12800 + 500

        # Verify usage event was emitted
        usage_events = [
            e for e in mock_sse_callback.events if e["type"] == "context.usage"
        ]
        assert len(usage_events) == 1
        assert usage_events[0]["data"]["usage_percentage"] == pytest.approx(
            10.0, rel=0.1
        )

    @pytest.mark.asyncio
    async def test_passthrough_when_no_pruning_needed(self, mock_session):
        """Verify input is passed through unchanged when no pruning needed."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        input_items = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        # Input should be unchanged
        assert len(list(result.input)) == 3
        assert result.instructions == "System prompt"

        # Session should not have been cleared
        mock_session.clear_session.assert_not_called()


# =============================================================================
# Test: Post-Turn Threshold Detection
# =============================================================================


class TestPostTurnThresholdDetection:
    """Test threshold detection after LLM calls."""

    @pytest.mark.asyncio
    async def test_token_tracking_on_llm_end(self, mock_session, mock_sse_callback):
        """Verify on_llm_end tracks tokens and emits usage event."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        hooks._max_context_tokens = 100000

        # Simulate LLM response with ~92% usage (above 90% threshold)
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=92000, output_tokens=1000)
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_context = Mock()

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Verify tokens were tracked (input + output for accurate next-turn prediction)
        assert hooks._last_input_tokens == 93000  # 92000 + 1000

        # Verify usage event was emitted
        usage_events = [
            e for e in mock_sse_callback.events if e["type"] == "context.usage"
        ]
        assert len(usage_events) == 1
        assert usage_events[0]["data"]["usage_percentage"] == pytest.approx(
            92.0, rel=0.1
        )

    @pytest.mark.asyncio
    async def test_no_duplicate_scheduling(self, mock_session, mock_sse_callback):
        """Verify pruning is not re-scheduled if already scheduled."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        hooks._max_context_tokens = 100000

        # Simulate another LLM response
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=95000, output_tokens=1000)
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_context = Mock()

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Should still be scheduled, but no new event

        # Only usage event, no new pruning_scheduled
        scheduled_events = [
            e
            for e in mock_sse_callback.events
            if e["type"] == "context.pruning_scheduled"
        ]
        assert len(scheduled_events) == 0


# =============================================================================
# Test: Pre-Turn Threshold Detection (Large Inputs)
# =============================================================================


class TestPreTurnThresholdDetection:
    """Test threshold detection before LLM calls for large inputs."""


# =============================================================================
# Test: Pruning Execution and Session Persistence
# =============================================================================


class TestPruningExecution:
    """Test the actual pruning execution and session persistence."""

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_pruning_clears_and_persists_session(
        self, mock_summarize, mock_session, mock_sse_callback
    ):
        """Verify pruning clears session and persists pruned items."""
        mock_summarize.return_value = {
            "summary_text": "Previous conversation about testing.",
            "goals": ["Test the feature"],
            "accomplishments": ["Wrote tests"],
            "most_recent_state": "Running integration tests",
        }

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        # Set high token count to trigger pruning (above 90% threshold)
        hooks._last_input_tokens = 120000

        # Create input with many messages
        input_items = [{"role": "system", "content": "System instructions"}]
        for i in range(10):
            input_items.append({"role": "user", "content": f"Message {i}"})
            input_items.append({"role": "assistant", "content": f"Response {i}"})
        input_items.append({"role": "user", "content": "Current message"})

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        # Verify session was cleared
        mock_session.clear_session.assert_called_once()

        # Verify pruned items were persisted
        mock_session.add_items.assert_called_once()
        persisted_items = mock_session.add_items.call_args[0][0]

        # Should have: system + assistant summary + user continue message
        # (excluding current user message which SDK adds)
        assert len(persisted_items) == 3
        assert any("system" in str(item) for item in persisted_items)
        assert any("assistant" in str(item) for item in persisted_items)
        assert any("continue" in str(item) for item in persisted_items)

        # Verify pruning completed event
        completed_events = [
            e
            for e in mock_sse_callback.events
            if e["type"] == "context.pruning_completed"
        ]
        assert len(completed_events) == 1

        # Verify flag was cleared

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_pruned_output_structure(self, mock_summarize, mock_session):
        """Verify the structure of pruned output is correct."""
        mock_summarize.return_value = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )
        # Set high token count to trigger pruning (above 90% threshold)
        hooks._last_input_tokens = 120000

        # Create input with system + many conversation items
        input_items = [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "Old message 1"},
            {"role": "assistant", "content": "Old response 1"},
            {"role": "user", "content": "Old message 2"},
            {"role": "assistant", "content": "Old response 2"},
            {"role": "user", "content": "Recent message 1"},
            {"role": "assistant", "content": "Recent response 1"},
            {"role": "user", "content": "Recent message 2"},
            {"role": "assistant", "content": "Recent response 2"},
            {
                "role": "user",
                "content": "Current message",
            },  # Will be excluded from persist
        ]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        # Result should have: system + assistant summary + user continue message
        result_items = list(result.input)

        # First item should be system
        assert result_items[0]["role"] == "system"

        # Second item should be assistant summary
        assert result_items[1]["role"] == "assistant"
        assert "summary" in result_items[1]["content"].lower()

        # Third item should be user continue message
        assert result_items[2]["role"] == "user"
        assert "continue" in result_items[2]["content"].lower()

        # Should have exactly: system + assistant summary + user continue message
        assert len(result_items) == 3


# =============================================================================
# Test: Summary Creation
# =============================================================================


class TestSummaryCreation:
    """Test summary creation functionality."""

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_summary_includes_all_required_fields(
        self, mock_summarize, mock_session
    ):
        """Verify summary message includes all required fields."""
        mock_summarize.return_value = {
            "summary_text": "User discussed geotechnical modeling.",
            "goals": ["Create slope model", "Run stability analysis"],
            "accomplishments": ["Imported geometry", "Set material properties"],
            "most_recent_state": "Ready to run analysis",
        }

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        input_items = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]

        summary_data = await hooks._create_summary(input_items)

        # Format the summary message
        formatted = hooks._format_summary_message(summary_data, 10)

        # Verify all fields are included
        assert "geotechnical modeling" in formatted
        assert "Create slope model" in formatted
        assert "Imported geometry" in formatted
        assert "Ready to run analysis" in formatted
        assert "10 messages" in formatted

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_fallback_summary_on_error(self, mock_summarize, mock_session):
        """Verify fallback summary is created when summarization fails."""
        mock_summarize.side_effect = Exception("API Error")

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        input_items = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
        ]

        summary_data = await hooks._create_summary(input_items)

        # Should have fallback summary
        assert "summary_text" in summary_data
        assert "2 user messages" in summary_data["summary_text"]
        assert "1 assistant response" in summary_data["summary_text"]


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_no_session_skips_pruning(self, mock_sse_callback):
        """Verify pruning is skipped gracefully when no session."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=None,  # No session
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )

        input_items = [{"role": "user", "content": "test"}]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        # Should pass through unchanged
        assert len(list(result.input)) == 1

        # Flag should remain (can't clear without session)
        # But no error should occur

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_session_persistence_error_continues(
        self, mock_summarize, mock_session, mock_sse_callback
    ):
        """Verify turn continues even if session persistence fails."""
        mock_summarize.return_value = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        # Make clear_session fail
        mock_session.clear_session.side_effect = Exception("DB Error")

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        # Set high token count to trigger pruning (above 90% threshold)
        hooks._last_input_tokens = 120000

        input_items = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "current"},
        ]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        # Should not raise - error is caught
        result = await hooks.call_model_input_filter(mock_data)

        # Should have attempted pruning and emitted error event
        error_events = [
            e for e in mock_sse_callback.events if e["type"] == "context.pruning_error"
        ]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_empty_input_handling(self, mock_session):
        """Verify empty input is handled gracefully."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = []

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        assert len(list(result.input)) == 0
        mock_session.clear_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_only_system_messages(self, mock_session):
        """Verify handling when only system messages present."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        # Only system messages - nothing to summarize
        input_items = [
            {"role": "system", "content": "Instructions 1"},
            {"role": "system", "content": "Instructions 2"},
        ]

        pruned = hooks._build_pruned_items(
            input_items,
            {
                "summary_text": "",
                "goals": [],
                "accomplishments": [],
                "most_recent_state": "",
            },
        )

        # Should keep system messages, no summary added (nothing summarized)
        assert len(pruned) == 2
        assert all(item["role"] == "system" for item in pruned)


# =============================================================================
# Test: Token Tracking Across Turns
# =============================================================================


class TestTokenTrackingAcrossTurns:
    """Test token tracking persists correctly across turns."""

    @pytest.mark.asyncio
    async def test_token_tracking_accumulates(self, mock_session, mock_sse_callback):
        """Verify tokens are tracked across multiple LLM calls."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        hooks._max_context_tokens = 100000

        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_context = Mock()

        # Turn 1: ~20% usage (input + output for accurate next-turn prediction)
        mock_response_1 = Mock()
        mock_response_1.usage = Mock(input_tokens=20000, output_tokens=500)
        await hooks.on_llm_end(mock_context, mock_agent, mock_response_1)
        assert hooks._last_input_tokens == 20500  # 20000 + 500

        # Turn 2: ~50% usage
        mock_response_2 = Mock()
        mock_response_2.usage = Mock(input_tokens=50000, output_tokens=500)
        await hooks.on_llm_end(mock_context, mock_agent, mock_response_2)
        assert hooks._last_input_tokens == 50500  # 50000 + 500

        # Turn 3: ~85% usage - still below threshold
        mock_response_3 = Mock()
        mock_response_3.usage = Mock(input_tokens=85000, output_tokens=500)
        await hooks.on_llm_end(mock_context, mock_agent, mock_response_3)
        assert hooks._last_input_tokens == 85500  # 85000 + 500

        # Turn 4: ~92% usage - exceeds threshold
        mock_response_4 = Mock()
        mock_response_4.usage = Mock(input_tokens=92000, output_tokens=500)
        await hooks.on_llm_end(mock_context, mock_agent, mock_response_4)
        assert hooks._last_input_tokens == 92500  # 92000 + 500

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_token_tracking_resets_after_pruning(
        self, mock_summarize, mock_session, mock_sse_callback
    ):
        """Verify token tracking resets after successful pruning."""
        mock_summarize.return_value = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        # Set max tokens so 92K is above 90% threshold
        hooks._max_context_tokens = 100000
        hooks._last_input_tokens = 92000

        input_items = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "current"},
        ]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        await hooks.call_model_input_filter(mock_data)

        # Token tracking should be reset after pruning
        assert hooks._last_input_tokens == 0


# =============================================================================
# Test: SSE Event Emission
# =============================================================================


class TestSSEEventEmission:
    """Test SSE events are emitted correctly."""

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_full_pruning_event_sequence(
        self, mock_summarize, mock_session, mock_sse_callback
    ):
        """Verify the complete sequence of SSE events during pruning."""
        mock_summarize.return_value = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
        )
        hooks._max_context_tokens = 100000

        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_context = Mock()

        # Step 1: LLM call that tracks tokens
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=92000, output_tokens=500)
        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Should have: usage event
        assert len(mock_sse_callback.events) == 1
        assert mock_sse_callback.events[0]["type"] == "context.usage"

        # Step 2: Next turn triggers pruning (threshold check happens in call_model_input_filter)
        mock_sse_callback.events.clear()

        input_items = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "current"},
        ]

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = input_items

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        await hooks.call_model_input_filter(mock_data)

        # Should have: pruning_scheduled + summarizing + pruning_completed events
        event_types = [e["type"] for e in mock_sse_callback.events]
        assert "context.pruning_scheduled" in event_types
        assert "context.summarizing" in event_types
        assert "context.pruning_completed" in event_types


# =============================================================================
# Test: Build Pruned Items
# =============================================================================


class TestBuildPrunedItems:
    """Test the _build_pruned_items method in detail."""

    def test_preserves_system_messages(self, mock_session):
        """Verify system messages are always preserved."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        items = [
            {"role": "system", "content": "System 1"},
            {"role": "system", "content": "System 2"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]

        summary_data = {
            "summary_text": "Test",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        pruned = hooks._build_pruned_items(items, summary_data)

        # Both system messages should be preserved
        system_count = sum(1 for item in pruned if item.get("role") == "system")
        assert system_count == 2

    def test_keeps_recent_messages(self, mock_session):
        """Verify correct number of recent messages are kept."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        items = [{"role": "system", "content": "System"}]
        for i in range(10):
            items.append({"role": "user", "content": f"msg{i}"})
            items.append({"role": "assistant", "content": f"resp{i}"})

        summary_data = {
            "summary_text": "Test",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        pruned = hooks._build_pruned_items(items, summary_data)

        # Count non-system, non-summary items
        conversation_items = [
            item
            for item in pruned
            if item.get("role") != "system"
            and "summary" not in str(item.get("content", "")).lower()
        ]

        # Should have the user "please continue" message
        assert len(conversation_items) == 1
        assert conversation_items[0]["role"] == "user"
        assert "continue" in conversation_items[0]["content"].lower()

    def test_summary_added_when_conversation_items_exist(self, mock_session):
        """Verify summary is added when there are conversation items."""
        hooks = ContextManagerHooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        # Test with conversation items
        items = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]

        summary_data = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        pruned = hooks._build_pruned_items(items, summary_data)

        # Summary should be added since there are conversation items
        summary_items = [
            item for item in pruned if "summary" in str(item.get("content", "")).lower()
        ]
        assert len(summary_items) == 1


# =============================================================================
# Test: Factory Function
# =============================================================================


class TestFactoryFunction:
    """Test the create_context_manager_hooks factory function."""

    def test_creates_hooks_with_all_parameters(self, mock_session, mock_sse_callback):
        """Verify factory creates hooks with all parameters."""
        hooks = create_context_manager_hooks(
            session_id="test-session",
            session=mock_session,
            model_name="gpt-4o",
            emit_sse_callback=mock_sse_callback,
            initial_token_count=50000,
        )

        assert hooks.session_id == "test-session"
        assert hooks.session is mock_session
        assert hooks.model_name == "gpt-4o"
        assert hooks.emit_sse_callback is mock_sse_callback
        assert hooks._last_input_tokens == 50000

    def test_creates_hooks_with_minimal_parameters(self):
        """Verify factory works with minimal parameters."""
        hooks = create_context_manager_hooks(session_id="test-session")

        assert hooks.session_id == "test-session"
        assert hooks.session is None
        assert hooks.model_name is None
        assert hooks.emit_sse_callback is None
        assert hooks._last_input_tokens == 0
