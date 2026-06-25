# Agent Streaming Architecture Refactoring Plan

> **Status**: Planning
> **Created**: November 24, 2025
> **Last Updated**: November 24, 2025

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Issues](#current-architecture-issues)
3. [Key Decisions](#key-decisions)
4. [Proposed Architecture](#proposed-architecture)
5. [Implementation Phases](#implementation-phases)
   - **Phase 1: Code Cleanup** ⭐ **START HERE**
     - 1a. Agent Folder Reorganization
     - 1b. SSE Event Emitter Extraction
     - 1c. Tool Initializer Consolidation
     - 1d. Context Manager Simplification (remove buckets)
     - 1e. run_config Cleanup
   - Phase 2: SDK Sessions Integration
   - Phase 3: Trace Metadata
   - Phase 4: Type-Based Pruning
   - **Phase 5: Unify Ask/Agent Modes** (**LAST**)
6. [Detailed Changes](#detailed-changes)
7. [Migration Notes](#migration-notes)
8. [SDK Sessions Architecture](#sdk-sessions-integration-major-architecture-decision)

---

## Executive Summary

This document outlines the plan to refactor the agent streaming architecture in `rsgpt-ai-core` to improve:

- **Readability**: Separate concerns into focused modules
- **Scalability**: Type-safe message handling for future context management
- **Maintainability**: Remove redundancy and strengthen typing
- **Reliability**: Better error handling and cleaner SSE event emission

### Files Affected

| File | Change Type | Phase |
|------|-------------|-------|
| **Phase 1: Code Cleanup** | | |
| `app/services/agent/agents/` | **Remove folder** | 1a |
| `app/services/agent/main_agent.py` | Move from `agents/` | 1a |
| `app/services/agent/summarizer_agent.py` | Move from `agents/` | 1a |
| `app/services/agent/tools/` | **New folder** | 1a |
| `app/services/agent/tools/base_tools.py` | Move from `agent_tools.py` | 1a |
| `app/services/agent/tools/device_tools.py` | Rename from `dynamic_tool_factory.py` | 1a |
| `app/services/agent/orchestration_service.py` | Rename + refactor | 1a-1e |
| `app/services/agent/sse_event_emitter.py` | **New file** | 1b |
| `app/services/agent/tools/tool_initializer.py` | **New file** | 1c |
| `app/services/context_manager/bucket_tracker.py` | **Remove entirely** | 1d |
| `app/services/context_manager/context_manager_hooks.py` | Major simplification | 1d |
| **Phase 2: SDK Sessions** | | |
| `app/services/agent/session_factory.py` | **New file** | 2 |
| `app/config.py` | Add `SESSION_DATABASE_URL` | 2 |
| **Phase 3-4: Enhancements** | | |
| `app/models/agent.py` | Add `user_id`, `mode` fields | 3, 5 |
| **Phase 5: Unify Modes** | | |
| `app/services/streaming/streaming_service.py` | **Deprecate/Remove** | 5 |
| `app/api/routes/chat.py` | **Deprecate/Remove** `/stream` | 5 |

---

## Current Architecture Issues

### 1. Conversation History Organization

**Current State** (`dynamic_orchestration_service.py:201-209`):
```python
conversation_history = []
for msg in request.messages:
    conversation_history.append({
        "role": msg.role,
        "content": msg.content,
    })
```

**Problems**:
- Loses type information by flattening to simple dicts
- No distinction between user messages, assistant messages, tool calls, tool outputs
- Cannot apply type-based pruning/summarization heuristics

### 2. SSE Event Handling Overload

**Current State** (`_stream_agent_execution`: lines 730-996):
- ~270 lines handling multiple responsibilities:
  - Event type detection (via `hasattr`)
  - Tool call state tracking
  - SSE event formatting and emission
  - Thinking buffer management
  - Error handling

**Problems**:
- Hard to test individual concerns
- `hasattr`-based type checking is fragile
- Mixing filtering logic with emission logic

### 3. Redundant Tool Initialization

**Current State**:
- **First init** (`_initialize_tools`: lines 603-675): Creates tools without agent reference
- **Second init** (`_execute`: lines 490-528): Re-creates device tools WITH agent reference

```python
# Step 1: Initialize tools (no agent ref)
all_tools = await self._initialize_tools(request)

# ... create agent ...

# Step 4: Re-initialize device tools with agent reference (WHY?)
if request.device_id:
    device_tools = parse_device_tools_to_functions(
        device_id=request.device_id,
        json_tools=json_tools,
        agent_ref=main_agent,  # NOW we have the ref
        update_callback=update_agent_tools,
    )
    # Replace in agent
    main_agent.tools = base_tools + device_tools
```

**Problem**: Duplicate work, confusing flow, wasteful API calls.

### 4. run_config Injection Pattern

**Current State** (`_execute`: lines 534-551):
```python
run_config = None
if hasattr(main_agent, "hooks") and main_agent.hooks:
    hooks = main_agent.hooks
    if hasattr(hooks, "call_model_input_filter"):
        run_config = RunConfig(
            call_model_input_filter=hooks.call_model_input_filter
        )
```

**Problems**:
- Hooks attached to agent, then extracted for run_config
- `hasattr` checks instead of type-safe access
- Unclear ownership of hooks

### 6. Missing Trace Metadata

**Current State**: Trace only has `trace_id`.

**Missing**:
- `user_id`
- `session_id`
- `ai_response_id` (final assistant message)

-> We will need to store this from rsgpt-be

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single blob vs structured messages | **Structured** | Enables type-based pruning |
| Store thinking blocks | **YES** | |
| Bucket percentages vs type heuristics | **Type heuristics** | More flexible, uses SDK types |
| Filter tool calls from history | **Keep all for now** | Apply heuristics later if needed |
| RSLog MCP connection | **Keep but evaluate** | Remove for now (may add it later) |
| SDK Sessions adoption | **YES (Option C)** | Simplifies context management, full type preservation |
| Database architecture | **Separate DBs** | AI-Core owns its DB, BE owns its DB (true microservice) |
| AI-Core database | **Own Neon Postgres** | Independent storage, no shared DB concerns |
| Keep BE timeline storage | **YES (dual storage)** | Frontend needs optimized format, agent needs raw format |
| Unify Ask/Agent modes | **YES (Agent SDK for both)** | Unified session, seamless context switching, single code path |

---

## Proposed Architecture

### High-Level Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DynamicOrchestrationService                          │
│  Responsibilities:                                                       │
│  - Workflow lifecycle (start/complete/fail)                             │
│  - Trace management with metadata                                        │
│  - Coordination between components                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────┐
│   ToolInitializer   │  │    SSEEventEmitter      │  │ ConversationBuilder │
│                     │  │                         │  │                     │
│ - Single-pass init  │  │ - Filter SDK events     │  │ - Build typed items │
│ - Device tools      │  │ - Format SSE strings    │  │ - Handle summary    │
│ - MCP servers       │  │ - Track tool state      │  │ - Type preservation │
│ - Base tools        │  │ - Emit to stream        │  │                     │
└─────────────────────┘  └─────────────────────────┘  └─────────────────────┘
```

### Data Flow (with SDK Sessions)

```
Request from BE: { session_id, user_message, model, device_id, ... }
   │
   │  (BE no longer sends full history - AI-Core has it)
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SDK Session loads history from AI-Core's database                       │
│   → session.get_items(session_id)                                       │
│   → Returns: [previous items, maybe summary, recent messages...]        │
└─────────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ToolInitializer.initialize(request)                                     │
│   → (tools, mcp_servers)                                                │
└─────────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ create_main_agent(model, tools, mcp_servers, ...)                       │
│   → Agent[AgentContext]                                                 │
└─────────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Runner.run_streamed(agent, input=user_message, session=session, ...)    │
│   │                                                                     │
│   ├─► call_model_input_filter: may prune & persist summary to session   │
│   │                                                                     │
│   └─► StreamedRunResult                                                 │
└─────────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SSEEventEmitter.process_stream(agent_result)                            │
│   → AsyncGenerator[str, None] (SSE strings to BE)                       │
└─────────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SDK Session stores new items to AI-Core's database                      │
│   → session.add_items([user_msg, assistant_response, tool_calls, ...])  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

> **Phase Order Rationale**:
> 1. **Code Cleanup FIRST** - Clean foundation before adding new features
> 2. **SDK Sessions** - Add on clean codebase
> 3. **Enhancements** - Build on SDK Sessions
> 4. **Mode unification LAST** - Builds on everything

---

### Phase 1: Code Cleanup & Reorganization 🧹 **START HERE**

**Goal**: Clean up the codebase structure before adding new features. Remove redundancy, simplify, reorganize.

#### 1a. Agent Folder Reorganization

**Current Structure** (messy):
```
app/services/agent/
├── agents/                    # Unnecessary nesting
│   ├── __init__.py
│   ├── agent_config.py
│   ├── agent_factory.py
│   ├── main_agent.py
│   └── summarizer_agent.py
├── agent_tools.py
├── dynamic_orchestration_service.py
└── dynamic_tool_factory.py
```

**Proposed Structure** (flat, clear):
```
app/services/agent/
├── __init__.py
├── orchestration_service.py      # Renamed from dynamic_orchestration_service.py
├── main_agent.py                  # Moved up from agents/
├── summarizer_agent.py            # Moved up from agents/
├── agent_config.py                # Moved up from agents/
├── agent_factory.py               # Moved up from agents/
├── tools/                         # Group tool-related code
│   ├── __init__.py
│   ├── base_tools.py              # search_knowledge, search_web
│   ├── device_tools.py            # Renamed from dynamic_tool_factory.py
│   └── tool_initializer.py        # NEW: consolidated initialization
├── sse_event_emitter.py           # NEW: extracted from orchestration
└── session_factory.py             # NEW (Phase 2): SDK session creation
```

**Changes**:
1. Remove `agents/` subfolder - move files up one level
2. Rename `dynamic_orchestration_service.py` → `orchestration_service.py`
3. Create `tools/` subfolder for tool-related code
4. Rename `dynamic_tool_factory.py` → `tools/device_tools.py`
5. Split `agent_tools.py` → `tools/base_tools.py`

#### 1b. SSE Event Emitter Extraction

**Goal**: Extract SSE event handling from `_stream_agent_execution` (~270 lines).

**New File**: `app/services/agent/sse_event_emitter.py`

**Changes**:
1. Create `SSEEventEmitter` class
2. Move event filtering logic out of orchestration service
3. Replace `hasattr` checks with `isinstance` for SDK types

#### 1c. Tool Initializer Consolidation

**Goal**: Single-pass tool initialization, remove redundancy.

**New File**: `app/services/agent/tools/tool_initializer.py`

**Changes**:
1. Create `ToolInitializer` class
2. Merge duplicate device tool initialization
3. Consolidate MCP server initialization

#### 1d. Context Manager Simplification

**Goal**: Remove bucket implementation, simplify `context_manager_hooks.py`.

**Current** (`context_manager_hooks.py`): ~1226 lines with bucket tracking

**Target**: ~400-500 lines focused on:
- `call_model_input_filter` for pruning (will persist to SDK session in Phase 2)
- `on_llm_end` for usage tracking
- Remove: `BucketTracker`, bucket allocation logic, complex bucket calculations

**Files to simplify/remove**:
- `context_manager_hooks.py` - Major simplification
- `bucket_tracker.py` - **Remove entirely** (replaced by type-based pruning)

#### 1e. run_config Cleanup

**Goal**: Clean separation between agent and run configuration.

**Changes**:
1. Don't attach hooks to agent
2. Build `RunConfig` explicitly
3. Pass hooks directly to `RunConfig.call_model_input_filter`

**Estimated Effort**: 8-12 hours total for Phase 1

---

### Phase 2: SDK Sessions Integration 🔄 **HIGH PRIORITY**

**Goal**: Add SDK session memory on the now-clean codebase.

**New File**: `app/services/agent/session_factory.py`

**Changes**:
1. Create new Neon PostgreSQL instance for AI-Core
2. Add `SESSION_DATABASE_URL` to config
3. Create session factory for SQLAlchemy sessions
4. Update orchestration service to use SDK session
5. Simplify BE request (just new message + session_id)
6. Update `call_model_input_filter` to persist pruning to session

**Benefits**:
- Automatic history retrieval before each run
- Automatic storage of all items
- Full `TResponseInputItem` type preservation
- Pruning persists across turns

**Dependencies**: Phase 1 (clean codebase)

**Estimated Effort**: 6-8 hours

---

### Phase 3: Trace Metadata ✅ Low Risk

**Goal**: Add required metadata to traces.

**Changes**:
1. Add `user_id` field to `AgentRequest` model
2. Pass metadata to `trace()` context manager
3. Store final `ai_response` in trace

**Estimated Effort**: 1 hour

---

### Phase 4: Type-Based Pruning ⚠️ Medium Risk

**Goal**: Implement intelligent pruning that persists to SDK session.

**Changes**:
1. Update `call_model_input_filter` to use item types
2. Implement pruning strategies per item type
3. Persist pruning to session (`session.clear_session()` + `session.add_items(pruned)`)

**Dependencies**: Phase 2 (SDK Sessions)

**Estimated Effort**: 4-6 hours

---

### Phase 5: Unify Ask and Agent Modes 🔄 **LAST**

**Goal**: Use Agent SDK for both Ask and Agent modes to ensure unified session storage and seamless context switching.

**Problem Statement**:
Currently, Ask mode uses direct LLM calls (`streaming_service.py`) while Agent mode uses the Agent SDK. This creates:
- Split context: Ask mode history not in SDK session
- Lost context when switching modes
- Two code paths to maintain
- Inconsistent event formats

**Solution**: Run both modes through Agent SDK with different configurations:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│   Ask Mode (Agent SDK)                  Agent Mode (Agent SDK)              │
│   ════════════════════                  ══════════════════════              │
│                                                                              │
│   • Tools: search_knowledge,            • Tools: All (search, device, MCP)  │
│            search_web                   • max_turns: 10                     │
│   • max_turns: 3                        • Full autonomous instructions      │
│   • Conversational instructions         • Complex workflows                 │
│   • Quick Q&A responses                                                     │
│                                                                              │
│            └──────────────────┬─────────────────────────┘                   │
│                               ▼                                              │
│                       ┌───────────────┐                                     │
│                       │  SDK Session  │  ← UNIFIED STORAGE                  │
│                       └───────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Mode Configurations**:

```python
# Ask Mode: Conversational, limited scope
ASK_MODE_CONFIG = {
    "tools": ["search_knowledge", "search_web"],
    "max_turns": 3,
    "instructions": ASK_MODE_INSTRUCTIONS,
}

# Agent Mode: Autonomous, full capabilities
AGENT_MODE_CONFIG = {
    "tools": [*base_tools, *device_tools, *mcp_tools],
    "max_turns": 10,
    "instructions": AGENT_MODE_INSTRUCTIONS,
}
```

**Files to Remove/Deprecate**:
- `app/services/streaming/streaming_service.py` - No longer needed
- `app/api/routes/chat.py` `/stream` endpoint - Merge into agent endpoint

**Changes**:
1. Add `mode` field to `AgentRequest` (ask | agent)
2. Create mode-specific agent configurations
3. Write `ASK_MODE_INSTRUCTIONS` (conversational, suggests agent mode for complex tasks)
4. Route both modes through `DynamicOrchestrationService`
5. Remove `streaming_service.py` dependency
6. Update BE to always use agent endpoint

**Benefits**:
- ✅ Unified session storage for both modes
- ✅ Seamless context when switching modes
- ✅ Single code path to maintain
- ✅ Consistent SSE event format
- ✅ Future flexibility via configuration

**Ask Mode Instructions** (Draft):

```python
ASK_MODE_INSTRUCTIONS = """
You are the RSInsight Assistant, helping with Rocscience software questions.

## Your Approach
1. **Search first** - Use search_knowledge to find relevant documentation
2. **Answer concisely** - Provide clear, direct answers
3. **Cite sources** - Reference documentation when available
4. **Stay focused** - Quick, helpful responses

## What You Can Do
- Answer questions about Rocscience software
- Search documentation and knowledge base
- Explain concepts and best practices

## What You Cannot Do
- Execute operations on the user's device
- Run multi-step autonomous workflows

If the user needs device operations or complex workflows, suggest:
"For that task, I'd recommend switching to Agent mode where I can
directly interact with your Rocscience software."
"""
```

**Estimated Effort**: 4-6 hours

**Dependencies**: Phase 7 (SDK Sessions) should be complete first

**Rollout Strategy**:
1. Implement Ask mode via Agent SDK alongside existing streaming service
2. A/B test for quality parity
3. Deprecate streaming service
4. Remove old code path

---

## Detailed Changes

### New Files

#### `app/services/agent/session_factory.py` (Phase 2)

```python
"""Session Factory for Agent Execution.

Creates SDK sessions backed by AI-Core's own PostgreSQL database.
"""

from typing import Optional
from agents.extensions.memory import SQLAlchemySession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from app.config import settings

_engine: Optional[AsyncEngine] = None


async def get_session_engine() -> AsyncEngine:
    """Get or create the session database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.session_database_url,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


async def create_agent_session(session_id: str) -> SQLAlchemySession:
    """
    Create SDK session for the given chat session ID.

    Uses AI-Core's own database, not BE's.
    Session ID matches BE's chat_session.id for correlation.

    Args:
        session_id: The chat session ID from BE

    Returns:
        SQLAlchemySession configured for this session
    """
    engine = await get_session_engine()
    return SQLAlchemySession(
        session_id=session_id,
        engine=engine,
        create_tables=True,  # Auto-creates table on first use
    )
```

#### `app/services/agent/sse_event_emitter.py` (Phase 1b)

```python
"""SSE Event Emitter for Agent Streaming.

Handles filtering and emission of Server-Sent Events from agent execution.
Separates event processing concerns from orchestration logic.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, AsyncGenerator

from agents.items import TResponseInputItem

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """Typed SSE event container."""
    event_type: str
    data: Dict[str, Any]
    sequence_number: int


class SSEEventEmitter:
    """
    Handles filtering and emission of Server-Sent Events.

    Responsibilities:
    - Filter raw SDK events into meaningful SSE events
    - Track tool call state (id -> name mapping)
    - Format events for SSE wire format
    - Manage thinking buffer (display only, never store)

    Usage:
        emitter = SSEEventEmitter(agent_name="RSInsight Agent")

        async for event in agent_result.stream_events():
            sse_event = emitter.process_event(event, seq_num)
            if sse_event:
                yield emitter.format_sse(sse_event)
    """

    def __init__(self, agent_name: str = "RSInsight Agent"):
        self.agent_name = agent_name
        self._tool_call_names: Dict[str, str] = {}
        self._thinking_buffer: str = ""

    @staticmethod
    def format_sse(event_type: str, data: dict) -> str:
        """Format event as SSE string."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    def process_event(
        self,
        event: Any,
        sequence_number: int,
    ) -> Optional[SSEEvent]:
        """Process a single stream event and return SSE event if applicable."""
        # Implementation moved from _stream_agent_execution
        ...

    def reset(self) -> None:
        """Reset state for new run."""
        self._tool_call_names.clear()
        self._thinking_buffer = ""
```

#### `app/services/agent/tools/tool_initializer.py` (Phase 1c)

```python
"""Tool Initializer for Agent Execution.

Single-pass initialization of all tools (base, device, MCP).
"""

import logging
from typing import Any, Callable, List, Optional, Tuple

from app.models.agent import AgentRequest
from app.services.agent.agent_tools import search_knowledge, search_web
from app.services.agent.dynamic_tool_factory import parse_device_tools_to_functions
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)


class ToolInitializer:
    """
    Initializes all tools for agent execution in a single pass.

    Eliminates redundant device tool initialization by using a deferred
    agent reference pattern.

    Usage:
        initializer = ToolInitializer()
        tools, mcp_servers = await initializer.initialize(
            request=request,
            agent_ref_getter=lambda: main_agent,  # Deferred
        )
    """

    async def initialize(
        self,
        request: AgentRequest,
        agent_ref_getter: Optional[Callable[[], Any]] = None,
        update_callback: Optional[Callable] = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Initialize all tools and MCP servers.

        Args:
            request: Agent request with configuration
            agent_ref_getter: Callable that returns agent reference (deferred)
            update_callback: Callback for dynamic tool updates

        Returns:
            Tuple of (tools, mcp_servers)
        """
        tools = []
        mcp_servers = []

        # 1. Base tools (always available)
        tools.extend([search_knowledge, search_web])
        logger.info("✓ Base tools added (search_knowledge, search_web)")

        # 2. Device tools (if device connected)
        if request.device_id:
            device_tools = await self._initialize_device_tools(
                device_id=request.device_id,
                agent_ref_getter=agent_ref_getter,
                update_callback=update_callback,
            )
            tools.extend(device_tools)

        # 3. RSLog MCP server (if enabled)
        if request.rslog_mcp_enabled:
            rslog_server = await self._initialize_rslog_mcp(request)
            if rslog_server:
                mcp_servers.append(rslog_server)

        return tools, mcp_servers

    async def _initialize_device_tools(
        self,
        device_id: str,
        agent_ref_getter: Optional[Callable[[], Any]],
        update_callback: Optional[Callable],
    ) -> List[Any]:
        """Initialize device tools with optional agent reference."""
        if not connection_manager.is_device_connected(device_id):
            logger.warning(f"Device '{device_id}' requested but not connected")
            return []

        try:
            logger.info(f"Loading tools for device {device_id}...")
            tools_response = await connection_manager.request_list_tools(
                device_id, timeout=30.0
            )

            if tools_response.get("error"):
                logger.error(f"Error fetching device tools: {tools_response.get('error')}")
                return []

            json_tools = tools_response.get("tools", [])
            logger.info(f"Fetched {len(json_tools)} tools from device {device_id}")

            # Parse with agent reference getter (deferred)
            device_tools = parse_device_tools_to_functions(
                device_id=device_id,
                json_tools=json_tools,
                agent_ref=agent_ref_getter,  # Pass getter, not value
                update_callback=update_callback,
            )

            logger.info(f"✓ Added {len(device_tools)} device tools for '{device_id}'")
            return device_tools

        except Exception as e:
            logger.error(f"Failed to load device tools: {e}", exc_info=True)
            return []

    async def _initialize_rslog_mcp(self, request: AgentRequest) -> Optional[Any]:
        """Initialize RSLog MCP server."""
        # Implementation moved from _initialize_rslog_mcp_server
        ...
```

---

### Modified Files

#### `app/models/agent.py`

```python
class AgentRequest(BaseModel):
    # ... existing fields ...

    # NEW: User ID for trace metadata
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for trace metadata and analytics",
    )
```

#### `app/services/agent/dynamic_orchestration_service.py`

**Before** (~1239 lines):
- `generate_workflow_stream`: 150+ lines
- `_execute`: 200+ lines
- `_stream_agent_execution`: 270+ lines
- Duplicate tool initialization

**After** (~600 lines estimated):
- `generate_workflow_stream`: ~80 lines (lifecycle only)
- `_execute`: ~100 lines (coordination only)
- Event streaming delegated to `SSEEventEmitter`
- Tool init delegated to `ToolInitializer`
- Message building delegated to `ConversationBuilder`

---

## Migration Notes

### Backward Compatibility

- All SSE event types remain the same
- No changes to `AgentRequest` required fields
- No changes to frontend event handling needed

### Testing Strategy

1. **Unit Tests** for new classes:
   - `SSEEventEmitter.process_event()` with various SDK event types
   - `ConversationBuilder.build_from_request()` with summary/no summary
   - `ToolInitializer.initialize()` with various device states

2. **Integration Tests**:
   - Full workflow with mocked device connection
   - SSE event sequence verification

3. **Manual Testing**:
   - Verify SSE events in browser dev tools
   - Check thinking blocks are NOT persisted
   - Verify tool calls work end-to-end

### Rollback Plan

Each phase can be implemented and merged independently. If issues arise:

1. Revert the specific phase PR
2. Previous implementation remains functional
3. No database migrations required

---

## Checklist

### Phase 1: Code Cleanup & Reorganization ⭐ **START HERE**

#### 1a. Agent Folder Reorganization
- [X] Create `app/services/agent/tools/` directory
- [X] Move `agents/main_agent.py` → `app/services/agent/main_agent.py`
- [X] Move `agents/summarizer_agent.py` → `app/services/agent/summarizer_agent.py`
- [X] Move `agents/agent_config.py` → `app/services/agent/agent_config.py`
- [X] Move `agents/agent_factory.py` → `app/services/agent/agent_factory.py`
- [X] Delete `agents/` subfolder
- [X] Move `agent_tools.py` → `tools/base_tools.py`
- [X] Move `dynamic_tool_factory.py` → `tools/device_tools.py`
- [X] Rename `dynamic_orchestration_service.py` → `orchestration_service.py`
- [X] Update all imports across codebase
- [X] Verify tests pass after reorganization

#### 1b. SSE Event Emitter Extraction
- [X] Create `app/services/agent/sse_event_emitter.py`
- [X] Implement `SSEEventEmitter` class
- [X] Replace `hasattr` checks with `isinstance` for SDK types
- [X] Move event filtering logic from `_stream_agent_execution`
- [X] Add unit tests for event processing
- [X] Verify SSE events match existing behavior

#### 1c. Tool Initializer Consolidation
- [X] Create `app/services/agent/tools/tool_initializer.py`
- [X] Implement `ToolInitializer` class
- [X] Merge duplicate device tool initialization
- [X] Update `parse_device_tools_to_functions` for deferred refs
- [X] Remove duplicate initialization in `_execute`
- [X] Verify device tools work correctly

#### 1d. Context Manager Simplification ✅
- [x] Remove `bucket_tracker.py` entirely
- [x] Simplify `context_manager_hooks.py`:
  - [x] Remove bucket allocation logic
  - [x] Remove `_calculate_bucket_allocation_and_summarize`
  - [x] Remove `_log_bucket_analysis`
  - [x] Keep `call_model_input_filter` (simplified)
  - [x] Keep `on_llm_end` for usage tracking
  - [x] Keep `on_start`, `on_end` for session lifecycle
- [x] Target: ~511 lines (down from ~1226) ✅
- [x] Updated tests in `test_context_manager_hooks.py` (21 tests passing)

#### 1e. run_config Cleanup ✅
- [x] Remove hooks creation from `create_main_agent()` (now accepts hooks param)
- [x] Build `RunConfig` explicitly in orchestration service via `_build_run_config()`
- [x] Create hooks in orchestration service via `_create_context_hooks()`
- [x] Pass hooks directly to `RunConfig.call_model_input_filter`
- [x] Verify context management still works (18 tests passing)

---

### Phase 2: SDK Sessions Integration
- [X] **Infrastructure Setup**
  - [X] Create new Neon PostgreSQL instance for AI-Core
  - [X] Add `SESSION_DATABASE_URL` to `app/config.py`
  - [X] Configure connection pooling (10-20 connections)
  - [X] Set up environment variables in deployment
- [X] **Implementation**
  - [X] Create `app/services/agent/session_factory.py`
  - [X] Add `use_sdk_session` flag to `AgentRequest` (opt-in)
  - [X] Update orchestration service to create and pass SDK session
  - [X] Pass session reference to context hooks for pruning persistence
- [X] **Testing**
  - [X] Test session persistence across runs
  - [X] Verify timeline storage still works (dual storage)
  - [X] Load test session operations
- [X] **BE Coordination**
  - [X] Update BE to send simplified payload when SDK session enabled
  - [X] Document new request format

---

### Phase 3: Trace Metadata
- [ ] Add `user_id` to `AgentRequest`
- [ ] Update trace context with metadata
- [ ] Verify traces include new fields

---

### Phase 4: Type-Based Pruning
- [ ] Design pruning strategy per item type
- [ ] Update `call_model_input_filter` to persist pruning to session
- [ ] Implement `session.clear_session()` + `session.add_items(pruned)` flow
- [ ] Add configuration for thresholds
- [ ] Test with long conversations
- [ ] Verify pruning persists across turns

---

### Phase 5: Unify Ask and Agent Modes (**LAST**)
- [X] **Configuration**
  - [X] Add `mode` field to `AgentRequest` ("ask" | "agent")
  - [X] Create `ASK_MODE_INSTRUCTIONS` prompt, derived from the current chat stream
        instructions
  - [X] Create mode configuration constants
- [ ] **Implementation**
  - [X] Update `_execute` to handle mode-specific configuration
  - [X] Create `create_ask_mode_agent()` helper (or unified with mode param)
  - [X] Limit tools for Ask mode (search_knowledge, search_web only)
        The perplexity models are not allowed to have tools!
  - [X] Set `max_turns` = 10 for ask mode, and instruct the AI to use less than that
  - [ ] The fallback mechanism when hitting max_turns is similar to the summarizer agent
        in the same trace it will make a final call to the LLM with a smooth user experience
        to prompt the user to let the LLM know if they would like to continue.
- [ ] **Testing**
  - [ ] Test Ask mode quality parity with old streaming service
  - [ ] Test context preservation when switching modes
  - [ ] Test session stores both Ask and Agent conversations
  - [ ] Verify SSE events are consistent
- [ ] **Deprecation**
  - [ ] Mark `streaming_service.py` as deprecated
  - [ ] Mark `/chat/stream` endpoint as deprecated
  - [ ] Update BE to use agent endpoint for both modes
- [ ] **Cleanup** (after rollout stable)
  - [ ] Remove `streaming_service.py`
  - [ ] Remove `/chat/stream` endpoint
  - [ ] Remove BE's separate chat/agent code paths

---

## Questions / Decisions Needed

### Resolved ✅

1. **SDK Sessions**: Should we adopt SDK built-in session memory?
   - **Decision**: YES (Option C - AI-Core with own database)
   - **Rationale**: True microservice separation, low latency, clean boundaries

2. **Database Architecture**: Should AI-Core share BE's database?
   - **Decision**: NO - AI-Core gets its own PostgreSQL (Neon)
   - **Rationale**:
     - Multiple services sharing DB is anti-pattern
     - Each service owns its data
     - Independent scaling and optimization
     - Easy with Neon (spin up in minutes)

3. **Keep BE Storage**: Should we keep TimelineCoalescer storage?
   - **Decision**: YES (dual storage)
   - **Rationale**: Frontend needs optimized blocks, agent needs raw items

4. **Session Mutability**: Should pruning be temporary (per-call) or persistent?
   - **Decision**: **Persistent** - prune AND persist to session
   - **Rationale**: Prevents re-loading pruned items on subsequent turns
   - **Implementation**: `call_model_input_filter` calls `session.clear_session()` + `session.add_items(pruned)`

5. **BE Timeline vs SDK Session semantics**:
   - **Decision**: Different mutability
   - **BE Timeline**: Append-only audit log (never delete)
   - **SDK Session**: Mutable working memory (prune, delete, replace)

6. **Ask Mode vs Agent Mode**: Should they use different code paths?
   - **Decision**: NO - Unify both under Agent SDK
   - **Rationale**:
     - Unified session storage for both modes
     - Context preserved when switching modes
     - Single code path to maintain
     - Consistent SSE events
   - **Implementation**: Same orchestration service, mode-specific configuration

7. **Summary Storage**: Where and how should summaries be stored?
   - **Decision**: As a regular session item in AI-Core's `session_items` table
   - **Rationale**:
     - Summaries are just `EasyInputMessageParam` with `role: "system"`
     - No separate table needed - part of normal session flow
     - SDK automatically includes summary when loading session
     - Simplest possible implementation
   - **Implementation**:
     ```python
     summary_item = {"role": "system", "content": "Summary: ...", "type": "message"}
     await session.clear_session()
     await session.add_items([summary_item, *recent_items])
     ```

### Open Questions ❓

4. **RSLog MCP**: Should we remove this initialization if rarely used? Or keep for completeness?

5. **Deferred Agent Reference**: The device tools need agent reference for dynamic updates. Should we:
   - Pass a getter function (proposed)
   - Use a post-init hook
   - Accept the two-phase initialization

6. **Thinking Block Storage**: Current implementation streams thinking but doesn't explicitly prevent storage. Should we add a flag to `AgentThinkingEvent` marking it as ephemeral?

7. **User ID Source**: Where does `user_id` come from in the BE→AI-Core request? Is it in the token or needs explicit field?

8. **Session Data Retention**: How long do we keep `session_items` in AI-Core's DB?
    - Same retention as BE's chat sessions?
    - Separate TTL policy?
    - Clean up when BE deletes chat session? (Would need notification mechanism)

9. **Thinking in SDK Session**: SDK stores assistant messages. Do we need to filter out thinking content before storage?
    - SDK doesn't separate thinking from output
    - May need custom serialization hook
    - Note: Since session is mutable working memory, thinking content would be pruned naturally over time
    - But should we filter it BEFORE initial storage? (Security consideration)

10. **BE Request Simplification**: When SDK session enabled, what does BE send?
    - Just new user message (AI-Core loads history from its own DB)
    - Session ID
    - Configuration (model, device_id, etc.)
    - Smaller payload, simpler interface

11. **Neon Setup**: Production database setup for AI-Core
    - Create new Neon project for `rsgpt-ai-core`
    - Connection string in environment/secrets
    - Backup and monitoring configuration

---

## SDK Sessions Integration (Major Architecture Decision)

> **Status**: Under Discussion
> **Impact**: High - affects data storage, service boundaries, and context management

### Background

The OpenAI Agents SDK provides built-in **Session Memory** that automatically:
- **Before each run**: Retrieves conversation history and prepends to input
- **After each run**: Stores all new items (user input, assistant responses, tool calls, tool outputs)
- **Preserves context**: Full conversation history with typed `TResponseInputItem` items

This could significantly simplify our context management and provide richer data for future use.

### Current Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│    Frontend     │ ──────► │    rsgpt-be     │ ──────► │  rsgpt-ai-core  │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                    │
                                    ▼
                            ┌─────────────────┐
                            │   PostgreSQL    │
                            │                 │
                            │ - UserMessages  │  ← user messages (role: user)
                            │ - AIResponses   │  ← timeline blocks (message_block,
                            │                 │     thinking_block, tool_execution_block)
                            └─────────────────┘
```

**Data Flow**:
1. BE receives user message, stores in `UserMessagesORM`
2. BE sends request to AI-Core with `messages` array
3. AI-Core converts to simple `{role, content}` dicts
4. AI-Core runs agent, streams SSE events
5. BE coalesces events via `TimelineCoalescer` into blocks
6. BE stores blocks as AI response timeline

**Limitations**:
- AI-Core has no memory of previous runs
- Tool calls/outputs not stored in a format agent can reuse
- Manual history reconstruction from BE format
- No automatic context preservation

### SDK Sessions Option

The SDK provides `SQLAlchemySession` that can use our existing PostgreSQL:

```python
from agents.extensions.memory import SQLAlchemySession

# Create session using existing database
session = SQLAlchemySession.from_url(
    session_id=chat_session_id,  # Our existing session ID
    url="postgresql+asyncpg://...",
    create_tables=True
)

# Runner automatically handles history
result = await Runner.run(
    agent,
    user_message,
    session=session
)
```

### Architecture Options

#### Option A: AI-Core with Shared DB Access

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│    Frontend     │ ──────► │    rsgpt-be     │ ──────► │  rsgpt-ai-core  │
└─────────────────┘         └─────────────────┘         └────────┬────────┘
                                    │                            │
                                    ▼                            ▼
                            ┌─────────────────────────────────────────────┐
                            │              PostgreSQL (shared)             │
                            └─────────────────────────────────────────────┘
```

**Cons**:
- ❌ Two services accessing same DB (anti-pattern)
- ❌ Schema coupling between services
- ❌ Connection pool contention
- ❌ Harder to scale independently

---

#### Option B: Custom Session via BE API

```
┌─────────────────┐         ┌─────────────────┐  ◄────►  ┌─────────────────┐
│    Frontend     │ ──────► │    rsgpt-be     │  (HTTP)  │  rsgpt-ai-core  │
└─────────────────┘         └─────────────────┘          └─────────────────┘
                                    │                     (stateless)
                                    ▼
                            ┌─────────────────┐
                            │   PostgreSQL    │
                            └─────────────────┘
```

AI-Core implements custom `SessionABC` that calls BE via HTTP.

**Pros**:
- ✅ Clean service boundary
- ✅ BE owns all data

**Cons**:
- ⚠️ Network latency on session operations
- ⚠️ Need to implement 4 BE endpoints
- ⚠️ More complex error handling

---

#### Option C: AI-Core with Own Database (Recommended) ⭐

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│    Frontend     │ ──────► │    rsgpt-be     │ ──────► │  rsgpt-ai-core  │
└─────────────────┘         └─────────────────┘         └────────┬────────┘
                                    │                            │
                                    ▼                            ▼
                            ┌─────────────┐             ┌─────────────┐
                            │ BE Postgres │             │ AI-Core     │
                            │   (Neon)    │             │ Postgres    │
                            │             │             │   (Neon)    │
                            │ • Users     │             │             │
                            │ • Chats     │             │ • Sessions  │
                            │ • Timeline  │             │   (items)   │
                            │ • Messages  │             │             │
                            └─────────────┘             └─────────────┘
```

**True microservice separation** - each service owns its own database.

**Pros**:
- ✅ True microservice separation - each service owns its data
- ✅ No shared DB concerns (no coupling, no contention)
- ✅ Low latency (direct DB access, no HTTP overhead)
- ✅ Can use SDK's `SQLAlchemySession` directly
- ✅ Independent scaling
- ✅ Easy with Neon (spin up new DB in minutes)
- ✅ AI-Core can optimize its storage independently
- ✅ Full `TResponseInputItem` types preserved

**Cons**:
- ⚠️ Another database to manage (but Neon makes this trivial)
- ⚠️ Data in two places (but different data for different purposes)

---

### Recommendation: Option C (AI-Core with Own Database)

**Why Option C is the best choice**:

1. **True Microservice Architecture**: Each service owns its data store
2. **Best Performance**: Direct DB access, no HTTP overhead
3. **Clean Boundaries**: BE doesn't know about AI-Core's internals
4. **Simple Implementation**: SDK's `SQLAlchemySession` works directly
5. **Independent Operations**: Can scale, optimize, backup independently
6. **Easy Setup**: Neon allows spinning up new DB in minutes
7. **Future-Proof**: AI-Core can add more tables as needed (analytics, etc.)

**Data Ownership**:

| Service | Database | Data | Purpose |
|---------|----------|------|---------|
| **rsgpt-be** | BE Postgres | Users, Chats, UserMessages, AIResponses (timeline) | User data, UI display |
| **rsgpt-ai-core** | AI-Core Postgres | SessionItems (`TResponseInputItem`) | Agent context, LLM input |

**Key Insight**: These are **different data for different purposes**:
- BE stores what the **user sees** (timeline blocks with timestamps, durations)
- AI-Core stores what the **model needs** (raw items for LLM input)

**Summaries are just session items** (no separate table):
- When pruning occurs, AI-Core creates a summary as an `EasyInputMessageParam`:
  ```python
  summary_item = {
      "role": "system",  # or "user"
      "content": "Previous conversation summary:\n...",
      "type": "message"
  }
  ```
- Summary is stored as a regular session item in `session_items` table
- No separate summaries table needed!
- On next turn, SDK loads session items which includes the summary

They reference the same `session_id` but store different representations.

### Data Flow with Separate Databases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User sends message                                                       │
│     └──► BE stores in UserMessagesORM (BE's DB)                             │
│                                                                              │
│  2. BE calls AI-Core                                                         │
│     └──► Request: { session_id, user_message, model, device_id, ... }       │
│          (BE does NOT send history or summary - AI-Core has its own)        │
│                                                                              │
│  3. AI-Core loads session from ITS OWN DB                                   │
│     └──► SQLAlchemySession.get_items(session_id)                            │
│     └──► Returns: [summary (if exists), recent items, tool calls...]        │
│                                                                              │
│  4. AI-Core runs agent                                                       │
│     └──► Streams SSE events to BE                                           │
│     └──► call_model_input_filter may:                                       │
│          • Create summary of old messages                                   │
│          • Prune old items                                                  │
│          • Persist pruned state + summary to AI-Core's DB                   │
│                                                                              │
│  5. AI-Core stores new items in ITS OWN DB                                  │
│     └──► SQLAlchemySession.add_items([new user msg, assistant response,     │
│          tool calls, tool outputs...])                                       │
│                                                                              │
│  6. BE receives SSE events                                                   │
│     └──► TimelineCoalescer → AIResponsesORM (BE's DB)                       │
│     └──► Stores UI-friendly timeline blocks (NOT summaries)                 │
│                                                                              │
│  7. Frontend reads from BE                                                   │
│     └──► Gets timeline blocks for display                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         WHAT EACH DATABASE STORES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   BE's Database (Neon)                AI-Core's Database (Neon)             │
│   ════════════════════                ═════════════════════════             │
│                                                                              │
│   UserMessagesORM:                    session_items:                        │
│   ┌─────────────────────────┐         ┌─────────────────────────┐          │
│   │ id: 1                   │         │ session_id: "abc-123"   │          │
│   │ session_id: "abc-123"   │         │ item_index: 0           │          │
│   │ content: "Hello"        │         │ item_data: {            │          │
│   │ role: "user"            │         │   "role": "user",       │          │
│   │ created_at: ...         │         │   "content": "Hello"    │          │
│   └─────────────────────────┘         │ }                       │          │
│                                        └─────────────────────────┘          │
│   AIResponsesORM (Timeline):          ┌─────────────────────────┐          │
│   ┌─────────────────────────┐         │ session_id: "abc-123"   │          │
│   │ id: 1                   │         │ item_index: 1           │          │
│   │ session_id: "abc-123"   │         │ item_data: {            │          │
│   │ timeline: {             │         │   "role": "assistant",  │          │
│   │   blocks: [             │         │   "content": "Hi!"      │          │
│   │     {type: "thinking",  │         │ }                       │          │
│   │      content: "..."},   │         └─────────────────────────┘          │
│   │     {type: "message",   │         ┌─────────────────────────┐          │
│   │      content: "Hi!"},   │         │ session_id: "abc-123"   │          │
│   │   ]                     │         │ item_index: 2           │          │
│   │ }                       │         │ item_data: {            │          │
│   └─────────────────────────┘         │   "type": "tool_call",  │          │
│                                        │   "name": "search",     │          │
│   📺 Optimized for UI display         │   ...                   │          │
│                                        │ }                       │          │
│                                        └─────────────────────────┘          │
│                                                                              │
│                                        🧠 Optimized for LLM input           │
│                                        (Mutable - can be pruned)            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Dual Storage Strategy

Keep **both** storage systems with **different mutability semantics**:

| System | Data | Purpose | Mutability |
|--------|------|---------|------------|
| **BE TimelineCoalescer** | `message_block`, `thinking_block`, `tool_execution_block` | Frontend UI rendering | **Append-only (audit log)** |
| **SDK Session** | `TResponseInputItem` (user, assistant, tool calls, outputs) | Agent context, LLM input | **Mutable (working memory)** |

**Critical Insight: Session = Model's Working Memory**

The SDK session is NOT an append-only log. It's the model's **active working memory** that we manage:

```
┌─────────────────────────────────────────────────────────────────────────┐
│   BE Timeline (Audit Log)               SDK Session (Working Memory)    │
│   ═══════════════════════               ═════════════════════════════   │
│                                                                          │
│   📜 Complete history                   🧠 What model needs NOW          │
│   • Never delete                        • Prune old tool outputs         │
│   • Append only                         • Replace old msgs with summary  │
│   • For UI display                      • Delete irrelevant items        │
│   • All thinking blocks                 • Keep recent context            │
│   • All tool executions                 • Actively managed               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Why This Matters for Context Management**

If we only filtered in `call_model_input_filter` without persisting:
- SDK loads full history (100 items)
- Filter prunes to 50 items (temporary)
- LLM runs
- SDK adds new items → 102 items
- Next turn: SDK loads 102 items → must prune again!

With mutable session:
- SDK loads history (already pruned from previous turns)
- Filter checks if MORE pruning needed
- If yes: prune AND persist to session
- Next turn: SDK loads already-pruned history
- No redundant re-pruning

**Why keep both?**

1. **Frontend optimized**: TimelineCoalescer produces UI-friendly blocks with timestamps, durations, visual hierarchy
2. **Agent optimized**: SDK sessions store raw items in LLM-consumable format
3. **Separation of concerns**: UI needs != Agent needs
4. **No migration risk**: Existing frontend continues to work
5. **Audit trail**: BE has complete history even after session pruning

### Implementation Details

#### AI-Core's Own Database (Neon)

AI-Core gets its own PostgreSQL database, completely separate from BE's database.

```
Production Setup:
├── BE Database:      rsgpt-be-prod.neon.tech/rsgpt_be
└── AI-Core Database: rsgpt-ai-core-prod.neon.tech/rsgpt_ai_core
```

#### Table Schema (SDK Auto-Creates)

```sql
-- In AI-Core's database (NOT BE's database)
-- Created by SQLAlchemySession with create_tables=True

CREATE TABLE session_items (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,   -- References BE's chat_session.id
    item_index INTEGER NOT NULL,
    item_data JSONB NOT NULL,           -- Serialized TResponseInputItem
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_session_item UNIQUE (session_id, item_index)
);

CREATE INDEX idx_session_items_session_id ON session_items(session_id);
```

**Note**: `session_id` references BE's `chat_session.id` by value (not FK constraint).
This is intentional - no cross-database foreign keys.

#### AI-Core Configuration

```python
# app/config.py
class Settings(BaseSettings):
    # Existing settings...

    # AI-Core's own database for session storage
    session_database_url: str = Field(
        default="",
        description="PostgreSQL URL for AI-Core's session storage (separate from BE)"
    )
```

```yaml
# example.env (development)
SESSION_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/rsgpt_ai_core

# production (Neon)
SESSION_DATABASE_URL=postgresql+asyncpg://user:pass@rsgpt-ai-core-prod.neon.tech/rsgpt_ai_core
```

#### Session Factory

```python
# app/services/agent/session_factory.py

from typing import Optional
from agents.extensions.memory import SQLAlchemySession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from app.config import settings

_engine: Optional[AsyncEngine] = None

async def get_session_engine() -> AsyncEngine:
    """Get or create the shared database engine for sessions."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.session_database_url,
            pool_size=5,
            max_overflow=10,
        )
    return _engine

async def create_agent_session(session_id: str) -> SQLAlchemySession:
    """
    Create an SDK session for the given chat session ID.

    Args:
        session_id: The chat_session_id from rsgpt-be

    Returns:
        SQLAlchemySession configured for this session
    """
    engine = await get_session_engine()
    return SQLAlchemySession(
        session_id=session_id,
        engine=engine,
        create_tables=True,  # Idempotent, creates if not exists
    )
```

#### Updated Orchestration Service

```python
# app/services/agent/dynamic_orchestration_service.py

async def _execute(self, request: AgentRequest, ...):
    # Create SDK session if session_id provided
    session = None
    if request.session_id:
        session = await create_agent_session(request.session_id)
        logger.info(f"✓ SDK session created for {request.session_id}")

    # Runner automatically handles history with session
    agent_result = Runner.run_streamed(
        main_agent,
        input=user_message,  # Just the new user message
        context=agent_context,
        max_turns=request.max_turns,
        run_config=run_config,
        session=session,  # SDK handles history automatically
    )
```

#### Context Management with Persistent Pruning

With SDK sessions, `call_model_input_filter` does **two things**:
1. Mutate input for THIS LLM call
2. **Persist the pruning to session** so future turns don't re-load pruned items

```python
# app/services/context_manager/context_manager_hooks.py

class ContextManagerHooks(AgentHooks):
    def __init__(self, session_id: str, session: SQLAlchemySession, ...):
        self.session = session  # Reference to SDK session for persistence
        ...

    async def call_model_input_filter(self, data: CallModelData) -> ModelInputData:
        """
        Central mutation orchestrator.

        KEY: We don't just filter for this call - we PERSIST pruning to session.
        This ensures next turn loads already-pruned history.
        """
        input_items = list(data.model_data.input)

        if self._should_summarize(input_items):
            # 1. Create summary of old conversation
            summary_data = await self._create_summary(input_items)

            # 2. Build pruned list (summary + recent items)
            pruned_items = self._build_pruned_items(input_items, summary_data)

            # 3. PERSIST to session (critical!)
            await self._persist_pruned_session(pruned_items)

            # 4. Return for this LLM call
            return ModelInputData(
                input=pruned_items,
                instructions=data.model_data.instructions,
            )

        return data.model_data

    async def _persist_pruned_session(self, pruned_items: List[TResponseInputItem]):
        """
        Actually modify the session storage.
        Next turn will load the pruned version, not full history.
        """
        # Clear current session
        await self.session.clear_session()

        # Add pruned items
        await self.session.add_items(pruned_items)

        self.context_logger.info(f"✓ Session pruned to {len(pruned_items)} items")

    def _build_pruned_items(
        self,
        items: List[TResponseInputItem],
        summary_data: dict,
    ) -> List[TResponseInputItem]:
        """
        Build pruned item list using type-based heuristics.

        Strategy:
        - Replace old messages with summary
        - Keep recent messages (last N turns)
        - Delete old tool outputs
        - Keep recent tool calls with their outputs
        """
        pruned = []

        # Add summary at start
        pruned.append({
            "role": "user",
            "content": self._format_summary(summary_data),
        })

        # Type-based filtering
        for item in items:
            item_type = self._get_item_type(item)

            if item_type == "tool_output":
                # Only keep recent tool outputs
                if self._is_recent(item, max_age_turns=3):
                    pruned.append(item)
                # Old outputs are DROPPED (not in pruned list)

            elif item_type in ("user", "assistant"):
                # Only keep recent messages
                if self._is_recent(item, max_age_turns=5):
                    pruned.append(item)
                # Old messages are summarized

            elif item_type == "tool_call":
                # Keep if corresponding output is kept
                if self._output_is_kept(item, pruned):
                    pruned.append(item)

        return pruned
```

**Flow Diagram**:

```
Turn N (context at 90% capacity):
├─ SDK loads session (90 items)
├─ call_model_input_filter:
│   ├─ Detects: need to prune
│   ├─ Creates summary of old messages
│   ├─ Builds pruned list (30 items)
│   ├─ session.clear_session()
│   ├─ session.add_items(pruned_30_items)  ← PERSISTED
│   └─ Returns pruned input for LLM
├─ LLM runs with 30 items
├─ SDK adds new items → Session now has 32 items
│
Turn N+1:
├─ SDK loads session (32 items) ← Already pruned!
├─ call_model_input_filter:
│   └─ Checks: 32 items OK, no pruning needed
├─ LLM runs with 32 items
└─ ... continues normally
```

### What Stays the Same

1. **BE stores user messages** in `UserMessagesORM`
2. **BE stores AI responses** as timeline blocks via `TimelineCoalescer`
3. **Frontend reads** from BE as usual
4. **SSE streaming** continues to work
5. **Service authentication** - existing X-Service-Token auth

### What Changes

1. **AI-Core gets own database** (new Neon PostgreSQL instance)
2. **Single table** `session_items` in AI-Core's database (stores everything including summaries)
3. **Conversation history** comes from AI-Core's session DB, not BE request
4. **Tool calls/outputs** automatically stored and retrieved by SDK
5. **Summaries** stored as regular session items (just `EasyInputMessageParam` with `role: "system"`)
6. **Context pruning** happens in `call_model_input_filter` and persists to AI-Core's DB
7. **Simpler `_execute`** - no manual history building
8. **BE request payload** - simpler (just new message + session_id + config)
9. **BE can remove summary-related code** - no longer sends/receives summaries

### Migration Path

**Phase 1**: Add infrastructure (no behavior change)
- Add `SESSION_DATABASE_URL` to config
- Create `session_factory.py`
- AI-Core can connect to DB

**Phase 2**: Opt-in SDK sessions
- Add `use_sdk_session: bool` to `AgentRequest`
- If true, use SDK session; if false, use existing flow
- Test in staging

**Phase 3**: Full rollout
- Default `use_sdk_session=True`
- Monitor for issues
- Deprecate old flow

### Open Questions

1. **Database credentials**: How do we securely pass PostgreSQL credentials to AI-Core?
   - Environment variable (current approach for BE)
   - Secrets manager
   - Kubernetes secrets

2. **Connection pooling**: Should AI-Core share a connection pool or have its own?
   - Separate pool recommended (5-10 connections)
   - Avoids contention with BE

3. **Data retention**: How long do we keep `session_items`?
   - Same as chat sessions?
   - Separate TTL?

4. **Thinking blocks in session**: SDK will store assistant messages. Do we filter out thinking?
   - SDK doesn't separate thinking from output
   - May need custom serialization

5. **BE request simplification**: If SDK has full history, what does BE send?
   - Just the new user message
   - Session ID
   - Configuration (model, device_id, etc.)

---

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [SDK Sessions Documentation](https://openai.github.io/openai-agents-python/sessions/)
- [SQLAlchemy Sessions](https://openai.github.io/openai-agents-python/sessions/sqlalchemy/)
- [Context Manager Hooks Guide](./CONTEXT_SYSTEM_GUIDE.md)
- [Agent Streaming Guide](./AGENT_STREAMING_GUIDE.md)
