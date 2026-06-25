# Agent Streaming Guide

This guide explains how to use the OpenAI Agent SDK streaming endpoint with dynamic tool discovery.

## Overview

The `/agent/stream` endpoint provides an agent that can dynamically discover and execute tools on connected devices. The agent has access to two simple meta-tools that enable this capability.

## Key Features

- **Dynamic Tool Discovery**: Agent discovers tools at runtime using `list_tools()`
- **Runtime Tool Execution**: Execute any tool using `invoke_tool()`
- **Multi-turn Conversations**: Agent maintains context across multiple turns
- **Device Integration**: Execute tools on devices connected via WebSocket
- **Streaming Events**: Real-time updates for all agent actions

## The Two Meta-Tools

Every agent automatically has access to two strongly-typed Python tools:

### 1. `list_tools(device_id: Optional[str]) -> Dict`

Discover what tools are currently available on a device.

**Parameters:**
- `device_id` (optional): Device to query for tools

**Returns:**
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {...}
      }
    }
  ],
  "device_id": "device-123",
  "count": 5,
  "error": null
}
```

### 2. `invoke_tool(tool_name: str, device_id: str, tool_arguments: Optional[Dict]) -> Dict`

Execute a tool by name on a device.

**Parameters:**
- `tool_name`: Name of the tool to execute
- `device_id`: Device where tool should run
- `tool_arguments`: Dictionary of arguments for the tool

**Returns:**
```json
{
  "result": {...},
  "error": null
}
```

## How It Works

```
Turn 1: User asks "What's the weather?"
  ↓
  Agent calls list_tools(device_id="phone-123")
  ↓
  Returns: [get_weather, get_location, take_photo]

Turn 2: Agent sees get_weather is available
  ↓
  Agent calls invoke_tool(
    tool_name="get_weather",
    device_id="phone-123",
    tool_arguments={"location": "San Francisco"}
  )
  ↓
  Returns: {"result": {"temp": 68, "conditions": "sunny"}}

Turn 3: Agent responds
  ↓
  "The weather in San Francisco is 68°F and sunny!"
```

## Request Format

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What tools do you have?"
    }
  ],
  "agent_name": "Assistant",
  "device_id": "phone-123",
  "model": "gpt-4o",
  "parallel_tool_calls": false,
  "max_turns": 10
}
```

### Request Parameters

- **messages** (required): List of conversation messages
- **agent_name**: Name of the agent (default: "Assistant")
- **device_id**: Device ID to interact with (included in context for the agent)
- **model**: Model to use (default: "gpt-4o")
- **parallel_tool_calls**: Whether to allow parallel tool calls (default: false)
- **max_tokens**: Maximum tokens to generate
- **temperature**: Sampling temperature
- **max_turns**: Maximum number of agent loop turns (default: 10)

**Note**: Agent instructions and available tools are controlled by the service for consistency and security. The agent is automatically configured with `list_tools` and `invoke_tool` meta-tools.

## API Endpoints

### POST `/agent/stream`
Stream agent responses with dynamic tool discovery.

### GET `/agent/devices`
List all connected devices.

### GET `/agent/runs`
List currently active agent runs.

### GET `/agent/`
Get agent service information.

## Event Types

The stream emits Server-Sent Events (SSE):

### Agent Events

- **agent.run.started**: Run begins
- **agent.run_item.created**: New item created
- **agent.run_item.completed**: Item completed
- **agent.tool_execution.started**: Tool execution begins
- **agent.tool_execution.completed**: Tool execution succeeds
- **agent.tool_execution.failed**: Tool execution fails
- **agent.updated**: Agent changes
- **agent.run.completed**: Run completes
- **agent.run.failed**: Run fails

### OpenAI Response API Events

- **response.created**: Response created
- **response.output_text.delta**: Text delta (stream text)
- **response.tool_call.created**: Tool call created
- **response.tool_call.done**: Tool call complete
- **response.completed**: Response completed

## Example Flow

**User:** "What tools are available?"

**Agent:**
```python
# Calls: list_tools(device_id="phone-123")
# Returns: [get_weather, take_photo, get_location]
```

