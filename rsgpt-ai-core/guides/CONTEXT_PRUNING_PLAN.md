# Context Window Pruning & Summarization Plan

> **Status**: Planning
> **Phase**: 4 (Type-Based Pruning)
> **Created**: November 27, 2025
> **Dependencies**: Phase 2 (SDK Sessions) - Complete

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [SDK Deep Dive](#sdk-deep-dive)
4. [Architecture Options](#architecture-options)
5. [Recommended Solution](#recommended-solution)
6. [Implementation Plan](#implementation-plan)
7. [Data Flow](#data-flow)
8. [Code Changes](#code-changes)
9. [Testing Strategy](#testing-strategy)

---

## Executive Summary

When conversations become long, the context window approaches its limit (e.g., 128K tokens for GPT-4). We need to:

1. **Detect** when context usage exceeds a threshold (e.g., 90%)
2. **Summarize** older conversation content using the summarizer agent
3. **Prune** the session to contain: summary + recent messages
4. **Persist** the pruned state so future turns load the already-pruned history

### Key Insight

The SDK automatically saves all items to the session after each turn. If we only filter items in `call_model_input_filter` without persisting to the session, the next turn will reload the full (unpruned) history. **We must persist pruning to the session database.**

---

## Problem Statement

### Current Behavior

```
Turn 1: User sends message → SDK loads history (0 items) → LLM → SDK saves items (2 items)
Turn 2: User sends message → SDK loads history (2 items) → LLM → SDK saves items (4 items)
...
Turn 50: User sends message → SDK loads history (100 items) → 🔴 Context at 95%!
```

### What We Have

1. `on_llm_end` hook: Can detect token usage after each LLM call
2. `call_model_input_filter` hook: Can modify input before LLM call
3. `summarize_conversation()`: Creates structured summaries
4. SDK Session: Stores conversation history in PostgreSQL

### What's Missing

1. **Persisting pruned state** to the SDK session
2. **Coordinated workflow** between detection and pruning
3. **Session reference** in the hooks to perform pruning

### The Root Cause

The SDK's `_save_result_to_session` method saves the **original input** plus new items:

```python
# From SDK run.py:1927-1949
async def _save_result_to_session(
    cls,
    session: Session | None,
    original_input: str | list[TResponseInputItem],
    new_items: list[RunItem],
) -> None:
    """
    Save the conversation turn to session.
    It does not account for any filtering or modification performed by
    `RunConfig.session_input_callback`.
    """
    if session is None:
        return

    # Convert original input to list format if needed
    input_list = ItemHelpers.input_to_new_input_list(original_input)

    # Convert new items to input format
    new_items_as_input = [item.to_input_item() for item in new_items]

    # Save all items from this turn
    items_to_save = input_list + new_items_as_input
    await session.add_items(items_to_save)
```

Key observation: **The SDK appends items. It never removes old items.** The pruning must happen separately.

---

## SDK Deep Dive

### Session Protocol

```python
# From SDK memory/session.py
class Session(Protocol):
    session_id: str

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]:
        """Retrieve conversation history."""
        ...

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """Add new items to history."""
        ...

    async def pop_item(self) -> TResponseInputItem | None:
        """Remove and return most recent item."""
        ...

    async def clear_session(self) -> None:
        """Clear all items for this session."""
        ...
```

### Hook Points Available

| Hook | When Called | Has Access To | Can Modify |
|------|-------------|---------------|------------|
| `on_start` | Before agent invoked | Agent, Context | Nothing |
| `call_model_input_filter` | Before each LLM call | Agent, Context, Input Items | Input items |
| `on_llm_end` | After each LLM call | Agent, Context, Response (with usage) | Nothing |
| `on_end` | After agent completes | Agent, Context, Output | Nothing |
| `session_input_callback` | Once per run (start) | History, New Input | Combined input |

### Key SDK Methods

```python
# Prepare input with session (called at run start)
prepared_input = await self._prepare_input_with_session(
    input, session, run_config.session_input_callback
)

# Filter before LLM call
model_input = await self._maybe_filter_model_input(
    agent=agent,
    run_config=run_config,
    context_wrapper=context_wrapper,
    input_items=input_items,
    system_instructions=system_instructions,
)

# Save results (called after each turn)
await self._save_result_to_session(session, original_input, new_items)
```

---

## Architecture Options

### Option A: Prune Only in `call_model_input_filter` (Current Approach)

**Flow:**
1. `on_llm_end`: Detect threshold, set flag
2. `call_model_input_filter`: Create summary, filter items
3. SDK saves original items anyway ❌

**Problem:** Pruning doesn't persist. Next turn loads full history.

---

### Option B: Prune and Persist in `call_model_input_filter`

**Flow:**
1. `on_llm_end`: Detect threshold, set flag
2. `call_model_input_filter`:
   - Create summary using summarizer agent
   - Build pruned items (summary + recent)
   - **`session.clear_session()`**
   - **`session.add_items(pruned_items)`**
   - Return pruned items for current LLM call
3. SDK saves turn's items (appended to pruned base) ✅

**Challenge:** Hooks need session reference. Also, the LLM call hasn't happened yet, so the new user message and response won't be in the pruned items when we persist.

**Solution:** We persist the pruned BASE (history without current turn). SDK will add current turn's items after.

---

### Option C: Prune After Turn Completes

**Flow:**
1. Turn completes normally (SDK saves items)
2. Post-turn hook checks threshold
3. If exceeded: summarize, `clear_session()`, `add_items(pruned)`

**Challenge:** No built-in "after turn" hook. Would need custom wrapper.

---

### Option D: Custom Session Wrapper

**Flow:**
1. Create `PrunableSession` that wraps `SQLAlchemySession`
2. Override `get_items()` to check threshold and auto-prune
3. Prune transparently on history load

**Challenge:** Need usage data to check threshold, but usage is only available after LLM call.

---

### Option E: Hybrid Approach (Recommended) ⭐

**Flow:**
1. `on_llm_end`: Detect threshold, **immediately** trigger pruning
2. Pruning:
   - Get current session items
   - Create summary using summarizer agent
   - Build pruned items (summary + recent N messages)
   - `session.clear_session()`
   - `session.add_items(pruned_items + new_response_items)`
3. Next `call_model_input_filter`: Normal operation (history already pruned)

**Key Insight:** Prune in `on_llm_end` AFTER we have usage data, and BEFORE the SDK's automatic save. This requires intercepting the flow or doing cleanup after SDK save.

**Actually, better:** Since SDK saves after each turn regardless, we prune **after** the turn. The next turn will load pruned history.

---

## Recommended Solution

### Enhanced Two-Phase Pruning with Token Persistence

The key insight is that we need to handle **two scenarios**:

1. **Post-turn detection**: Context exceeded threshold after LLM call → prune next turn
2. **Pre-turn detection**: Large user input + existing context would exceed threshold → prune immediately

To enable pre-turn detection, we **persist the last known token count** so we can estimate before the LLM call.

#### Token Persistence Strategy

Store `last_input_tokens` in the hooks instance AND optionally in the database for cross-request persistence:

```python
# In-memory (survives within a single agent run with multiple turns)
self._last_input_tokens: int = 0

# Database (survives across requests - optional enhancement)
# Could store in agent_sessions table or a separate context_usage table
```

#### Phase 1: Track Usage (in `on_llm_end`)

- Extract `response.usage.input_tokens`
- **Store this value** for use in next `call_model_input_filter`
- Check if threshold exceeded → set `_needs_pruning = True`

#### Phase 2: Pre-emptive Check (in `call_model_input_filter`)

**Before** checking `_needs_pruning`, estimate if current input would exceed threshold:

```python
# Estimate tokens for current input
estimated_new_tokens = self._estimate_input_tokens(input_items)

# Check if we'd exceed threshold
if self._last_input_tokens > 0:
    projected_usage = self._last_input_tokens + estimated_new_tokens
    max_tokens = TokenCounter.estimate_max_tokens(model_name)

    if projected_usage / max_tokens >= SUMMARIZATION_THRESHOLD:
        # Trigger immediate pruning!
        self._needs_pruning = True
```

#### Phase 3: Execute Pruning (in `call_model_input_filter`)

- If `_needs_pruning` is True:
  1. Get current input items (loaded from session by SDK)
  2. Run summarizer agent (separate run, no session)
  3. Build pruned list: `[summary_msg] + recent_messages[-N:]`
  4. **Persist to session:**
     - `await session.clear_session()`
     - `await session.add_items(pruned_items)`
  5. Clear flag and reset `_last_input_tokens`
  6. Return pruned items for current LLM call
- SDK will then add THIS turn's new items to the now-pruned session

### Why This Works

#### Scenario A: Gradual Growth (Post-Turn Detection)

```
Turn N (usage at 92%):
├─ SDK loads session (100 items)
├─ call_model_input_filter:
│   └─ Check: _last_input_tokens (85K) + new_input (~2K) = 87K (68%) → OK
│   └─ _needs_pruning = False → pass through
├─ LLM runs with 100 items
├─ on_llm_end:
│   └─ usage: 118,000 tokens (92%)
│   └─ Store: _last_input_tokens = 118,000
│   └─ Check: 92% >= 90% → _needs_pruning = True
├─ SDK saves: adds 2 new items → session has 102 items
│
Turn N+1:
├─ SDK loads session (102 items)
├─ call_model_input_filter:
│   └─ _needs_pruning = True → EXECUTE PRUNING
│   ├─ Create summary of items 0-97
│   ├─ Pruned list = [summary] + items[98:102] (5 items)
│   ├─ session.clear_session()
│   ├─ session.add_items(pruned 5 items)
│   ├─ Reset: _last_input_tokens = 0, _needs_pruning = False
│   └─ Return pruned items for LLM
├─ LLM runs with 5 items + new user message
├─ on_llm_end:
│   └─ usage: 12,000 tokens (9%)
│   └─ Store: _last_input_tokens = 12,000
├─ SDK saves: adds 2 new items → session has 7 items
```

#### Scenario B: Large Input (Pre-Turn Detection)

```
Turn N (usage at 70%):
├─ LLM runs normally
├─ on_llm_end:
│   └─ usage: 90,000 tokens (70%)
│   └─ Store: _last_input_tokens = 90,000
│   └─ Check: 70% < 90% → _needs_pruning stays False
├─ SDK saves items
│
Turn N+1 (user pastes large document):
├─ SDK loads session (50 items)
├─ call_model_input_filter:
│   └─ Check: _last_input_tokens (90K) + new_input (~35K) = 125K (98%) ⚠️
│   └─ 98% >= 90% → _needs_pruning = True (PRE-EMPTIVE!)
│   ├─ Create summary
│   ├─ Prune session
│   └─ Return pruned items for LLM
├─ LLM runs with pruned context + large input (now fits!)
├─ on_llm_end: usage: 45,000 tokens (35%)
```

#### Scenario C: Very Large Single Input (Immediate Pruning)

```
Turn N (fresh session, user pastes huge document):
├─ SDK loads session (2 items, ~5K tokens)
├─ call_model_input_filter:
│   └─ Check: _last_input_tokens (0) + new_input (~120K) = 120K
│   └─ But wait - we also need to count existing history!
│   └─ Estimate: history (5K) + new_input (120K) = 125K (98%) ⚠️
│   └─ 98% >= 90% → IMMEDIATE PRUNING
│   └─ (May need to truncate the large input itself)
```

---

## Implementation Plan

### Files to Modify

| File | Changes |
|------|---------|
| `context_manager_hooks.py` | Add session reference, implement persistence |
| `orchestration_service.py` | Pass session to hooks |
| `agent_config.py` | Update run config builder to include hooks with session |

### New Components

```
app/services/context_manager/
├── context_manager_hooks.py    # Modified: add session-aware pruning
├── token_counter.py            # Existing: model limits
└── context_manager_logging.py  # Existing: logging
```

### Step-by-Step Implementation

#### Step 1: Update ContextManagerHooks to Accept Session and Track Tokens

```python
class ContextManagerHooks(AgentHooks):
    def __init__(
        self,
        session_id: str,
        session: Optional[SQLAlchemySession] = None,  # NEW
        model_name: Optional[str] = None,
        emit_sse_callback: Optional[Callable] = None,
        initial_token_count: int = 0,  # NEW: Can be loaded from DB
    ):
        self.session_id = session_id
        self.session = session  # Store session reference
        self.model_name = model_name
        self.emit_sse_callback = emit_sse_callback
        self.logger = get_context_logger(session_id)

        # Pruning state
        self._needs_pruning = False
        self._pruning_model_name: Optional[str] = None

        # Token tracking (NEW)
        self._last_input_tokens: int = initial_token_count
        self._max_context_tokens: int = 0  # Set based on model
        self._session_start_time: Optional[float] = None
```

#### Step 2: Update `on_llm_end` to Track and Persist Token Usage

```python
async def on_llm_end(
    self,
    context: RunContextWrapper[AgentContext],
    agent: Agent[AgentContext],
    response: ModelResponse,
) -> None:
    """Called after LLM call. Tracks tokens and detects if pruning needed."""
    try:
        # Emit usage event
        await self._emit_usage_event(context, response, agent)

        # CRITICAL: Store token usage for next turn's pre-check
        await self._track_token_usage(response, agent)

        # Check if threshold exceeded (schedule pruning for next turn)
        if not self._needs_pruning:
            await self._check_pruning_threshold(response, agent)

    except Exception as e:
        self.logger.error(f"Error in on_llm_end: {e}")

async def _track_token_usage(
    self,
    response: ModelResponse,
    agent: Agent[AgentContext],
) -> None:
    """Store token usage for pre-turn threshold checking."""
    if not (hasattr(response, "usage") and response.usage):
        return

    input_tokens = getattr(response.usage, "input_tokens", 0)
    model_name = self._get_model_name(agent)
    max_tokens = TokenCounter.estimate_max_tokens(model_name)

    # Store in memory for next call_model_input_filter
    self._last_input_tokens = input_tokens
    self._max_context_tokens = max_tokens
    self._pruning_model_name = model_name

    self.logger.info(
        f"📊 Token usage tracked: {input_tokens:,} / {max_tokens:,} "
        f"({input_tokens / max_tokens * 100:.1f}%)"
    )

    # Optional: Persist to database for cross-request durability
    # await self._persist_token_usage_to_db(input_tokens, model_name)

async def _check_pruning_threshold(
    self,
    response: ModelResponse,
    agent: Agent[AgentContext],
) -> None:
    """Check if context usage exceeds threshold after LLM call."""
    if not (hasattr(response, "usage") and response.usage):
        return

    input_tokens = getattr(response.usage, "input_tokens", 0)
    max_tokens = self._max_context_tokens or TokenCounter.estimate_max_tokens(
        self._get_model_name(agent)
    )

    if max_tokens == 0:
        return

    usage_ratio = input_tokens / max_tokens

    if usage_ratio >= SUMMARIZATION_THRESHOLD:
        self.logger.warning(
            f"⚠️ Context at {usage_ratio:.1%} - pruning scheduled for next turn"
        )
        self._needs_pruning = True

        # Emit event for frontend
        if self.emit_sse_callback:
            self.emit_sse_callback(
                "context.pruning_scheduled",
                {
                    "session_id": self.session_id,
                    "input_tokens": input_tokens,
                    "max_tokens": max_tokens,
                    "usage_percentage": usage_ratio * 100,
                    "threshold_percentage": SUMMARIZATION_THRESHOLD * 100,
                    "reason": "post_turn_threshold_exceeded",
                },
            )
```

#### Step 3: Implement Pre-Turn Check AND Pruning in `call_model_input_filter`

```python
async def call_model_input_filter(self, data: CallModelData) -> ModelInputData:
    """
    Filter called before LLM.

    Two responsibilities:
    1. PRE-CHECK: Estimate if current input would exceed threshold
    2. EXECUTE: Perform pruning if needed (from pre-check OR post-turn flag)
    """
    try:
        model_data = data.model_data
        input_items = list(model_data.input)

        # =====================================================
        # STEP 1: PRE-TURN CHECK (for large inputs)
        # =====================================================
        if not self._needs_pruning and self.session:
            await self._pre_turn_threshold_check(input_items)

        # =====================================================
        # STEP 2: EXECUTE PRUNING (if needed from either check)
        # =====================================================
        if self._needs_pruning and self.session:
            self.logger.info("🔄 Executing context pruning...")

            # 1. Create summary of current items
            summary_data = await self._create_summary(input_items)

            # 2. Build pruned items
            pruned_items = self._build_pruned_items(input_items, summary_data)

            # 3. Persist to session (CRITICAL!)
            await self._persist_pruned_session(pruned_items)

            # 4. Clear flags and reset token tracking
            self._needs_pruning = False
            self._last_input_tokens = 0  # Reset after pruning

            # 5. Return pruned items for this LLM call
            self.logger.info(
                f"✓ Pruned from {len(input_items)} to {len(pruned_items)} items"
            )

            return ModelInputData(
                input=pruned_items,
                instructions=model_data.instructions,
            )

        return model_data

    except Exception as e:
        self.logger.error(f"Error in call_model_input_filter: {e}")
        return data.model_data

async def _pre_turn_threshold_check(
    self,
    input_items: List[TResponseInputItem],
) -> None:
    """
    Check if current input + stored context would exceed threshold.

    This catches the case where user submits a large input that would
    push us over the limit, even if the previous turn was under threshold.
    """
    if self._last_input_tokens == 0:
        # No previous usage data - estimate from input items
        estimated_context = self._estimate_tokens(input_items)
    else:
        # Use stored value + estimate new items added since last LLM call
        # The input_items includes history + new user message
        estimated_context = self._estimate_tokens(input_items)

    max_tokens = self._max_context_tokens
    if max_tokens == 0:
        model_name = self.model_name or "gpt-4"
        max_tokens = TokenCounter.estimate_max_tokens(model_name)

    if max_tokens == 0:
        return

    usage_ratio = estimated_context / max_tokens

    self.logger.debug(
        f"Pre-turn check: ~{estimated_context:,} / {max_tokens:,} "
        f"({usage_ratio:.1%})"
    )

    if usage_ratio >= SUMMARIZATION_THRESHOLD:
        self.logger.warning(
            f"⚠️ Pre-turn threshold exceeded: {usage_ratio:.1%} >= "
            f"{SUMMARIZATION_THRESHOLD:.0%} - triggering immediate pruning"
        )
        self._needs_pruning = True

        if self.emit_sse_callback:
            self.emit_sse_callback(
                "context.pruning_scheduled",
                {
                    "session_id": self.session_id,
                    "estimated_tokens": estimated_context,
                    "max_tokens": max_tokens,
                    "usage_percentage": usage_ratio * 100,
                    "threshold_percentage": SUMMARIZATION_THRESHOLD * 100,
                    "reason": "pre_turn_large_input",
                },
            )

def _estimate_tokens(self, items: List[TResponseInputItem]) -> int:
    """
    Estimate token count for a list of items.

    Uses a simple heuristic: ~4 characters per token (English text).
    For more accuracy, could use tiktoken library.
    """
    total_chars = 0
    for item in items:
        if isinstance(item, dict):
            content = item.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # Handle content arrays (e.g., with images)
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total_chars += len(part["text"])
        elif hasattr(item, "content"):
            content = getattr(item, "content", "")
            if isinstance(content, str):
                total_chars += len(content)

    # Rough estimate: 4 chars per token + 10% overhead for structure
    estimated_tokens = int((total_chars / 4) * 1.1)
    return estimated_tokens
```

#### Step 4: Implement Session Persistence

```python
async def _persist_pruned_session(
    self,
    pruned_items: List[TResponseInputItem],
) -> None:
    """
    Persist pruned items to session database.

    This replaces the full history with the pruned version.
    Next turn will load the pruned history.
    """
    if not self.session:
        self.logger.warning("No session - cannot persist pruning")
        return

    try:
        # Clear existing session data
        await self.session.clear_session()
        self.logger.info("✓ Session cleared")

        # Add pruned items
        await self.session.add_items(pruned_items)
        self.logger.info(f"✓ Persisted {len(pruned_items)} pruned items")

        # Emit event
        if self.emit_sse_callback:
            self.emit_sse_callback(
                "context.pruning_completed",
                {
                    "session_id": self.session_id,
                    "items_after_pruning": len(pruned_items),
                },
            )

    except Exception as e:
        self.logger.error(f"Failed to persist pruning: {e}")
        raise
```

#### Step 5: Summarizer Agent Integration

The summarizer agent runs as a **separate, independent agent call** without session:

```python
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
        # Extract messages for summarization
        messages = self._extract_messages(input_items)
        self.logger.info(f"Creating summary of {len(messages)} messages")

        # Emit event for frontend progress indication
        if self.emit_sse_callback:
            self.emit_sse_callback(
                "context.summarizing",
                {"session_id": self.session_id, "message_count": len(messages)},
            )

        # Run summarizer (no session - standalone call)
        summary_data = await summarize_conversation(
            messages=messages,
            previous_summary=None,  # Could pass existing summary for incremental
            model="gpt-4o-mini",    # Fast, cheap model for summarization
        )

        self.logger.info(
            f"✓ Summary created: {summary_data.get('summary_text', '')[:80]}..."
        )
        return summary_data

    except Exception as e:
        self.logger.error(f"Summarization failed: {e}")
        # Return fallback summary so pruning can still proceed
        return self._create_fallback_summary(messages)

def _create_fallback_summary(self, messages: List[Dict]) -> Dict[str, Any]:
    """Create basic fallback summary when LLM summarization fails."""
    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

    return {
        "summary_text": (
            f"Previous conversation with {user_count} user messages and "
            f"{assistant_count} assistant responses. Topics discussed include "
            "the items in recent messages."
        ),
        "goals": ["Continue assisting the user"],
        "tool_calls": [],
        "accomplishments": [f"Processed {len(messages)} messages"],
        "most_recent_state": "Conversation in progress",
    }
```

#### Step 6: Build Pruned Items with Summary

```python
def _build_pruned_items(
    self,
    items: List[TResponseInputItem],
    summary_data: Dict[str, Any],
) -> List[TResponseInputItem]:
    """
    Build pruned item list with summary.

    Strategy:
    - Keep system messages (instructions)
    - Replace old conversation with summary
    - Keep recent N messages
    """
    pruned = []

    # Categorize items
    system_msgs = []
    conversation_items = []

    for item in items:
        role = self._get_item_role(item)
        if role == "system":
            system_msgs.append(item)
        else:
            conversation_items.append(item)

    # Keep system messages
    pruned.extend(system_msgs)

    # Calculate how many recent items to keep
    # Keep last MESSAGES_TO_KEEP conversation items
    recent_items = conversation_items[-MESSAGES_TO_KEEP:]
    summarized_count = len(conversation_items) - len(recent_items)

    # Add summary if we actually summarized something
    if summarized_count > 0:
        summary_content = self._format_summary_message(
            summary_data, summarized_count
        )
        summary_msg: TResponseInputItem = {
            "role": "user",
            "content": summary_content,
        }
        pruned.append(summary_msg)

    # Add recent items
    pruned.extend(recent_items)

    return pruned
```

#### Step 6: Update Orchestration Service

```python
# In orchestration_service.py

async def _run_agent(
    self,
    request: AgentRequest,
    agent_context: AgentContext,
    sequence_number: int,
    emitter: SSEEventEmitter,
) -> AsyncGenerator[tuple[str, int], None]:
    """Execute agent workflow."""

    # ... tool initialization ...

    # Create SDK session
    sdk_session = None
    if request.use_sdk_session:
        sdk_session = create_sdk_session(
            session_id=request.session_id,
            create_tables=False,
        )

    # Create context hooks WITH session reference
    context_hooks = create_context_manager_hooks(
        session_id=request.session_id,
        session=sdk_session,  # Pass session for pruning persistence
        model_name=request.model or "gpt-5",
        emit_sse_callback=lambda event_type, data: emitter.emit_custom_event(
            event_type, data
        ),
    )

    # Build run config with hooks
    run_config = build_run_config(context_hooks)

    # Execute with session
    agent_result = Runner.run_streamed(
        main_agent,
        input=request.input,
        context=agent_context,
        max_turns=max_turns,
        run_config=run_config,
        session=sdk_session,
    )
```

---

## Data Flow

### Normal Turn (No Pruning)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         NORMAL TURN (No Pruning)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Runner.run_streamed() called                                         │
│     └── input: "What's the weather?"                                     │
│                                                                          │
│  2. SDK: _prepare_input_with_session()                                   │
│     └── history = session.get_items() → [prev_user, prev_assistant]     │
│     └── prepared_input = history + new_user_message                      │
│                                                                          │
│  3. Hooks: call_model_input_filter()                                     │
│     └── Pre-check: _last_input_tokens (5K) + estimated (~500) = 5.5K    │
│     └── 5.5K / 128K = 4% < 90% → OK                                      │
│     └── _needs_pruning = False → return unchanged                        │
│                                                                          │
│  4. LLM Call                                                             │
│     └── input: [prev_user, prev_assistant, new_user]                     │
│     └── response: "The weather is sunny..."                              │
│                                                                          │
│  5. Hooks: on_llm_end()                                                  │
│     └── usage: 5,500 tokens (4% of 128K)                                 │
│     └── Store: _last_input_tokens = 5,500                                │
│     └── threshold not reached → _needs_pruning stays False               │
│                                                                          │
│  6. SDK: _save_result_to_session()                                       │
│     └── session.add_items([new_user, new_assistant])                     │
│                                                                          │
│  Session after turn: [prev_user, prev_assistant, new_user, new_assistant]│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Turn That Triggers Pruning

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TURN THAT TRIGGERS PRUNING (Turn N)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1-4. Normal flow...                                                     │
│                                                                          │
│  5. Hooks: on_llm_end()                                                  │
│     └── usage: 115,000 tokens (90% of 128K) ⚠️                           │
│     └── threshold REACHED!                                               │
│     └── _needs_pruning = True                                            │
│     └── Emit "context.pruning_scheduled" event                           │
│                                                                          │
│  6. SDK: _save_result_to_session()                                       │
│     └── session.add_items([new_user, new_assistant])                     │
│                                                                          │
│  Session after turn: 102 items (115K tokens worth) 🔴                    │
│  Flag: _needs_pruning = True                                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Large Input Triggers Pre-Turn Pruning

```
┌─────────────────────────────────────────────────────────────────────────┐
│              LARGE INPUT TRIGGERS PRE-TURN PRUNING                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Previous turn ended with: _last_input_tokens = 90,000 (70% of 128K)    │
│  Session has: 50 items                                                   │
│                                                                          │
│  1. User pastes large document (30,000 words)                            │
│     └── input: "Analyze this document: [huge text...]"                   │
│                                                                          │
│  2. SDK: _prepare_input_with_session()                                   │
│     └── prepared_input = 50 history items + huge_user_message            │
│                                                                          │
│  3. Hooks: call_model_input_filter() ⚠️ PRE-TURN CHECK                   │
│     └── Estimate new input tokens: ~35,000                               │
│     └── Pre-check: _last_input_tokens (90K) vs estimated total (~125K)  │
│     └── 125K / 128K = 98% >= 90% → THRESHOLD EXCEEDED!                   │
│     └── _needs_pruning = True (PRE-EMPTIVE)                              │
│     │                                                                    │
│     └── EXECUTE PRUNING IMMEDIATELY:                                     │
│         ├── Create summary of items 0-45                                 │
│         ├── Pruned list = [summary] + items[46:50] + huge_user_msg       │
│         ├── session.clear_session()                                      │
│         ├── session.add_items([summary, items 46-50])                    │
│         ├── Reset: _last_input_tokens = 0                                │
│         └── Return: [summary, recent_4, huge_user] (~40K tokens)         │
│                                                                          │
│  4. LLM Call                                                             │
│     └── input: ~40K tokens (31% of 128K) ✅ FITS!                        │
│     └── response: "Based on the document..."                             │
│                                                                          │
│  5. Hooks: on_llm_end()                                                  │
│     └── usage: 45,000 tokens (35%)                                       │
│     └── Store: _last_input_tokens = 45,000                               │
│                                                                          │
│  6. SDK: _save_result_to_session()                                       │
│     └── session.add_items([huge_user, assistant])                        │
│                                                                          │
│  Session after turn: [summary, recent_4, huge_user, assistant] = 7 items │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Turn After Pruning (Turn N+1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  TURN AFTER PRUNING (Turn N+1)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Runner.run_streamed() called                                         │
│     └── input: "Tell me more"                                            │
│                                                                          │
│  2. SDK: _prepare_input_with_session()                                   │
│     └── history = session.get_items() → 102 items                        │
│     └── prepared_input = history + new_user_message (103 items)          │
│                                                                          │
│  3. Hooks: call_model_input_filter() 🔄                                  │
│     └── _needs_pruning = True → EXECUTE PRUNING                          │
│     │                                                                    │
│     ├── a. Create summary of items 0-97                                  │
│     │   └── await summarize_conversation(old_items)                      │
│     │   └── summary: "User discussed X, Y, Z. Tools used: A, B..."       │
│     │                                                                    │
│     ├── b. Build pruned list                                             │
│     │   └── [summary_msg] + recent_items[-4:] + new_user_msg             │
│     │   └── Total: 6 items                                               │
│     │                                                                    │
│     ├── c. Persist to session (CRITICAL!)                                │
│     │   └── await session.clear_session()                                │
│     │   └── await session.add_items(pruned_5_items_without_new_user)     │
│     │                                                                    │
│     ├── d. Clear flag                                                    │
│     │   └── _needs_pruning = False                                       │
│     │                                                                    │
│     └── e. Return pruned items for LLM                                   │
│         └── [summary_msg, recent_4, new_user] = 6 items                  │
│                                                                          │
│  4. LLM Call                                                             │
│     └── input: 6 items (~8K tokens)                                      │
│     └── response: "Here's more detail..."                                │
│                                                                          │
│  5. Hooks: on_llm_end()                                                  │
│     └── usage: 10,000 tokens (8%)                                        │
│     └── threshold not reached → flag stays False                         │
│                                                                          │
│  6. SDK: _save_result_to_session()                                       │
│     └── session.add_items([new_user, new_assistant])                     │
│     └── (Added to already-pruned session)                                │
│                                                                          │
│  Session after turn: 7 items ✅                                          │
│  - summary_msg                                                           │
│  - recent_1, recent_2, recent_3, recent_4                                │
│  - new_user, new_assistant                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Code Changes

### Modified: `context_manager_hooks.py`

```python
"""Context Manager Hooks with Session-Aware Pruning"""

import time
from typing import Any, Callable, Dict, List, Optional

from agents import Agent, AgentHooks, ModelResponse, Tool
from agents.extensions.memory import SQLAlchemySession
from agents.items import TResponseInputItem
from agents.run import CallModelData, ModelInputData
from agents.run_context import RunContextWrapper

from app.models.agent import AgentContext
from app.services.agent.summarizer_agent import summarize_conversation
from app.services.context_manager.context_manager_logging import get_context_logger
from app.services.context_manager.token_counter import TokenCounter

# Constants
SUMMARIZATION_THRESHOLD = 0.90
MESSAGES_TO_KEEP = 4


class ContextManagerHooks(AgentHooks):
    """Agent hooks with session-aware context pruning."""

    def __init__(
        self,
        session_id: str,
        session: Optional[SQLAlchemySession] = None,
        model_name: Optional[str] = None,
        emit_sse_callback: Optional[Callable] = None,
    ):
        self.session_id = session_id
        self.session = session
        self.model_name = model_name
        self.emit_sse_callback = emit_sse_callback
        self.logger = get_context_logger(session_id)

        # Pruning state
        self._needs_pruning = False
        self._pruning_model_name: Optional[str] = None
        self._session_start_time: Optional[float] = None

    async def call_model_input_filter(self, data: CallModelData) -> ModelInputData:
        """Execute pruning if scheduled, otherwise pass through."""
        try:
            model_data = data.model_data
            input_items = list(model_data.input)

            if self._needs_pruning and self.session:
                self.logger.info("🔄 Executing scheduled context pruning...")

                # Create summary
                summary_data = await self._create_summary(input_items)

                # Build pruned items
                pruned_items = self._build_pruned_items(input_items, summary_data)

                # Persist to session
                await self._persist_pruned_session(pruned_items)

                # Clear flag
                self._needs_pruning = False
                self._pruning_model_name = None

                self.logger.info(
                    f"✓ Pruned: {len(input_items)} → {len(pruned_items)} items"
                )

                return ModelInputData(
                    input=pruned_items,
                    instructions=model_data.instructions,
                )

            return model_data

        except Exception as e:
            self.logger.error(f"Error in call_model_input_filter: {e}")
            return data.model_data

    async def on_llm_end(
        self,
        context: RunContextWrapper[AgentContext],
        agent: Agent[AgentContext],
        response: ModelResponse,
    ) -> None:
        """Check usage and schedule pruning if threshold exceeded."""
        try:
            await self._emit_usage_event(context, response, agent)

            if not self._needs_pruning:
                await self._check_pruning_threshold(response, agent)

        except Exception as e:
            self.logger.error(f"Error in on_llm_end: {e}")

    async def _check_pruning_threshold(
        self,
        response: ModelResponse,
        agent: Agent[AgentContext],
    ) -> None:
        """Check if pruning is needed based on token usage."""
        if not (hasattr(response, "usage") and response.usage):
            return

        input_tokens = getattr(response.usage, "input_tokens", 0)
        model_name = self._get_model_name(agent)
        max_tokens = TokenCounter.estimate_max_tokens(model_name)

        if max_tokens == 0:
            return

        usage_ratio = input_tokens / max_tokens

        if usage_ratio >= SUMMARIZATION_THRESHOLD:
            self.logger.warning(
                f"⚠️ Context at {usage_ratio:.1%} - scheduling pruning"
            )
            self._needs_pruning = True
            self._pruning_model_name = model_name

            if self.emit_sse_callback:
                self.emit_sse_callback(
                    "context.pruning_scheduled",
                    {
                        "session_id": self.session_id,
                        "usage_percentage": usage_ratio * 100,
                        "threshold": SUMMARIZATION_THRESHOLD * 100,
                    },
                )

    async def _create_summary(
        self,
        input_items: List[TResponseInputItem],
    ) -> Dict[str, Any]:
        """Create summary using summarizer agent."""
        messages = self._extract_messages(input_items)
        self.logger.info(f"Creating summary of {len(messages)} messages")

        summary_data = await summarize_conversation(
            messages=messages,
            previous_summary=None,
            model="gpt-4o-mini",
        )

        self.logger.info(f"✓ Summary created: {summary_data.get('summary_text', '')[:80]}...")
        return summary_data

    def _build_pruned_items(
        self,
        items: List[TResponseInputItem],
        summary_data: Dict[str, Any],
    ) -> List[TResponseInputItem]:
        """Build pruned list with summary + recent messages."""
        pruned = []

        # Separate system and conversation items
        system_msgs = []
        conversation_items = []

        for item in items:
            role = self._get_item_role(item)
            if role == "system":
                system_msgs.append(item)
            else:
                conversation_items.append(item)

        # Keep system messages
        pruned.extend(system_msgs)

        # Keep recent conversation items
        recent = conversation_items[-MESSAGES_TO_KEEP:]
        summarized_count = len(conversation_items) - len(recent)

        # Add summary if we summarized anything
        if summarized_count > 0:
            summary_content = self._format_summary_message(summary_data, summarized_count)
            pruned.append({"role": "user", "content": summary_content})

        # Add recent items
        pruned.extend(recent)

        return pruned

    async def _persist_pruned_session(
        self,
        pruned_items: List[TResponseInputItem],
    ) -> None:
        """Persist pruned items to session database."""
        if not self.session:
            return

        await self.session.clear_session()
        self.logger.info("✓ Session cleared")

        # Don't include the current user message - SDK will add it
        # Only persist the "base" pruned history
        base_items = pruned_items[:-1] if pruned_items else []
        await self.session.add_items(base_items)
        self.logger.info(f"✓ Persisted {len(base_items)} pruned items")

        if self.emit_sse_callback:
            self.emit_sse_callback(
                "context.pruning_completed",
                {
                    "session_id": self.session_id,
                    "items_after_pruning": len(base_items),
                },
            )

    # ... (helper methods: _extract_messages, _format_summary_message, etc.)
```

### Modified: Factory Function

```python
def create_context_manager_hooks(
    session_id: str,
    session: Optional[SQLAlchemySession] = None,
    model_name: Optional[str] = None,
    emit_sse_callback: Optional[Callable] = None,
) -> ContextManagerHooks:
    """Create context manager hooks with session for pruning."""
    return ContextManagerHooks(
        session_id=session_id,
        session=session,
        model_name=model_name,
        emit_sse_callback=emit_sse_callback,
    )
```

---

## Testing Strategy

### Unit Tests

1. **Threshold Detection**
   - Test `_check_pruning_threshold` with various usage ratios
   - Verify flag is set at 90%+, not set below

2. **Pruning Logic**
   - Test `_build_pruned_items` produces correct structure
   - Verify system messages preserved
   - Verify summary created when items removed
   - Verify recent N items kept

3. **Session Persistence**
   - Mock session, verify `clear_session()` called
   - Verify `add_items()` called with pruned items

### Integration Tests

1. **Full Pruning Flow**
   - Create session with 100+ items
   - Trigger turn that exceeds threshold
   - Verify pruning scheduled
   - Trigger next turn
   - Verify session now contains pruned items

2. **Multi-Turn After Pruning**
   - After pruning, run several more turns
   - Verify session grows normally from pruned base

### Manual Testing

1. Create long conversation (50+ turns)
2. Monitor usage percentage via SSE events
3. When pruning triggered, verify:
   - `context.pruning_scheduled` event emitted
   - Next turn: `context.pruning_completed` event emitted
   - Response quality maintains context awareness
   - Database shows pruned session

### Edge Cases to Test

1. **No Session**: `use_sdk_session=False`
   - Pruning should be skipped gracefully
   - No errors, just warning log

2. **Empty Session**: First message in conversation
   - No pruning needed (below threshold)
   - Normal operation

3. **Summarization Fails**: LLM error during summarization
   - Fallback summary should be used
   - Pruning should still complete

4. **Session Persistence Fails**: Database error
   - Current turn should continue (with unpruned input)
   - Error logged
   - Retry on next turn

5. **Very Long Single Message**: One message exceeds threshold
   - Cannot summarize meaningfully
   - Keep as-is or truncate

6. **All System Messages**: Session only has system prompts
   - No conversation to summarize
   - Keep all system messages

---

## Important: Timing of Session Persistence

### Critical Insight

When we prune in `call_model_input_filter`, we need to understand what the SDK saves:

```python
# SDK only saves the NEW items from this turn, not the full history
await self._save_result_to_session(session, original_input, new_items)
# Where original_input = just the new user message
# And new_items = assistant response, tool calls, etc.
```

This means:
1. We clear session and persist pruned HISTORY (summary + recent items, **excluding current user message**)
2. SDK then appends: current user message + assistant response
3. Result: pruned history + current turn

### Correct Pruning Logic

```python
async def _persist_pruned_session(self, pruned_items):
    """
    Persist only the BASE history (without current turn's user message).
    SDK will add the current turn's items automatically.
    """
    # pruned_items = [summary, recent_1, recent_2, recent_3, recent_4, current_user]
    # We save everything EXCEPT the last item (current user message)
    base_items = pruned_items[:-1]  # [summary, recent_1, recent_2, recent_3, recent_4]

    await self.session.clear_session()
    await self.session.add_items(base_items)

    # SDK will then add: [current_user, assistant_response]
    # Final session: [summary, recent_1-4, current_user, assistant_response]
```

### Why Not Use `session_input_callback`?

The `session_input_callback` in `RunConfig` is another hook point that handles history merging:

```python
session_input_callback: SessionInputCallback | None = None
"""Defines how to handle session history when new input is provided.
- `None` (default): The new input is appended to the session history.
- `SessionInputCallback`: A custom function that receives the history and new input.
"""
```

**Why we DON'T use it for pruning:**
1. It's called BEFORE the LLM call, before we have usage data
2. It doesn't have access to previous token counts
3. It only modifies the combined input, doesn't persist to session

**However**, it could be useful for lightweight filtering (e.g., always limit to last N messages without summarization). Our approach uses `call_model_input_filter` because:
1. We need the flag from `on_llm_end` (which has usage data)
2. We need to persist pruning to the session
3. We have access to the full context

---

## Open Questions

### Resolved ✅

1. **Pre-turn vs Post-turn Detection**: Should we only detect after LLM calls?
   - **Answer**: No! We now do BOTH:
     - Post-turn detection in `on_llm_end` (using actual usage)
     - Pre-turn detection in `call_model_input_filter` (using estimates + stored usage)
   - This handles both gradual growth AND large input scenarios

2. **Token Persistence**: Should we persist token counts to database?
   - **Answer**: Optional enhancement. In-memory tracking is sufficient for MVP since pruning can happen any time usage is high. Database persistence is useful for cross-request durability.

### Open Questions ❓

1. **Summary Content**: What should the summary message format be for optimal LLM understanding?

2. **What to Keep**: Should we keep:
   - Last N messages (current approach)
   - Last N user-assistant pairs
   - Messages from last X minutes
   - All tool calls from session

3. **Token Estimation Accuracy**: The `_estimate_tokens` method uses a simple 4-chars-per-token heuristic. Should we:
   - Use tiktoken for exact counts (slower, more accurate)
   - Keep the heuristic (faster, ~90% accurate for English)
   - Use a hybrid (tiktoken for large inputs only)

4. **Pruning the Current Turn**: When we prune in `call_model_input_filter`, the SDK will still save the current turn's items. Should we adjust the pruned items to account for this?

5. **Error Recovery**: If pruning fails, should we:
   - Continue with unpruned items (current approach)
   - Retry
   - Fail the turn

6. **Very Large Single Message**: What if one message alone exceeds the threshold?
   - Truncate the message?
   - Refuse and ask user to send smaller input?
   - Process anyway (let LLM truncate)?

---

## Alternative Approaches Considered

### Enhancement: Token Count Persistence in Database

For cross-request durability, we can optionally store token usage in the database:

```sql
-- Add columns to agent_sessions table
ALTER TABLE agent_sessions ADD COLUMN last_input_tokens INTEGER DEFAULT 0;
ALTER TABLE agent_sessions ADD COLUMN last_model_name VARCHAR(50);
ALTER TABLE agent_sessions ADD COLUMN token_updated_at TIMESTAMP;
```

**Implementation:**

```python
async def _persist_token_usage_to_db(
    self,
    input_tokens: int,
    model_name: str,
) -> None:
    """Optionally persist token usage for cross-request durability."""
    if not self.session:
        return

    try:
        # Use raw SQL or ORM to update the session record
        async with self.session._session_factory() as sess:
            async with sess.begin():
                await sess.execute(
                    update(self.session._sessions)
                    .where(self.session._sessions.c.session_id == self.session_id)
                    .values(
                        last_input_tokens=input_tokens,
                        last_model_name=model_name,
                        token_updated_at=sql_text("CURRENT_TIMESTAMP"),
                    )
                )
        self.logger.debug(f"Persisted token count: {input_tokens}")
    except Exception as e:
        self.logger.warning(f"Failed to persist token usage: {e}")

async def _load_token_usage_from_db(self) -> tuple[int, str]:
    """Load previously stored token usage on session start."""
    if not self.session:
        return 0, ""

    try:
        async with self.session._session_factory() as sess:
            result = await sess.execute(
                select(
                    self.session._sessions.c.last_input_tokens,
                    self.session._sessions.c.last_model_name,
                )
                .where(self.session._sessions.c.session_id == self.session_id)
            )
            row = result.first()
            if row:
                return row.last_input_tokens or 0, row.last_model_name or ""
    except Exception as e:
        self.logger.warning(f"Failed to load token usage: {e}")

    return 0, ""
```

**When to Use:**
- **In-memory only (default)**: Sufficient for most cases since pruning can happen any time usage is high
- **Database persistence**: Use when:
  - Service may restart between turns (rare in production)
  - Sessions span multiple deployments
  - Need audit trail of token usage

**Recommendation:** Start with in-memory tracking. Add database persistence as an enhancement if needed.

---

### Alternative 2: Proactive Pruning via Background Job

Run a background job that periodically checks session sizes and prunes proactively:

```python
async def prune_large_sessions():
    """Background job to prune sessions over threshold."""
    sessions = await get_all_sessions()
    for session in sessions:
        items = await session.get_items()
        token_count = estimate_tokens(items)
        if token_count > threshold:
            await prune_session(session)
```

**Pros:**
- Pruning happens outside of request path
- No latency impact on user

**Cons:**
- Complex to implement token estimation without model info
- May prune sessions that are about to be deleted anyway
- Harder to track which model context window to use

**Verdict:** Overkill for current needs. In-request pruning is simpler.

---

### Alternative 3: Sliding Window Only (No Summarization)

Instead of summarizing, just keep the last N items:

```python
def prune_to_window(items, max_items=20):
    """Simple sliding window pruning."""
    return items[-max_items:]
```

**Pros:**
- Much simpler
- No LLM call for summarization
- Faster

**Cons:**
- Loses context from older messages
- Agent may "forget" important information
- User experience degrades in long conversations

**Verdict:** Could be used as fallback if summarization fails. But primary approach should include summarization for better context retention.

---

### Alternative 4: Hierarchical Summarization

Create summaries of summaries as conversations get very long:

```
Items 1-100   → Summary A
Items 101-200 → Summary B
Summary A + B → Meta-Summary

Session: [Meta-Summary, Recent 10 items]
```

**Pros:**
- Handles very long conversations
- Preserves more nuanced context

**Cons:**
- Complex implementation
- Multiple LLM calls
- May introduce compounding summarization errors

**Verdict:** Future enhancement. Start with simple single-level summarization.

---

## Future Enhancements

1. **Type-Aware Pruning**
   - Different retention policies for different item types
   - Keep all tool calls from current session
   - Summarize only user/assistant messages

2. **Importance Scoring**
   - Use LLM to score message importance
   - Keep high-importance messages even if old
   - Prune low-importance messages first

3. **User Preference**
   - Allow users to "pin" important messages
   - Never prune pinned messages

4. **Compression**
   - Compress tool outputs (often verbose)
   - Store references instead of full content

---

## Checklist

### Implementation - Core
- [ ] Update `ContextManagerHooks.__init__` to accept session parameter
- [ ] Add `_last_input_tokens` and `_max_context_tokens` tracking fields
- [ ] Implement `_track_token_usage` in `on_llm_end`
- [ ] Implement `_pre_turn_threshold_check` in `call_model_input_filter`
- [ ] Implement `_estimate_tokens` helper method
- [ ] Implement `_check_pruning_threshold` (post-turn check)
- [ ] Implement `_persist_pruned_session` method
- [ ] Update `call_model_input_filter` to execute pruning
- [ ] Update `create_context_manager_hooks` factory
- [ ] Update `orchestration_service.py` to pass session to hooks
- [ ] Update `build_run_config` to accept hooks

### Implementation - Optional Enhancements
- [ ] Add database columns for token persistence (Alembic migration)
- [ ] Implement `_persist_token_usage_to_db`
- [ ] Implement `_load_token_usage_from_db`
- [ ] Load initial token count in hooks constructor

### Testing
- [ ] Unit tests for post-turn threshold detection
- [ ] Unit tests for pre-turn threshold detection (large input)
- [ ] Unit tests for token estimation
- [ ] Unit tests for pruning logic
- [ ] Unit tests for session persistence
- [ ] Integration test for gradual growth scenario
- [ ] Integration test for large input scenario
- [ ] Manual test with long conversation
- [ ] Manual test with large document paste

### Documentation
- [ ] Update `AGENT_REFACTORING_PLAN.md` Phase 4 checklist
- [ ] Add SSE event documentation for new events:
  - `context.pruning_scheduled` (with reason: `post_turn_threshold_exceeded` | `pre_turn_large_input`)
  - `context.summarizing`
  - `context.pruning_completed`
