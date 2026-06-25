"""Unit tests for ContextManagerHooks functionality"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.context_manager.context_manager_hooks import (
    SUMMARIZATION_THRESHOLD,
    ContextManagerHooks,
    create_context_manager_hooks,
)


class TestContextManagerHooks:
    """Test cases for ContextManagerHooks class"""

    def test_initialization(self):
        """Test ContextManagerHooks initialization"""
        mock_session = Mock()
        hooks = ContextManagerHooks(
            "test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        assert hooks.session_id == "test-session"
        assert hooks.model_name == "gpt-4o"
        assert hooks.session is mock_session
        assert hooks._last_input_tokens == 0

    def test_initialization_without_model(self):
        """Test initialization without model name"""
        hooks = ContextManagerHooks("test-session")

        assert hooks.session_id == "test-session"
        assert hooks.model_name is None

    def test_initialization_with_callback(self):
        """Test initialization with SSE callback"""
        callback = Mock()
        hooks = ContextManagerHooks("test-session", emit_sse_callback=callback)

        assert hooks.emit_sse_callback is callback

    def test_initialization_with_initial_token_count(self):
        """Test initialization with initial token count"""
        hooks = ContextManagerHooks("test-session", initial_token_count=50000)

        assert hooks._last_input_tokens == 50000

    @pytest.mark.asyncio
    @patch(
        "app.services.context_manager.context_manager_hooks.TokenCounter.estimate_max_tokens"
    )
    async def test_on_start(self, mock_max_tokens):
        """Test on_start hook"""
        mock_max_tokens.return_value = 128000

        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")

        mock_context = Mock()
        mock_agent = Mock()
        mock_agent.name = "TestAgent"

        await hooks.on_start(mock_context, mock_agent)

        assert hooks._session_start_time is not None
        assert hooks._max_context_tokens == 128000

    @pytest.mark.asyncio
    async def test_on_end(self):
        """Test on_end hook"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")
        hooks._session_start_time = 1000.0
        hooks._last_input_tokens = 5000
        hooks._max_context_tokens = 128000

        mock_context = Mock()
        mock_context.usage = Mock(input_tokens=100, output_tokens=50)
        mock_agent = Mock()

        with patch("time.time", return_value=1010.0):
            await hooks.on_end(mock_context, mock_agent, "Final output")

        # Should complete without error

    @pytest.mark.asyncio
    @patch(
        "app.services.context_manager.context_manager_hooks.TokenCounter.estimate_max_tokens"
    )
    async def test_on_llm_end_emits_usage(self, mock_max_tokens):
        """Test on_llm_end emits usage event"""
        mock_max_tokens.return_value = 200000

        callback = Mock()
        hooks = ContextManagerHooks(
            "test-session", model_name="gpt-4o", emit_sse_callback=callback
        )

        mock_context = Mock()
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=50000, output_tokens=1000)

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Verify usage event was emitted
        callback.assert_called()
        call_args = callback.call_args_list[0]
        assert call_args[0][0] == "context.usage"
        assert call_args[0][1]["session_id"] == "test-session"

    @pytest.mark.asyncio
    @patch(
        "app.services.context_manager.context_manager_hooks.TokenCounter.estimate_max_tokens"
    )
    async def test_on_llm_end_triggers_pruning_flag(self, mock_max_tokens):
        """Test on_llm_end stores token count for threshold checking"""
        mock_max_tokens.return_value = 100000

        callback = Mock()
        hooks = ContextManagerHooks(
            "test-session", model_name="gpt-4o", emit_sse_callback=callback
        )

        mock_context = Mock()
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_response = Mock()
        # 95% usage - exceeds 90% threshold
        mock_response.usage = Mock(input_tokens=95000, output_tokens=1000)

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Token count should be stored for threshold checking
        # Now stores input + output tokens for accurate next-turn prediction
        assert hooks._last_input_tokens == 96000  # 95000 + 1000

        # Pruning decision is made in call_model_input_filter, not here

    @pytest.mark.asyncio
    async def test_on_llm_end_tracks_tokens(self):
        """Test on_llm_end tracks token usage for pre-turn check"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")
        hooks._max_context_tokens = 128000

        mock_context = Mock()
        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o")
        mock_response = Mock()
        mock_response.usage = Mock(input_tokens=50000, output_tokens=1000)

        await hooks.on_llm_end(mock_context, mock_agent, mock_response)

        # Verify tokens are tracked (input + output for accurate next-turn prediction)
        assert hooks._last_input_tokens == 51000  # 50000 + 1000

    @pytest.mark.asyncio
    async def test_on_tool_end(self):
        """Test on_tool_end hook"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")

        mock_context = Mock()
        mock_agent = Mock()
        mock_tool = Mock()
        mock_tool.name = "test_tool"

        await hooks.on_tool_end(mock_context, mock_agent, mock_tool, "result")

        # Tool end should complete without error

    @pytest.mark.asyncio
    @patch("app.services.context_manager.context_manager_hooks.summarize_conversation")
    async def test_call_model_input_filter_with_pruning(self, mock_summarize):
        """Test call_model_input_filter processes pruning when threshold exceeded"""
        mock_summarize.return_value = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        # Create a mock session for persistence
        mock_session = AsyncMock()
        mock_session.clear_session = AsyncMock()
        mock_session.add_items = AsyncMock()

        hooks = ContextManagerHooks(
            "test-session", session=mock_session, model_name="gpt-4o"
        )
        # Set high token count to trigger pruning (above 90% threshold)
        hooks._last_input_tokens = 120000

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "msg4"},
            {"role": "user", "content": "msg5"},
            {"role": "assistant", "content": "msg6"},
        ]

        mock_data = Mock()
        mock_data.model_data = mock_model_data
        mock_data.context = None

        result = await hooks.call_model_input_filter(mock_data)

        # Verify summarization was triggered
        mock_summarize.assert_called_once()

        # Verify session was cleared and pruned items persisted
        mock_session.clear_session.assert_called_once()
        mock_session.add_items.assert_called_once()

        # Token count should be reset after pruning
        assert hooks._last_input_tokens == 0

    @pytest.mark.asyncio
    async def test_call_model_input_filter_no_pruning(self):
        """Test call_model_input_filter passes through without pruning"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")

        mock_model_data = Mock()
        mock_model_data.instructions = "System prompt"
        mock_model_data.input = [{"role": "user", "content": "test"}]

        mock_data = Mock()
        mock_data.model_data = mock_model_data

        result = await hooks.call_model_input_filter(mock_data)

        assert result.instructions == "System prompt"
        assert len(list(result.input)) == 1

    def test_get_model_name_from_hook(self):
        """Test _get_model_name extracts model name correctly"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")

        # Test with hook's model_name
        assert hooks._get_model_name(None) == "gpt-4o"

    def test_get_model_name_from_agent(self):
        """Test _get_model_name extracts from agent when no hook model"""
        hooks = ContextManagerHooks("test-session")

        mock_agent = Mock()
        mock_agent.model = Mock(model="gpt-4o-mini")

        assert hooks._get_model_name(mock_agent) == "gpt-4o-mini"

    def test_get_model_name_default(self):
        """Test _get_model_name returns default"""
        hooks = ContextManagerHooks("test-session")

        assert hooks._get_model_name(None) == "gpt-4o"

    def test_get_item_role_dict(self):
        """Test _get_item_role extracts role from dict"""
        hooks = ContextManagerHooks("test-session")

        assert hooks._get_item_role({"role": "user"}) == "user"
        assert hooks._get_item_role({"role": "assistant"}) == "assistant"

    def test_get_item_role_object(self):
        """Test _get_item_role extracts role from object"""
        hooks = ContextManagerHooks("test-session")

        mock_item = Mock()
        mock_item.role = "system"
        assert hooks._get_item_role(mock_item) == "system"

    def test_extract_messages(self):
        """Test _extract_messages extracts messages correctly"""
        hooks = ContextManagerHooks("test-session")

        items = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "system", "content": "Instructions"},
        ]

        messages = hooks._extract_messages(items)

        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_format_summary_message(self):
        """Test _format_summary_message formats correctly"""
        hooks = ContextManagerHooks("test-session")

        summary_data = {
            "summary_text": "Test summary",
            "goals": ["Goal 1", "Goal 2"],
            "accomplishments": ["Done 1"],
            "most_recent_state": "Current state",
        }

        result = hooks._format_summary_message(summary_data, 10)

        assert "Test summary" in result
        assert "Goal 1" in result
        assert "Done 1" in result
        assert "Current state" in result
        assert "10 messages" in result

    def test_estimate_tokens(self):
        """Test _estimate_tokens provides reasonable estimates"""
        hooks = ContextManagerHooks("test-session", model_name="gpt-4o")

        # Test with simple messages
        items = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        estimated = hooks._estimate_tokens(items)

        # Should be a reasonable positive number
        assert estimated > 0

    def test_build_pruned_items(self):
        """Test _build_pruned_items creates correct structure"""
        hooks = ContextManagerHooks("test-session")

        items = [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "msg4"},
            {"role": "user", "content": "msg5"},
            {"role": "assistant", "content": "msg6"},
        ]

        summary_data = {
            "summary_text": "Test summary",
            "goals": [],
            "accomplishments": [],
            "most_recent_state": "",
        }

        pruned = hooks._build_pruned_items(items, summary_data)

        # Should have: system + assistant summary + user continue message
        assert len(pruned) == 3
        assert pruned[0]["role"] == "system"  # System first
        assert pruned[1]["role"] == "assistant"  # Assistant summary second
        assert "summary" in pruned[1]["content"].lower()  # Summary content
        assert pruned[2]["role"] == "user"  # User continue message third
        assert "continue" in pruned[2]["content"].lower()  # Continue message

    def test_create_context_manager_hooks(self):
        """Test the factory function"""
        mock_session = Mock()
        hooks = create_context_manager_hooks(
            "test-session",
            session=mock_session,
            model_name="gpt-4o",
        )

        assert isinstance(hooks, ContextManagerHooks)
        assert hooks.session_id == "test-session"
        assert hooks.session is mock_session
        assert hooks.model_name == "gpt-4o"

    def test_create_context_manager_hooks_with_callback(self):
        """Test factory function with callback"""
        callback = Mock()
        hooks = create_context_manager_hooks("test-session", emit_sse_callback=callback)

        assert isinstance(hooks, ContextManagerHooks)
        assert hooks.emit_sse_callback is callback

    def test_create_context_manager_hooks_with_initial_tokens(self):
        """Test factory function with initial token count"""
        hooks = create_context_manager_hooks(
            "test-session",
            initial_token_count=75000,
        )

        assert isinstance(hooks, ContextManagerHooks)
        assert hooks._last_input_tokens == 75000


class TestContextManagerConstants:
    """Test constants are defined correctly"""

    def test_summarization_threshold(self):
        """Test summarization threshold is reasonable"""
        assert 0.8 <= SUMMARIZATION_THRESHOLD <= 0.95