**Agent Response:** "I have access to: get_weather, take_photo, and get_location."

---

**User:** "Get the weather"

**Agent:**
```python
# Calls: invoke_tool(
#   tool_name="get_weather",
#   device_id="phone-123",
#   tool_arguments={}
# )
# Returns: {"result": {"temp": 72, "conditions": "cloudy"}}
```

**Agent Response:** "It's currently 72°F and cloudy."

## Python Client Example

```python
import httpx
import json

async def stream_agent():
    url = "http://localhost:8000/agent/stream"

    request_data = {
        "messages": [
            {"role": "user", "content": "List available tools"}
        ],
        "device_id": "phone-123",
        "max_turns": 5
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=request_data) as response:
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])

                    if event_type == "response.output_text.delta":
                        print(data["delta"], end="", flush=True)
                    elif event_type == "agent.tool_execution.started":
                        print(f"\n🔧 Calling {data['tool_name']}")
```

## Benefits

### ✅ **Simple Architecture**
- Only two tools to understand
- Clean, strongly-typed Python functions
- No complex configuration

### ✅ **Dynamic Discovery**
- Tools discovered at runtime
- Devices can connect/disconnect mid-conversation
- Agent adapts automatically

### ✅ **Multi-Device Support**
- Query different devices
- Switch between devices seamlessly
- Aggregate capabilities

## Error Handling

### Device Not Connected
```json
{
  "type": "agent.tool_execution.failed",
  "error": "Device 'phone-123' is not connected"
}
```

### Tool Not Found
The agent will see the error in the tool result and can inform the user or try alternatives.

## Best Practices

1. **Provide device_id in request**: Helps agent know which device to query
2. **Set appropriate max_turns**: Default is 10, adjust based on complexity
3. **Handle disconnections**: Agent will receive errors if devices disconnect
4. **Monitor events**: Track tool execution for debugging
5. **Use parallel_tool_calls wisely**: Enable only when you need multiple tools executed simultaneously

## Architecture

```
User Request
    ↓
POST /agent/stream
    ↓
AgentStreamingService
    ↓
OpenAI Agent SDK
  - Agent with [list_tools, invoke_tool]
    ↓
Agent calls list_tools(device_id)
    ↓
WebSocket Connection Manager
    ↓
Device returns tool list
    ↓
Agent calls invoke_tool(name, device_id, args)
    ↓
WebSocket Connection Manager
    ↓
Device executes tool
    ↓
Agent receives result
    ↓
Agent responds to user
    ↓
SSE Stream → Client
```

## Implementation Details

The two meta-tools are simple Python functions:

```python
from agents import function_tool
from app.services.streaming import connection_manager

@function_tool
async def list_tools(device_id: Optional[str] = None) -> Dict[str, Any]:
    """Get a list of available tools from a device."""
    response = await connection_manager.request_list_tools(device_id)
    return response

@function_tool
async def invoke_tool(
    tool_name: str,
    device_id: str,
    tool_arguments: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Invoke a tool on a device."""
    response = await connection_manager.request_invoke_tool(
        device_id, tool_name, tool_arguments
    )
    return response
```

The Agent SDK automatically:
- Extracts tool schemas from function signatures
- Uses docstrings for descriptions
- Handles async execution
- Manages tool call lifecycle

## Monitoring

```bash
# Check agent service status
curl http://localhost:8000/agent/

# List connected devices
curl http://localhost:8000/agent/devices

# List active runs
curl http://localhost:8000/agent/runs
```

## Environment Variables

```env
# OpenAI API Key (required)
OPENAI_API_KEY=sk-...

# Optional: WebSocket settings
WEBSOCKET_TIMEOUT=60.0
```

## Troubleshooting

### Agent Not Finding Tools
**Check:** Is device connected?
```bash
curl http://localhost:8000/agent/devices
```

### Tool Execution Timeout
**Check:** Device responsiveness, increase timeout if needed

### Max Turns Exceeded
**Solution:** Increase `max_turns` or simplify the task
