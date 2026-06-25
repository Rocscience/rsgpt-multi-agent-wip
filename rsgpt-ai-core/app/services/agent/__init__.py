"""Agent services for single-agent orchestration and tool execution"""

from .agent_config import (
    ResolvedModel,
    build_run_config,
    create_context_hooks,
    create_model_settings,
    resolve_model,
    validate_reasoning_effort,
)
from .instructions import (
    MAIN_AGENT_INSTRUCTIONS,
    SUMMARIZER_INSTRUCTIONS,
    build_device_context,
    build_instructions,
)
from .main_agent import create_main_agent
from .orchestration_service import OrchestrationService, orchestration_service
from .sse_event_emitter import SSEEventEmitter, SSEEventQueue
from .summarizer_agent import create_summarizer_agent, summarize_conversation
from .tools import search_knowledge, search_web

__all__ = [
    # Config
    "resolve_model",
    "ResolvedModel",
    "create_model_settings",
    "validate_reasoning_effort",
    "create_context_hooks",
    "build_run_config",
    # Agents
    "create_main_agent",
    "create_summarizer_agent",
    "summarize_conversation",
    # Instructions
    "MAIN_AGENT_INSTRUCTIONS",
    "SUMMARIZER_INSTRUCTIONS",
    "build_device_context",
    "build_instructions",
    # Services
    "OrchestrationService",
    "orchestration_service",
    # SSE
    "SSEEventEmitter",
    "SSEEventQueue",
    # Tools
    "search_knowledge",
    "search_web",
]
