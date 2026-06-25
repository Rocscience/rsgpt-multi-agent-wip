"""Agent endpoints for Multi-Agent Workflow with OpenAI Agent SDK integration"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies import verify_be_auth
from app.models.agent import AgentRequest, AgentMode
from app.services.agent import orchestration_service
from app.services.multi_agent.orchestration_service import (
    multi_agent_orchestration_service,
    should_use_multi_agent,
)
from app.services.streaming import connection_manager

logger = logging.getLogger(__name__)
agent_router = APIRouter()


@agent_router.get("/")
async def agent_info() -> Dict[str, Any]:
    """
    Agent Workflow service information endpoint.
    """
    active_runs = await orchestration_service.get_active_runs()
    connected_devices = connection_manager.get_connected_devices()

    return {
        "status": "success",
        "service": "rsgpt-ai-core-agent",
        "workflow_type": "single-agent",
        "active_runs": len(active_runs),
        "connected_devices": len(connected_devices),
        "features": [
            "dynamic_orchestration",
            "agents_as_tools",
            "multi_agent_workflow",
            "streaming",
            "tracing",
            "dynamic_tool_discovery",
            "device_tools",
            "rslog_mcp_server",
            "web_search",
            "knowledge_search",
        ],
        "agents": [
            "Orchestrator",
            "Research Agent",
            "Planning Agent",
            "Local Device Execution Agent",
            "RSLog Execution Agent",
            "Evaluation Agent",
            "Summarizer Agent",
        ],
    }


@agent_router.post("/stream")
async def agent_stream(
    agent_request: AgentRequest,
    request: Request,
    auth_info: dict = Depends(verify_be_auth),
):
    """
    Generate streaming multi-agent workflow response with dynamic LLM orchestration.

    This endpoint executes a dynamic multi-agent workflow using LLM-driven orchestration:
    1. Orchestrator Agent decides which specialized agents to invoke as tools
    2. Specialized agents execute their tasks and return results to orchestrator
    3. Orchestrator maintains control, narrates progress, and synthesizes results

    **Architecture:**
    - **Orchestrator Agent**: Central controller with continuous conversation control
    - **Specialized Agents (as Tools)**: Task-specific agents invoked as tools by orchestrator

    **Available Agent Tools:**
    - **research_expert**: Searches Rocscience docs and web for knowledge queries
    - **planning_expert**: Creates execution plans for device operations
    - **device_execution_expert**: Executes operations on connected devices (RS2, Slide2, etc.)
    - **rslog_expert**: Queries and analyzes RSLog server logs
    - **evaluation_expert**: Validates task completion and success criteria
    - **summarizer_expert**: Creates final user-facing responses

    **Workflow Examples:**
    - Knowledge Query: Orchestrator calls research_expert → narrates findings →
      calls summarizer_expert
    - Device Action: Orchestrator calls planning_expert → narrates plan →
      calls device_execution_expert → narrates results → calls evaluation_expert
    - Mixed Query: Orchestrator calls rslog_expert → narrates findings →
      calls planning_expert → narrates plan → calls device_execution_expert →
      narrates results

    **Available Tools:**
    - search_knowledge: Search internal Rocscience knowledge base (RAG)
    - search_web: Search the web using Perplexity API
    - Device tools: Dynamically loaded from connected devices
      (RS2_*, Slide2_*, etc.)
    - RSLog MCP tools: Log querying and analysis (when RSLog configured)

    **Tracing:**
    - OpenAI Agent SDK tracing enabled for all workflow executions
    - trace_id included in workflow.started and workflow.completed events
    - View traces at: https://platform.openai.com/traces

    **SSE Event Types:**
    - agent.run.started: Workflow run begins
    - agent.workflow.started: Workflow started (includes trace_id)
    - agent.workflow.status_changed: Workflow status transitions
      (ORCHESTRATING, RESEARCHING, PLANNING, EXECUTING, etc.)
    - agent.transition: Agent transition via tool call (from_agent, to_agent, tool_name)
    - agent.thinking: Agent reasoning/thinking steps (includes agent_name)
    - agent.planning: Plan creation (device actions)
    - agent.task_progress: Task execution progress
    - agent.tool_execution.started: Tool execution begins (non-agent tools)
    - agent.tool_execution.completed: Tool execution succeeds (non-agent tools)
    - agent.tool_execution.failed: Tool execution fails
    - agent.message.delta: Message text delta (incremental, primarily from orchestrator)
    - agent.message.done: Message completion
    - agent.text_output: Final text output
    - agent.workflow.completed: Workflow completed (includes trace_id)
    - agent.run.completed: Run completes successfully
    - agent.run.failed: Run fails
    - response.*: Raw OpenAI Response API events

    **Key Features:**
    - **Dynamic Orchestration**: LLM decides workflow (no code branches)
    - **Agents as Tools**: Orchestrator maintains control, calls specialized agents as tools
    - **Continuous Narration**: Orchestrator narrates progress throughout the workflow
    - **Context-Aware**: Only creates agents that are available (based on device/MCP status)

    Requires BE service token authentication (X-Service-Token header).

    **Request Body:**
    - messages: List of conversation messages
    - model: Orchestrator model to use (gpt-5, anthropic/claude-sonnet-4-5)
    - device_id: Optional device ID for tool execution (enables Local Device Execution Agent)
    - rslog_mcp_enabled: Optional flag to enable RSLog MCP server (enables RSLog Execution Agent)
    - rslog_mcp_token: Optional bearer token for RSLog authentication
    - user_permission: User permission level
    - source_channels: Knowledge source channels
    """
    try:
        # Note: We don't reject requests if device is not connected
        # Instead, we let the agent handle it gracefully by:
        # 1. Not loading device tools (agent will have no device-specific tools)
        # 2. Agent will detect missing tools and guide user on how to connect device
        # 3. Agent can still answer knowledge questions and provide guidance

        # Return streaming response with proper SSE headers
        # Note: Errors during streaming are handled by generate_workflow_stream()
        # which emits agent.run.failed events and ends the stream gracefully
        stream = (
            multi_agent_orchestration_service.stream_workflow(agent_request, request)
            if should_use_multi_agent(agent_request)
            else orchestration_service.stream_workflow(agent_request, request)
        )
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Safety net: catch any unexpected errors that occur BEFORE streaming starts
        # (errors during streaming are handled by generate_workflow_stream)
        logger.error(f"Unexpected error before streaming started: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize agent workflow: {str(e)}",
        )


@agent_router.get("/devices")
async def list_connected_devices():
    """
    List all connected devices that can execute tools.
    """
    try:
        devices = connection_manager.get_connected_devices()
        return {
            "status": "success",
            "devices": devices,
            "count": len(devices),
        }
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agent_router.get("/runs")
async def list_active_runs():
    """
    List currently active agent workflow runs.
    """
    try:
        runs = await orchestration_service.get_active_runs()
        return {
            "status": "success",
            "workflow_type": "single-agent",
            "active_runs": [run.model_dump() for run in runs.values()],
            "count": len(runs),
        }
    except Exception as e:
        logger.error(f"Error listing agent workflow runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
