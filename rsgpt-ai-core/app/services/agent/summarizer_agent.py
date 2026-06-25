"""Summarizer Agent for creating structured conversation summaries using OpenAI Agent SDK"""

import logging
from typing import Any, Dict, List

from agents import Agent, Runner
from agents.items import TResponseInputItem
from pydantic import BaseModel, Field

from app.models.agent import AgentContext
from app.services.agent.agent_config import resolve_model
from app.services.agent.instructions import SUMMARIZER_INSTRUCTIONS

logger = logging.getLogger(__name__)


# =============================================================================
# Output Type (Structured Output)
# =============================================================================


class ConversationSummary(BaseModel):
    """Structured conversation summary output"""

    summary_text: str = Field(
        description="A concise 2-3 sentence summary of the entire conversation so far"
    )
    goals: List[str] = Field(
        description="List of user goals or objectives (both completed and in-progress)"
    )
    accomplishments: List[str] = Field(
        description="List of tasks or goals that have been completed during the conversation"
    )
    tool_calls: List[str] = Field(
        description="List of tools used with brief context, e.g. 'search_knowledge: "
        "queried Settle3 integrations'"
    )
    key_insights: List[str] = Field(
        description="Critical facts, data, or findings extracted from tool results that "
        "the user would want preserved. Include specific names, numbers, lists, or "
        "technical details."
    )
    most_recent_state: str = Field(
        description="What the user was just asking about or working on - the immediate "
        "context for continuing"
    )


# =============================================================================
# Agent Creation
# =============================================================================


def create_summarizer_agent(model: str = "gpt-5-mini") -> Agent[AgentContext]:
    """
    Create a summarizer agent with structured output.

    Uses LiteLLM for consistent cross-model compatibility.

    Args:
        model: LLM model to use for summarization (default: gpt-5-mini for efficiency)

    Returns:
        Agent configured for conversation summarization with structured output
    """
    # Use LiteLLM for consistent format across all models
    resolved = resolve_model(model)

    return Agent[AgentContext](
        name="Conversation Summarizer",
        instructions=SUMMARIZER_INSTRUCTIONS,
        model=resolved.model,
        output_type=ConversationSummary,
    )


# =============================================================================
# Helper Functions
# =============================================================================


async def summarize_conversation(
    messages: List[TResponseInputItem],
    model: str = "gpt-5-mini",
) -> Dict[str, Any]:
    """
    Create a conversation summary by passing input_items to the summarizer agent.

    NOTE: Items should be pre-sanitized for OpenAI compatibility before calling.

    Args:
        messages: Sanitized conversation input items
        model: Model to use for summarization

    Returns:
        Structured summary dictionary
    """

    async def _run_summarizer(model_name: str) -> Dict[str, Any]:
        """Run the summarizer with a specific model."""
        summarizer = create_summarizer_agent(model_name)
        result = await Runner.run(summarizer, input=messages)

        if hasattr(result, "final_output") and result.final_output:
            summary_obj = result.final_output

            if hasattr(summary_obj, "model_dump"):
                return summary_obj.model_dump()
            else:
                return {
                    "summary_text": getattr(summary_obj, "summary_text", ""),
                    "goals": getattr(summary_obj, "goals", []),
                    "accomplishments": getattr(summary_obj, "accomplishments", []),
                    "tool_calls": getattr(summary_obj, "tool_calls", []),
                    "key_insights": getattr(summary_obj, "key_insights", []),
                    "most_recent_state": getattr(summary_obj, "most_recent_state", ""),
                }

        raise ValueError("No output from summarizer agent")

    # Try with the requested model first
    try:
        summary_dict = await _run_summarizer(model)
        logger.info(f"Created summary for {len(messages)} items using {model}")
        return summary_dict
    except Exception as e:
        logger.warning(f"Summarization failed with {model}: {e}")

    # Fallback to gpt-5-mini if different model was requested
    if model != "gpt-5-mini":
        try:
            summary_dict = await _run_summarizer("gpt-5-mini")
            logger.info(
                f"Created summary for {len(messages)} items using gpt-5-mini (fallback)"
            )
            return summary_dict
        except Exception as e:
            logger.warning(f"Summarization fallback failed with gpt-5-mini: {e}")

    # Final fallback: return basic summary
    logger.error(f"All summarization attempts failed for {len(messages)} messages")
    return {
        "summary_text": f"Previous conversation with {len(messages)} messages.",
        "goals": ["Continue conversation"],
        "accomplishments": [],
        "tool_calls": [],
        "key_insights": [],
        "most_recent_state": "Conversation in progress",
    }
