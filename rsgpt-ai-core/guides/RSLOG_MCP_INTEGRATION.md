# RSLog MCP Integration Guide

## Overview

This guide documents the integration of RSLog's HTTPS MCP server into the multi-agent workflow system. RSLog provides logging and analysis tools through a FastMCP server, enabling the agent to query logs, analyze events, and troubleshoot issues.

## Architecture Decision

### Approach: Extend `device_action` Branch

We're **extending the existing device_action workflow** rather than creating a new branch. This allows:

- ✅ Reuse of plan → execute → evaluate → summarize logic
- ✅ Support for WebSocket device tools + MCP servers simultaneously
- ✅ Future-proof for additional MCP servers
- ✅ Clean separation: WebSocket for devices, HTTPS for MCP servers

### Intent Classification

The classifier will route RSLog queries to `device_action` intent:

```json
{
  "intent_type": "device_action",
  "confidence": 0.95,
  "rationale": "User wants to query RSLog for error analysis"
}
```

Examples of RSLog queries:
- "Search RSLog for errors in the last hour"
- "Show me all warnings from RS2 in the logs"
- "What critical issues occurred today?"

## Technology Stack

### FastMCP Integration

We're using the **OpenAI Agents SDK's native MCP support** with FastMCP servers:

```python
from agents.mcp import MCPServerStreamableHttp

# FastMCP server connection
rslog_server = MCPServerStreamableHttp(
    name="RSLog MCP Server",
    params={
        "url": "https://rslog.example.com/mcp",
        "headers": {"Authorization": "Bearer <token>"},
        "timeout": 30,
    },
    cache_tools_list=True,
    max_retry_attempts=3,
    use_structured_content=True,
)
```

### FastMCP Server Features

FastMCP provides:
- **Tool exposure** - Python functions exposed as MCP tools
- **Streaming support** - Real-time responses
- **Type safety** - Pydantic models for input/output
- **Authentication** - Bearer token support

## Implementation Plan

### Phase 1: Data Models

#### 1.1 Update AgentRequest Model

**File:** `app/models/agent.py`

```python
class AgentRequest(BaseModel):
    # ... existing fields ...

    device_id: Optional[str] = Field(
        default=None,
        description="Device ID for WebSocket tool operations (RS2, Slide2, etc.)",
    )

    # RSLog MCP Server Configuration
    rslog_mcp_enabled: bool = Field(
        default=False,
        description="Enable RSLog MCP server tools for log querying and analysis",
    )
    rslog_mcp_token: Optional[str] = Field(
        default=None,
        description="Authorization bearer token for RSLog MCP server",
    )
```

**Rationale:**
- `rslog_mcp_enabled` - explicit flag for cleaner conditional logic
- `rslog_mcp_token` - per-request authentication token (user-specific)
- `rslog_mcp_url` - moved to environment configuration (infrastructure setting)

#### 1.2 Update Configuration Settings

**File:** `app/config.py`

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # RSLog MCP Server Configuration
    rslog_mcp_url: str = Field(
        "", env="RSLOG_MCP_URL"
    )
    rslog_mcp_timeout: int = Field(
        30, env="RSLOG_MCP_TIMEOUT"
    )
