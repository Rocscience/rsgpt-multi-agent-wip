"""Context Manager Hooks for OpenAI Agent SDK

Session-aware hooks that integrate with the OpenAI Agent SDK lifecycle
for context management, token tracking, and automatic pruning.

Key features:
1. Track token usage after each LLM call (stored for next turn's check)
2. Fast threshold check before LLM call using stored token count
3. Trigger summarization and persist pruned history to SDK session
4. Emit SSE events for frontend visibility
5. Persist token counts to database for cross-request durability

Token count flow:
- Initial count loaded from DB (includes user input estimate)
- Before LLM call: check stored count against threshold (fast O(1))
- After each LLM call (on_llm_end): store input + output tokens
  (output from this turn becomes context input for next turn)
- Note: on_llm_end receives per-call usage, not cumulative
- Fallback estimation only used when stored count is 0
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents import Agent, AgentHooks, ModelResponse, Tool
from agents.extensions.memory import SQLAlchemySession
from agents.items import TResponseInputItem
from agents.run import CallModelData, ModelInputData
from agents.run_context import RunContextWrapper
from agents.usage import Usage
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentContext
from app.services.agent.summarizer_agent import summarize_conversation
from app.services.context_manager.token_counter import TokenCounter

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Summarization threshold (90% of context window)
SUMMARIZATION_THRESHOLD = 0.90


# =============================================================================
# Context Manager Hooks
# =============================================================================


class ContextManagerHooks(AgentHooks):
    """
    Agent hooks for session-aware context management with automatic pruning.

    Key responsibilities:
    1. Track token usage after each LLM call (input + output tokens)
    2. Fast threshold check before LLM call using stored token count
    3. Trigger summarization when context window is near capacity
    4. Persist pruned history to SDK session
    5. Emit SSE events for frontend visibility

    The stored token count (_last_input_tokens) represents the estimated context
    size for the NEXT turn (input + output from last LLM call, since output
    becomes context input for the next turn). This is initialized from the
    database for fast pre-run threshold checking.
    """

    def __init__(
        self,
        session_id: str,
        session: Optional[SQLAlchemySession] = None,
        model_name: Optional[str] = None,
        emit_sse_callback: Optional[Callable] = None,
        initial_token_count: int = 0,
    ):
        """
        Initialize context manager hooks.

        Args:
            session_id: Unique identifier for the chat session
            session: SDK session for persisting pruned history (optional)
            model_name: Model name for token counting
            emit_sse_callback: Callback to emit SSE events
            initial_token_count: Initial token count (can be loaded from DB)
        """
        self.session_id = session_id
        self.session = session
        self.model_name = model_name
        self.emit_sse_callback = emit_sse_callback

        # Session state
        self._session_start_time: Optional[float] = None

        # Token tracking for threshold checking
        # This stores the estimated context size for the NEXT turn:
        # input_tokens + output_tokens from the last LLM call
        # (output becomes part of context for next turn)
        self._last_input_tokens: int = initial_token_count
        self._max_context_tokens: int = 0

        logger.debug(f"[{session_id[:8]}] Context hooks initialized")

    # =========================================================================
    # Main Hook Methods
    # =========================================================================

    async def on_start(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
    ) -> None:
        """Called before the agent is invoked."""
        try:
            self._session_start_time = time.time()

            # Initialize max context tokens based on model
            model_name = self._get_model_name(agent)
            try:
                self._max_context_tokens = TokenCounter.estimate_max_tokens(model_name)
            except ValueError:
                # Model not in config, use default
                self._max_context_tokens = 128000
                logger.warning(
                    f"Model '{model_name}' not in config, using default 128K context"
                )

            logger.debug(
                f"[{self.session_id[:8]}] Session started: model={model_name}, "
                f"max_tokens={self._max_context_tokens:,}"
            )

        except Exception as e:
            logger.error(f"Error in on_start: {e}")

    async def call_model_input_filter(self, data: CallModelData) -> ModelInputData:
        """
        Filter called immediately before the LLM is invoked.

        Three responsibilities:
        1. SANITIZE: Replace fake IDs with proper rs-prefixed IDs for cross-model compatibility
        2. THRESHOLD CHECK: Check if context exceeds threshold using stored token count
        3. EXECUTE: Perform pruning if threshold exceeded

        Args:
            data: CallModelData with agent, context, and model_data

        Returns:
            ModelInputData (possibly modified with summary)
        """
        try:
            model_data = data.model_data
            system_prompt = model_data.instructions
            input_items = list(model_data.input)

            # =====================================================
            # STEP 0: SANITIZE for OpenAI compatibility (if needed)
            # =====================================================
            # Only sanitize when targeting OpenAI - removes thinking blocks
            # and fixes fake IDs that OpenAI rejects
            # IMPORTANT: Do NOT sanitize for Anthropic - it removes thinking blocks
            # which causes API errors on multi-turn conversations with extended thinking
            if self._is_openai_model():
                input_items = self._sanitize_items_for_openai(input_items)

            # =====================================================
            # STEP 1: THRESHOLD CHECK
            # =====================================================
            # Check if pruning is needed using the stored token count
            # This is fast since we use the exact value from the last LLM call
            needs_pruning = False
            if self.session:
                needs_pruning = self._check_threshold_exceeded()

                # Fallback: If no token count available (shouldn't happen normally),
                # estimate from input items
                if not needs_pruning and self._last_input_tokens == 0:
                    logger.debug("No stored token count, falling back to estimation")
                    needs_pruning = await self._estimate_threshold_check(input_items)

            # =====================================================
            # STEP 2: EXECUTE PRUNING (if threshold exceeded)
            # =====================================================
            if needs_pruning and self.session:
                logger.info(
                    f"[{self.session_id[:8]}] Pruning context ({len(input_items)} items)"
                )

                # Emit summarizing event
                if self.emit_sse_callback:
                    self.emit_sse_callback(
                        "context.summarizing",
                        {
                            "session_id": self.session_id,
                            "message_count": len(input_items),
                        },
                    )

                # 1. Create summary of current items
                summary_data = await self._create_summary(input_items)

                # 2. Build pruned items
                pruned_items = self._build_pruned_items(input_items, summary_data)

                # 3. Persist to session (CRITICAL!)
                await self._persist_pruned_session(pruned_items)

                # 4. Reset token tracking after pruning
                self._last_input_tokens = 0  # Reset after pruning

                # 5. Return pruned items for this LLM call
                logger.info(
                    f"[{self.session_id[:8]}] Pruned: {len(input_items)} \
                    -> {len(pruned_items)} items"
                )

                return ModelInputData(input=pruned_items, instructions=system_prompt)

            return ModelInputData(input=input_items, instructions=system_prompt)

        except Exception as e:
            logger.error(f"Error in call_model_input_filter: {e}", exc_info=True)
            return data.model_data

    async def on_llm_end(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        response: ModelResponse,
    ) -> None:
        """
        Called immediately after the LLM call returns.

        Tracks tokens for next turn's threshold check.
        """
        try:
            # CRITICAL: Store token usage for next turn's threshold check
            # This exact value is used directly in call_model_input_filter
            self._track_token_usage(response, agent)

            # Emit usage event using already-computed values
            self._emit_usage_event()

        except Exception as e:
            logger.error(f"Error in on_llm_end: {e}")

    async def on_tool_end(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        tool: Tool,
        result: str,
    ) -> None:
        """Called after a tool is invoked. Currently just logs."""
        try:
            tool_name = getattr(tool, "name", "unknown")
            logger.debug(f"Tool completed: {tool_name}")
        except Exception as e:
            logger.error(f"Error in on_tool_end: {e}")

    async def on_end(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        output: Any,
    ) -> None:
        """Called when the agent produces final output."""
        try:
            duration = time.time() - (self._session_start_time or time.time())
            logger.debug(
                f"[{self.session_id[:8]}] Session ended: {duration:.2f}s, "
                f"tokens={self._last_input_tokens:,}/{self._max_context_tokens:,}"
            )

        except Exception as e:
            logger.error(f"Error in on_end: {e}")

    # =========================================================================
    # Token Tracking
    # =========================================================================

    def _track_token_usage(
        self,
        response: ModelResponse,
        agent: Agent[AgentContext],
    ) -> None:
        """
        Store token usage for pre-turn threshold checking.

        This is called after each LLM call to track the actual token usage.
        Also schedules async persistence to database.

        NOTE: on_llm_end is called after EACH individual LLM call, so
        response.usage represents THIS call's usage (not cumulative).
        The cumulative Usage with request_usage_entries is only available
        on RunResult.context_wrapper.usage after the run completes.

        We track input_tokens + output_tokens because the output from this
        turn will be part of the context window for the next turn.
        """
        if not (hasattr(response, "usage") and response.usage):
            return

        usage: Usage = response.usage
        model_name = self._get_model_name(agent)

        # on_llm_end is per-call, so usage.input_tokens/output_tokens
        # represent THIS call's usage (not cumulative)
        input_tokens: int = usage.input_tokens
        output_tokens: int = usage.output_tokens

        # Store input + output tokens for next call_model_input_filter
        # The output from this turn becomes input context for the next turn
        context_tokens = input_tokens + output_tokens
        logger.info(
            f"[{self.session_id[:8]}] Context tokens: {context_tokens:,} "
            f"[input={input_tokens:,}, output={output_tokens:,}]"
        )
        self._last_input_tokens = context_tokens

        # Update max tokens if not already set
        if self._max_context_tokens == 0:
            try:
                self._max_context_tokens = TokenCounter.estimate_max_tokens(model_name)
            except ValueError:
                self._max_context_tokens = 128000

        logger.debug(
            f"[{self.session_id[:8]}] Token usage: {context_tokens:,}/{self._max_context_tokens:,} "
            f"({context_tokens / self._max_context_tokens * 100:.1f}%)"
        )

        # Note: Database persistence is handled by persist_token_count() called from
        # orchestration service after the run completes

    def _check_threshold_exceeded(self) -> bool:
        """
        Check if stored token count exceeds the summarization threshold.

        This is the primary check using the exact token count from the last LLM call
        (stored in _last_input_tokens). Fast O(1) check with no estimation needed.

        Returns:
            True if threshold exceeded and pruning is needed
        """
        if self._last_input_tokens == 0:
            return False

        max_tokens = self._max_context_tokens
        if max_tokens == 0:
            model_name = self.model_name or "gpt-4o"
            try:
                max_tokens = TokenCounter.estimate_max_tokens(model_name)
                self._max_context_tokens = max_tokens
            except ValueError:
                max_tokens = 128000
                self._max_context_tokens = max_tokens

        if max_tokens == 0:
            return False

        usage_ratio = self._last_input_tokens / max_tokens

        logger.debug(
            f"[{self.session_id[:8]}] Threshold check: {self._last_input_tokens:,}/{max_tokens:,} "
            f"({usage_ratio:.1%})"
        )

        if usage_ratio >= SUMMARIZATION_THRESHOLD:
            logger.warning(
                f"[{self.session_id[:8]}] Threshold exceeded: {usage_ratio:.1%} >= "
                f"{SUMMARIZATION_THRESHOLD:.0%}"
            )

            if self.emit_sse_callback:
                self.emit_sse_callback(
                    "context.pruning_scheduled",
                    {
                        "session_id": self.session_id,
                        "input_tokens": self._last_input_tokens,
                        "max_tokens": max_tokens,
                        "usage_percentage": usage_ratio * 100,
                        "threshold_percentage": SUMMARIZATION_THRESHOLD * 100,
                        "reason": "threshold_exceeded",
                    },
                )
            return True

        return False

    async def _estimate_threshold_check(
        self,
        input_items: List[TResponseInputItem],
    ) -> bool:
        """
        Fallback: Estimate if current input would exceed threshold.

        Only used when _last_input_tokens is 0 (e.g., first turn of a session).
        This is slower than _check_threshold_exceeded since it requires estimation.

        Returns:
            True if threshold exceeded and pruning is needed
        """
        # Estimate tokens for current input
        estimated_context = self._estimate_tokens(input_items)

        max_tokens = self._max_context_tokens
        if max_tokens == 0:
            model_name = self.model_name or "gpt-4o"
            try:
                max_tokens = TokenCounter.estimate_max_tokens(model_name)
            except ValueError:
                max_tokens = 128000

        if max_tokens == 0:
            return False

        usage_ratio = estimated_context / max_tokens

        logger.debug(
            f"Fallback estimate check: ~{estimated_context:,} / {max_tokens:,} "
            f"({usage_ratio:.1%})"
        )

        if usage_ratio >= SUMMARIZATION_THRESHOLD:
            logger.warning(
                f"[{self.session_id[:8]}] Estimated threshold exceeded: {usage_ratio:.1%}"
            )

            if self.emit_sse_callback:
                self.emit_sse_callback(
                    "context.pruning_scheduled",
                    {
                        "session_id": self.session_id,
                        "estimated_tokens": estimated_context,
                        "max_tokens": max_tokens,
                        "usage_percentage": usage_ratio * 100,
                        "threshold_percentage": SUMMARIZATION_THRESHOLD * 100,
                        "reason": "fallback_estimation",
                    },
                )
            return True

        return False

    def _estimate_tokens(self, items: List[TResponseInputItem]) -> int:
        """
        Estimate token count for a list of items.

        Uses tiktoken for accurate counting when possible, falls back to
        character-based estimation.
        """
        # Try to use accurate tiktoken counting
        model_name = self.model_name or "gpt-5"
        messages = self._extract_messages(items)

        if messages:
            try:
                return TokenCounter.count_tokens_in_messages(messages, model_name)
            except ValueError:
                # Model not supported, fall back to estimation
                pass

        # Fallback: character-based estimation
        total_chars = 0
        for item in items:
            content = self._extract_content(item)
            if content:
                total_chars += len(content)

        # Rough estimate: 4 chars per token + 10% overhead for structure
        estimated_tokens = int((total_chars / 4) * 1.1)
        return estimated_tokens

    # =========================================================================
    # Usage Event Emission
    # =========================================================================

    def _emit_usage_event(self) -> None:
        """Emit context.usage SSE event using already-computed token values."""
        try:
            if not self.emit_sse_callback or self._last_input_tokens == 0:
                return

            max_tokens = self._max_context_tokens
            if max_tokens == 0:
                return

            usage_pct = self._last_input_tokens / max_tokens * 100

            self.emit_sse_callback(
                "context.usage",
                {
                    "session_id": self.session_id,
                    "total_tokens": self._last_input_tokens,
                    "max_tokens": max_tokens,
                    "usage_percentage": usage_pct,
                    "model_name": self.model_name or "gpt-4o",
                },
            )
            logger.debug(
                f"[{self.session_id[:8]}] Emitted context.usage: {usage_pct:.1f}%"
            )

        except Exception as e:
            logger.error(f"Error emitting usage event: {e}")

    # =========================================================================
    # Summarization
    # =========================================================================

    async def _create_summary(
        self,
        input_items: List[TResponseInputItem],
    ) -> Dict[str, Any]:
        """
        Create summary using summarizer agent.

        IMPORTANT: This is a standalone agent run, NOT using the main session.
        We don't want summarization messages in the conversation history.
        """
        try:
            logger.debug(
                f"[{self.session_id[:8]}] Summarizing {len(input_items)} items"
            )

            # Sanitize items for OpenAI (summarizer uses gpt-5-mini)
            sanitized_items = self._sanitize_items_for_openai(input_items)

            # Run summarizer with sanitized items
            summary_data = await summarize_conversation(
                messages=sanitized_items,
                model="xai/grok-4-1-fast-reasoning",
            )

            return summary_data

        except Exception as e:
            logger.error(f"[{self.session_id[:8]}] Summarization error: {e}")
            # Return fallback summary so pruning can still proceed
            return self._create_fallback_summary(self._extract_messages(input_items))

    def _create_fallback_summary(self, messages: List[Dict]) -> Dict[str, Any]:
        """Create basic fallback summary when LLM summarization fails."""
        logger.warning(f"[{self.session_id[:8]}] Using fallback summary")

        user_count = sum(1 for m in messages if m.get("role") == "user")
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

        return {
            "summary_text": (
                f"Previous conversation with {user_count} user messages and "
                f"{assistant_count} assistant responses."
            ),
            "goals": ["Continue assisting the user"],
            "tool_calls": [],
            "key_insights": [],
            "most_recent_state": "Conversation in progress",
        }

    def _build_pruned_items(
        self,
        items: List[TResponseInputItem],
        summary_data: Dict[str, Any],
    ) -> List[TResponseInputItem]:
        """
        Build pruned item list with summary only.

        Strategy:
        - Keep system messages (instructions)
        - Replace entire conversation with comprehensive summary
        - No recent messages kept (summary includes tool calls and key insights)
        """
        pruned: List[TResponseInputItem] = []

        # Categorize items
        system_msgs: List[TResponseInputItem] = []
        conversation_items: List[TResponseInputItem] = []

        for item in items:
            role = self._get_item_role(item)
            if role == "system":
                system_msgs.append(item)
            else:
                conversation_items.append(item)

        # Keep system messages
        pruned.extend(system_msgs)

        # All conversation items are summarized
        summarized_count = len(conversation_items)

        # Add summary as assistant message + user "please continue"
        # This prevents the model from treating the summary as something to respond to.
        if summarized_count > 0:
            summary_content = self._format_summary_message(
                summary_data, summarized_count
            )
            # Assistant acknowledges having the context
            assistant_msg: TResponseInputItem = {
                "role": "assistant",
                "content": f"[Previous conversation context loaded]\n\n{summary_content}",
            }
            pruned.append(assistant_msg)

            # User says to continue - model will wait for actual user input
            continue_msg: TResponseInputItem = {
                "role": "user",
                "content": "Please continue from where we left off.",
            }
            pruned.append(continue_msg)

        logger.debug(
            f"[{self.session_id[:8]}] Built pruned items: {len(system_msgs)} system + "
            f"summary context"
        )

        return pruned

    async def _persist_pruned_session(
        self,
        pruned_items: List[TResponseInputItem],
    ) -> None:
        """
        Persist pruned items to session database.

        This replaces the full history with the pruned version.
        Next turn will load the pruned history.

        IMPORTANT: Don't include the current user message - SDK will add it.
        Only persist the "base" pruned history.
        """
        if not self.session:
            logger.warning(
                f"[{self.session_id[:8]}] No session - cannot persist pruning"
            )
            return

        try:
            # Clear existing session data
            await self.session.clear_session()

            # Persist all pruned items (system messages + summary)
            # The summary replaces all conversation items including the current user message
            await self.session.add_items(pruned_items)
            logger.debug(
                f"[{self.session_id[:8]}] Persisted {len(pruned_items)} pruned items"
            )

            # Emit completion event
            if self.emit_sse_callback:
                self.emit_sse_callback(
                    "context.pruning_completed",
                    {
                        "session_id": self.session_id,
                        "items_after_pruning": len(pruned_items),
                    },
                )

        except Exception as e:
            logger.error(f"[{self.session_id[:8]}] Failed to persist pruning: {e}")
            # Don't raise - allow the turn to continue with pruned input
            if self.emit_sse_callback:
                self.emit_sse_callback(
                    "context.pruning_error",
                    {"session_id": self.session_id, "error": str(e)},
                )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _sanitize_items_for_openai(
        self, items: List[TResponseInputItem]
    ) -> List[TResponseInputItem]:
        """
        Sanitize items for OpenAI compatibility.

        Only called when target model is OpenAI. Handles:
        1. Replace __fake_id__ with proper rs-prefixed IDs
        2. Remove Anthropic-specific content types (thinking, reasoning)
        """
        import uuid

        FAKE_ID = "__fake_id__"
        UNSUPPORTED_TYPES = {
            "thinking",
            "redacted_thinking",
            "reasoning",
            "reasoning_text",
            "summary_text",
        }
        sanitized = []

        for item in items:
            # Convert to dict for manipulation
            if isinstance(item, dict):
                item_dict = item.copy()
            elif hasattr(item, "model_dump"):
                item_dict = item.model_dump()
            else:
                sanitized.append(item)
                continue

            # Skip reasoning items entirely (Anthropic extended thinking)
            if item_dict.get("type") == "reasoning":
                logger.debug("Skipping reasoning item for OpenAI compatibility")
                continue

            # Replace fake ID at item level
            if item_dict.get("id") == FAKE_ID:  # type: ignore[typeddict-unknown-key]
                item_dict["id"] = f"rs_{uuid.uuid4().hex[:24]}"  # type: ignore[typeddict-item]

            # Process nested content blocks
            if "content" in item_dict and isinstance(
                item_dict["content"], list  # type: ignore[typeddict-item]
            ):  # type: ignore[typeddict-item]
                cleaned_content = []
                for block in item_dict["content"]:  # type: ignore[typeddict-item]
                    if isinstance(block, dict):
                        block = block.copy()
                    elif hasattr(block, "model_dump"):
                        block = block.model_dump()
                    else:
                        cleaned_content.append(block)
                        continue

                    # Skip unsupported content types
                    block_type = block.get("type", "")
                    if block_type in UNSUPPORTED_TYPES:
                        logger.debug(f"Skipping {block_type} block for OpenAI")
                        continue

                    # Fix fake IDs
                    if block.get("id") == FAKE_ID:  # type: ignore[typeddict-unknown-key]
                        block["id"] = f"rs_{uuid.uuid4().hex[:24]}"  # type: ignore[typeddict-item]
                    if block.get("call_id") == FAKE_ID:  # type: ignore[typeddict-unknown-key]
                        block["call_id"] = (  # type: ignore[typeddict-item]
                            f"call_{uuid.uuid4().hex[:24]}"
                        )  # type: ignore[typeddict-item]

                    cleaned_content.append(block)

                item_dict["content"] = cleaned_content  # type: ignore[typeddict-item]

            # Skip items with empty content after filtering
            if "content" in item_dict and isinstance(
                item_dict["content"], list  # type: ignore[typeddict-item]
            ):  # type: ignore[typeddict-item]
                if len(item_dict["content"]) == 0:  # type: ignore[typeddict-item]
                    logger.debug("Skipping item with empty content after filtering")
                    continue

            sanitized.append(item_dict)

        return sanitized

    def _is_openai_model(self) -> bool:
        """Check if the current model is an OpenAI model."""
        if not self.model_name:
            return False
        model_lower = self.model_name.lower()
        return (
            model_lower.startswith("gpt-")
            or model_lower.startswith("openai/")
            or "gpt-4" in model_lower
            or "gpt-5" in model_lower
        )

    def _get_model_name(self, agent: Optional[Agent[AgentContext]]) -> str:
        """Extract model name from agent or use default."""
        if self.model_name:
            return self.model_name
        if agent and hasattr(agent, "model"):
            model = agent.model
            if model is not None and hasattr(model, "model"):
                return model.model
            return str(model) if model is not None else "gpt-4o"
        return "gpt-4o"

    def _get_item_role(self, item: Any) -> Optional[str]:
        """Extract role from an input item."""
        if isinstance(item, dict):
            return item.get("role")
        if hasattr(item, "role"):
            return getattr(item, "role", None)
        if hasattr(item, "model_dump"):
            return item.model_dump().get("role")
        return None

    def _extract_content(self, item: Any) -> Optional[str]:
        """Extract content string from an input item."""
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Handle content arrays
                parts = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        parts.append(part["text"])
                    elif isinstance(part, str):
                        parts.append(part)
                return " ".join(parts)
        if hasattr(item, "content"):
            content = getattr(item, "content", None)
            if isinstance(content, str):
                return content
        return None

    def _extract_messages(
        self, input_items: List[TResponseInputItem]
    ) -> List[Dict[str, str]]:
        """
        Extract messages from input items, including tool call information.

        Tool calls and results are formatted as readable text so the summarizer
        can capture them as part of the conversation context.
        """
        messages = []
        for item in input_items:
            role = None
            content = None

            if isinstance(item, dict):
                role = item.get("role")
                content = item.get("content")
            elif hasattr(item, "role") and hasattr(item, "content"):
                role = getattr(item, "role", None)
                content = getattr(item, "content", None)
            elif hasattr(item, "model_dump"):
                data = item.model_dump()
                role = data.get("role")
                content = data.get("content")

            if role and content:
                role_str = str(role)
                if isinstance(content, str):
                    messages.append({"role": role_str, "content": content})
                elif isinstance(content, list):
                    # Handle structured content (text, tool_use, tool_result)
                    content_parts = []
                    for part in content:
                        part_dict = self._to_dict(part)
                        if not part_dict:
                            continue

                        part_type = part_dict.get("type")

                        # Text content
                        if part_type == "text" or "text" in part_dict:
                            text = part_dict.get("text", "")
                            if text:
                                content_parts.append(text)

                        # Tool use (assistant calling a tool)
                        elif part_type == "tool_use":
                            tool_name = part_dict.get("name", "unknown_tool")
                            tool_input = part_dict.get("input", {})
                            # Format tool call in a readable way
                            input_summary = self._summarize_tool_input(tool_input)
                            content_parts.append(
                                f"[TOOL CALL: {tool_name}({input_summary})]"
                            )

                        # Tool result (response from tool) - include full content
                        # for summarizer to extract valuable insights
                        elif part_type == "tool_result":
                            tool_content = part_dict.get("content", "")
                            if tool_content:
                                content_parts.append(f"[TOOL RESULT: {tool_content}]")

                    if content_parts:
                        messages.append(
                            {"role": role_str, "content": " ".join(content_parts)}
                        )

        return messages

    def _to_dict(self, obj: Any) -> Optional[Dict]:
        """Convert object to dict if possible."""
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return None

    def _summarize_tool_input(self, tool_input: Any) -> str:
        """Summarize tool input for readable logging."""
        if not tool_input:
            return ""
        if isinstance(tool_input, str):
            return tool_input[:100] + "..." if len(tool_input) > 100 else tool_input
        if isinstance(tool_input, dict):
            # Extract key parameters
            parts = []
            for key, value in list(tool_input.items())[:3]:  # Limit to 3 params
                val_str = str(value)[:50]
                parts.append(f"{key}={val_str}")
            return ", ".join(parts)
        return str(tool_input)[:100]

    def _format_summary_message(
        self, summary_data: Dict[str, Any], removed_count: int
    ) -> str:
        """Format summary data as a comprehensive message including tool insights."""
        text = summary_data.get("summary_text", "Previous conversation summary")
        goals = summary_data.get("goals", [])
        accomplishments = summary_data.get("accomplishments", [])
        tool_calls = summary_data.get("tool_calls", [])
        key_insights = summary_data.get("key_insights", [])
        state = summary_data.get("most_recent_state", "")

        content = (
            f"**Previous Conversation Summary** (replaced {removed_count} messages):\n\n"
            f"{text}"
        )

        if goals:
            content += "\n\n**User Goals:**\n" + "\n".join(f"- {g}" for g in goals)

        if accomplishments:
            content += "\n\n**Accomplishments:**\n" + "\n".join(
                f"- {a}" for a in accomplishments
            )

        if tool_calls:
            content += "\n\n**Tools Used:**\n" + "\n".join(f"- {t}" for t in tool_calls)

        if key_insights:
            content += "\n\n**Key Information Discovered:**\n" + "\n".join(
                f"- {i}" for i in key_insights
            )

        if state:
            content += f"\n\n**Continue From:** {state}"

        return content


# =============================================================================
# Factory Function
# =============================================================================


def create_context_manager_hooks(
    session_id: str,
    session: Optional[SQLAlchemySession] = None,
    model_name: Optional[str] = None,
    emit_sse_callback: Optional[Callable] = None,
    initial_token_count: int = 0,
) -> ContextManagerHooks:
    """
    Factory function to create context manager hooks.

    Args:
        session_id: Unique identifier for the chat session
        session: SDK session for persisting pruned history (optional)
        model_name: Model name for token counting
        emit_sse_callback: Callback to emit SSE events
        initial_token_count: Initial token count (can be loaded from DB)

    Returns:
        Configured ContextManagerHooks instance
    """
    return ContextManagerHooks(
        session_id=session_id,
        session=session,
        model_name=model_name,
        emit_sse_callback=emit_sse_callback,
        initial_token_count=initial_token_count,
    )


# =============================================================================
# Database Token Persistence
# =============================================================================


async def load_token_count_from_db(
    session_id: str,
    db_session: AsyncSession,
) -> Tuple[int, Optional[str]]:
    """
    Load token count from database for a session.

    Args:
        session_id: The session ID to load tokens for
        db_session: SQLAlchemy async session

    Returns:
        Tuple of (last_input_tokens, last_model_name)
    """
    from app.db_models.sessions import AgentSessionsORM

    try:
        result = await db_session.execute(
            select(
                AgentSessionsORM.last_input_tokens,
                AgentSessionsORM.last_model_name,
            ).where(AgentSessionsORM.session_id == session_id)
        )
        row = result.first()

        if row and row.last_input_tokens is not None:
            logger.info(
                f"Loaded token count from DB for {session_id}: "
                f"{row.last_input_tokens:,} tokens ({row.last_model_name})"
            )
            return row.last_input_tokens, row.last_model_name

        logger.debug(f"No token count in DB for session {session_id}")
        return 0, None

    except Exception as e:
        logger.warning(f"Failed to load token count from DB: {e}")
        return 0, None


async def persist_token_count_to_db(
    session_id: str,
    input_tokens: int,
    model_name: str,
    db_session: AsyncSession,
) -> bool:
    """
    Persist token count to database for a session.

    Args:
        session_id: The session ID to save tokens for
        input_tokens: The token count to persist
        model_name: The model name used
        db_session: SQLAlchemy async session

    Returns:
        True if successful, False otherwise
    """
    from app.db_models.sessions import AgentSessionsORM

    try:
        await db_session.execute(
            update(AgentSessionsORM)
            .where(AgentSessionsORM.session_id == session_id)
            .values(
                last_input_tokens=input_tokens,
                last_model_name=model_name,
                token_updated_at=datetime.utcnow(),
            )
        )
        await db_session.commit()

        logger.info(
            f"Persisted token count to DB for {session_id}: "
            f"{input_tokens:,} tokens ({model_name})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to persist token count to DB: {e}")
        await db_session.rollback()
        return False