```

**File:** `example.env`

```bash
# RSLog MCP Server Configuration (Optional - for log analysis tools)
RSLOG_MCP_URL=https://rslog.example.com/mcp
RSLOG_MCP_TIMEOUT=30
```

**Rationale:**
- URL is infrastructure configuration, not per-request data
- Timeout can be tuned for environment performance
- Cleaner separation of concerns

### Phase 2: Workflow Validation

#### 2.1 Update Tool Availability Validation

**File:** `app/services/agent/device_action_workflow.py`

Replace `_validate_device_connection` with more generic `_validate_tool_availability`:

```python
async def _validate_tool_availability(
    self, request: AgentRequest, sequence_number: int, emit_event_callback
) -> Dict:
    """
    Validate that at least one tool source is available.

    Checks:
    - WebSocket device tools (RS2, Slide2, etc.)
    - MCP servers (RSLog, etc.)

    Returns:
        Dict with:
            - is_available: bool
            - has_device_tools: bool
            - has_rslog_tools: bool
            - sequence_number: int
            - events: List[str] (error events if unavailable)
    """
    events = []
    has_device_tools = False
    has_rslog_tools = False

    # Check WebSocket device tools
    if request.device_id:
        from app.services.streaming import connection_manager
        has_device_tools = connection_manager.is_device_connected(request.device_id)

        if not has_device_tools:
            logger.warning(
                f"Device {request.device_id} requested but not connected"
            )

    # Check RSLog MCP availability
    if request.rslog_mcp_enabled:
        from app.config import settings

        if settings.rslog_mcp_url:
            has_rslog_tools = True
            logger.info(f"RSLog MCP server configured: {settings.rslog_mcp_url}")
        else:
            logger.warning("RSLog enabled but RSLOG_MCP_URL not configured in environment")

        # Optional: Add health check here
        # try:
        #     await self._ping_rslog_server(request.rslog_mcp_url)
        # except Exception as e:
        #     logger.error(f"RSLog health check failed: {e}")
        #     has_rslog_tools = False

    if not has_device_tools and not has_rslog_tools:
        # No tools available - emit error
        sequence_number += 1
        events.append(
            emit_event_callback(
                "agent.out_of_scope",
                OutOfScopeEvent(
                    sequence_number=sequence_number,
                    reason=(
                        "Action workflows require either a connected device "
                        "or an MCP server (like RSLog). "
                        "Please connect a device or configure an MCP server."
                    ),
                ).model_dump(),
            )
        )
        sequence_number += 1
        events.append(
            emit_event_callback(
                "agent.workflow.status_changed",
                WorkflowStatusChangedEvent(
                    sequence_number=sequence_number,
                    status=WorkflowStatus.OUT_OF_SCOPE,
                    agent_name="Workflow",
                ).model_dump(),
            )
        )
        return {
            "is_available": False,
            "has_device_tools": False,
            "has_rslog_tools": False,
            "sequence_number": sequence_number,
            "events": events,
        }

    logger.info(
        f"Tool sources available - Device: {has_device_tools}, "
        f"RSLog: {has_rslog_tools}"
    )

    return {
        "is_available": True,
        "has_device_tools": has_device_tools,
        "has_rslog_tools": has_rslog_tools,
        "sequence_number": sequence_number,
        "events": [],
    }
```

#### 2.2 Update execute() Method

**File:** `app/services/agent/device_action_workflow.py`

```python
async def execute(
    self,
    request: AgentRequest,
    conversation_history: list,
    agent_context: AgentContext,
    sequence_number: int,
    emit_event_callback,
) -> AsyncGenerator[str, None]:
    """Execute the complete device action workflow with streaming."""

    # Validate tool availability (updated validation)
    validation_result = await self._validate_tool_availability(
        request, sequence_number, emit_event_callback
    )

    if not validation_result["is_available"]:
        # No tools available - yield error events and return
        for event_str in validation_result["events"]:
            yield event_str
        return

    sequence_number = validation_result["sequence_number"]

    # Log available tool sources
    logger.info(
        f"Executing workflow with tools - "
        f"Device: {validation_result['has_device_tools']}, "
        f"RSLog: {validation_result['has_rslog_tools']}"
    )

    # Continue with existing workflow...
    # (rest of the method remains the same)
```

### Phase 3: Tool Loading

#### 3.1 Create RSLog MCP Server Factory

**File:** `app/services/agent/device_action_workflow.py`

```python
async def _create_rslog_mcp_server(
    self,
    url: str,
    token: Optional[str] = None,
    timeout: int = 30,
):
    """
    Create RSLog MCP server instance using Agents SDK.

    Args:
        url: RSLog MCP server URL
        token: Optional bearer token for authentication
        timeout: Request timeout in seconds

    Returns:
        MCPServerStreamableHttp instance
    """
    from agents.mcp import MCPServerStreamableHttp

    logger.info(f"Creating RSLog MCP server connection to {url}")

    params = {
        "url": url,
        "timeout": timeout,
    }

    if token:
        params["headers"] = {"Authorization": f"Bearer {token}"}
        logger.debug("Added authorization header to RSLog MCP request")

    try:
        server = MCPServerStreamableHttp(
            name="RSLog MCP Server",
            params=params,
            cache_tools_list=True,  # Cache for performance
            max_retry_attempts=3,
            use_structured_content=True,
        )

        # Connect to the MCP server
        await server.connect()
        logger.info("RSLog MCP server connected successfully")

        return server

    except Exception as e:
        logger.error(f"Failed to create/connect RSLog MCP server: {e}", exc_info=True)
        raise
```

#### 3.2 Update _execute_single_task

**File:** `app/services/agent/device_action_workflow.py`

Modify the executor creation to include MCP servers:

```python
async def _execute_single_task(
    self,
    request: AgentRequest,
    task: dict,
    task_index: int,
    total_tasks: int,
    conversation_history: list,
    agent_context: AgentContext,
    sequence_number: int,
    emit_event_callback,
) -> AsyncGenerator[tuple[str, int], None]:
    """Execute a single task: executor → evaluator"""

    # Status: Executing
    sequence_number += 1
    yield emit_event_callback(
        "agent.workflow.status_changed",
        WorkflowStatusChangedEvent(
            sequence_number=sequence_number,
            status=WorkflowStatus.EXECUTING,
            agent_name="Executor",
        ).model_dump(),
    ), sequence_number

    logger.info(f"Executing task {task_index + 1}/{total_tasks}")

    # Collect MCP servers
    mcp_servers = []

    # Load RSLog MCP server if enabled
    if request.rslog_mcp_enabled:
        from app.config import settings

        if settings.rslog_mcp_url:
            try:
                rslog_server = await self._create_rslog_mcp_server(
                    url=settings.rslog_mcp_url,
                    token=request.rslog_mcp_token,
                    timeout=settings.rslog_mcp_timeout,
                )
            mcp_servers.append(rslog_server)
            logger.info("RSLog MCP server added to executor")
        except Exception as e:
            logger.error(f"Failed to add RSLog MCP server: {e}")
            # Continue without RSLog tools (device tools may still work)

    # Create executor with base tools and MCP servers
    if mcp_servers:
        # Use factory method that accepts MCP servers
        executor_agent = agent_factory.create_executor_agent_with_mcp(
            model=request.model or "gpt-5",
            tools=[search_knowledge],
            mcp_servers=mcp_servers,
        )
    else:
        # Traditional executor without MCP
        executor_agent = agent_factory.create_executor_agent(
            model=request.model or "gpt-5",
            tools=[search_knowledge],
        )

    # Load WebSocket device tools if device connected
    if request.device_id:
        await self._load_device_tools(request.device_id, executor_agent)

    # Add task to conversation
    task_prompt = f"Execute this task: {json.dumps(task)}"
    conversation_history.append(
        {
            "role": "user",
            "content": [{"type": "input_text", "text": task_prompt}],
        }
    )

    # Execute with tool tracking
    executor_result = Runner.run_streamed(
        executor_agent,
        input=conversation_history,
        context=agent_context,
    )

    # ... rest of execution (unchanged)
```

### Phase 4: Agent Factory Updates

#### 4.1 Add MCP-Aware Executor Creation

**File:** `app/services/agent/agent_factory.py`

```python
@staticmethod
def create_executor_agent_with_mcp(
    model: str,
    tools: List[Any],
    mcp_servers: List[Any],
) -> Agent[AgentContext]:
    """
    Create executor agent with MCP servers.

    Args:
        model: Model name (e.g., "gpt-5", "anthropic/claude-sonnet-4-5")
        tools: List of function tools
        mcp_servers: List of MCP server instances

    Returns:
        Agent configured with tools and MCP servers
    """
    model_obj = AgentFactory._create_model(model)

    logger.info(
        f"Creating executor agent with {len(tools)} tools "
        f"and {len(mcp_servers)} MCP servers"
    )

    return Agent[AgentContext](
        name="Executor",
        instructions=EXECUTOR_INSTRUCTIONS,
        model=model_obj,
        tools=tools,
        mcp_servers=mcp_servers,  # Add MCP servers here
        output_type=AgentOutputSchema(ExecutorSchema, strict_json_schema=False),
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            store=True,
            reasoning=Reasoning(effort="medium", summary="auto"),
        ),
    )
```

### Phase 5: Instruction Updates

#### 5.1 Update Executor Instructions

**File:** `app/services/agent/multi_agent_instructions.py`

Update EXECUTOR_INSTRUCTIONS to mention MCP tools:

```python
EXECUTOR_INSTRUCTIONS = """You are the Executor agent.
Your input is a single task object from the Planner output.

Goal: Fulfil the objective described in the task by using available tools.
You may call multiple tools sequentially to achieve the goal.

## Available Tools

**search_knowledge** - Search Rocscience documentation and knowledge base

**Device-specific tools** - Tools from connected devices (RS2, Slide2, etc.)
  - RS2 tools are prefixed with "RS2_" (e.g., RS2_enable_functions)
  - Slide2 tools are prefixed with "Slide2_"

**MCP Server tools** - Tools from MCP servers (RSLog, etc.)
  - RSLog tools for log querying and analysis
  - Available when RSLog MCP server is configured

## Device Tools

When a device is connected, its tools are automatically loaded and available.
You can call these tools directly by name, just like any other tool.

## MCP Server Tools

When an MCP server like RSLog is configured, its tools are automatically loaded.
These tools follow standard MCP conventions and provide specialized capabilities.

**Important:**
- All tools are ready to use immediately - no discovery step needed
- Device tools are executed on their respective devices via WebSocket
- MCP tools are executed on their respective servers via HTTPS
- Each tool has its own parameters defined in its schema
- Use the EXACT tool name as provided - do not modify prefixes

**DO NOT:**
- Make up or hallucinate tool names - ONLY call tools that exist
- Guess tool names or remove prefixes
- Call generic names when prefixed versions exist

## Execution Rules

1. Choose the correct sequence of tool calls to complete the task
2. Validate progress against task.success_criteria and task.validation
3. Stop when the objective is achieved or when you encounter a blocking error
4. Log each action and its result clearly

Return structured JSON only."""
```

#### 5.2 Update Classifier Instructions (Optional)

**File:** `app/services/agent/multi_agent_instructions.py`

```python
CLASSIFY_INSTRUCTIONS = """
Before classification, normalize obvious typos or abbreviations (RS-2 → RS2, slp → slope) only for
clarity. Do not rewrite or expand meaning.

Classify the user's rewritten query into one of the following categories based on intent and domain
relevance:

1. "knowledge" — The user is asking for information, guidance, or explanation
   **specifically related to Rocscience software or geotechnical engineering.**
   (Examples: "How does RS2 calculate stress?", "Explain factor of safety in Slide2.")

2. "device_action" — The user is requesting a change, query, or execution
   via tools (MCP tools for Rocscience products, log analysis, device actions).
   (Examples:
    - "Change the bolt pre-tension in my RS2 model"
    - "Run slope stability analysis"
    - "Search RSLog for errors in the last hour"
    - "Show me warnings from RS2 in the logs")

3. "out_of_scope" — The query is NOT about Rocscience software, geotechnical engineering,
   or supported workflows. This includes general knowledge, sports, finance, politics,
   or any other unrelated subject.
   (Examples: "What is soccer?", "Who won the World Cup?", "Explain ChatGPT.")

Rules:
- Preserve action intent: if the user commands a device, queries logs, or requests execution,
  classify as `device_action`.
- If the query is conceptual or informational, classify as `knowledge` only if it relates
  to Rocscience or geotechnical engineering.
- Be strict about scope: any non-geotechnical or non-Rocscience question is `out_of_scope`.
- If uncertain, prefer `out_of_scope`.

Return structured JSON with:
{
  "intent_type": "knowledge | device_action | out_of_scope",
  "confidence": "number between 0 and 1",
  "rationale": "short explanation of reasoning"
}"""
```

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# RSLog MCP Server Configuration (Optional - for log analysis tools)
RSLOG_MCP_URL=https://rslog.rocscience.com/mcp
RSLOG_MCP_TIMEOUT=30
```

**Configuration Settings:**
- `RSLOG_MCP_URL` - HTTPS endpoint for RSLog MCP server (infrastructure setting)
- `RSLOG_MCP_TIMEOUT` - Request timeout in seconds (default: 30)

### Runtime Configuration

RSLog MCP is enabled per-request with user-specific authentication:

```python
request = AgentRequest(
    messages=[...],
    rslog_mcp_enabled=True,           # Enable RSLog tools
    rslog_mcp_token="user-bearer-token",  # User-specific auth token
)
```

**Why this separation?**
- URL is **infrastructure configuration** (where the server is)
- Token is **per-request authentication** (who the user is)
- Cleaner security model and easier deployment configuration

## Testing Strategy

### Unit Tests

```python
# tests/services/agent/test_rslog_mcp.py

@pytest.mark.asyncio
async def test_rslog_mcp_server_creation():
    """Test RSLog MCP server instance creation"""
    workflow = DeviceActionWorkflow(event_handler)

    server = await workflow._create_rslog_mcp_server(
        url="https://rslog.example.com/mcp",
        token="test-token",
    )

    assert server is not None
    assert server.name == "RSLog MCP Server"


@pytest.mark.asyncio
async def test_tool_availability_with_rslog():
    """Test validation with RSLog enabled"""
    # Set environment configuration
    from app.config import settings
    settings.rslog_mcp_url = "https://rslog.example.com/mcp"

    request = AgentRequest(
        messages=[...],
        rslog_mcp_enabled=True,
        rslog_mcp_token="test-token",
    )

    validation = await workflow._validate_tool_availability(...)

    assert validation["is_available"] is True
    assert validation["has_rslog_tools"] is True
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_rslog_query_workflow():
    """Test complete workflow with RSLog query"""
    # Configure RSLog URL in settings
    from app.config import settings
    settings.rslog_mcp_url = TEST_RSLOG_URL

    request = AgentRequest(
        messages=[
            AgentMessage(
                role="user",
                content="Search RSLog for critical errors in the last hour"
            )
        ],
        rslog_mcp_enabled=True,
        rslog_mcp_token=TEST_TOKEN,
    )

    events = []
    async for event in service.generate_workflow_stream_events(request):
        events.append(event)

    # Verify workflow completed successfully
    assert any("agent.workflow.completed" in e for e in events)
```

## Error Handling

### Connection Failures

```python
try:
    rslog_server = await self._create_rslog_mcp_server(...)
    mcp_servers.append(rslog_server)
except ConnectionError as e:
    logger.error(f"RSLog connection failed: {e}")
    # Continue without RSLog (device tools may still work)
except Exception as e:
    logger.error(f"Unexpected error loading RSLog: {e}", exc_info=True)
    # Decide whether to fail task or continue
```

### Tool Execution Failures

The existing error handling in `_handle_tool_output` covers MCP tool failures:

```python
if error:
    logger.error(f"Tool call failed: {tool_call_id} - {error}")
    yield emit_event_callback(
        "agent.tool_execution.failed",
        ToolExecutionFailedEvent(
            sequence_number=sequence_number,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            error=str(error),
        ).model_dump(),
    )
```

## Future Enhancements

### 1. Connection Pooling

For better performance, maintain persistent MCP connections:

```python
class RSLogMCPManager:
    """Manages persistent RSLog MCP connections"""

    def __init__(self):
        self._connections: Dict[str, MCPServerStreamableHttp] = {}

    async def get_or_create(self, url: str, token: str):
        """Get existing connection or create new one"""
        cache_key = f"{url}:{token}"

        if cache_key not in self._connections:
            self._connections[cache_key] = await self._create_server(url, token)

        return self._connections[cache_key]
```

### 2. Health Checks

Add proactive health monitoring:

```python
async def _ping_rslog_server(self, url: str) -> bool:
    """Check if RSLog MCP server is reachable"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{url}/health")
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"RSLog health check failed: {e}")
        return False
```

### 3. Additional MCP Servers

The pattern extends to other MCP servers:

```python
# In AgentRequest
other_mcp_servers: Optional[List[MCPServerConfig]] = Field(...)

# In workflow
for mcp_config in request.other_mcp_servers:
    server = await self._create_mcp_server(mcp_config)
    mcp_servers.append(server)
```

### 4. Tool Filtering

Limit which RSLog tools are exposed:

```python
from agents.mcp import create_static_tool_filter

rslog_server = MCPServerStreamableHttp(
    name="RSLog MCP Server",
    params={...},
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["query_logs", "get_errors", "analyze_patterns"]
    ),
)
```

## Dependencies

Add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# Existing dependencies...
# agents SDK already includes MCP support
# No additional dependencies needed for basic MCP integration

# For FastMCP server development (separate project):
# fastmcp = "^0.1.0"
```

## References

- [OpenAI Agents SDK MCP Documentation](https://platform.openai.com/docs/agents/tools/mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Existing Agent Streaming Guide](./AGENT_STREAMING_GUIDE.md)

## Summary

This integration:
1. ✅ Extends existing device_action workflow (no new branch)
2. ✅ Uses SDK-native MCP support (clean, maintainable)
3. ✅ Supports WebSocket device tools + HTTPS MCP servers simultaneously
4. ✅ Provides clear separation of concerns
5. ✅ Enables future MCP server additions with minimal changes

**Next Steps:**
1. Implement Phase 1-3 (models, validation, tool loading)
2. Test with FastMCP RSLog server
3. Add integration tests
4. Update frontend to pass `rslog_mcp_*` parameters
5. Document RSLog-specific tool usage patterns
