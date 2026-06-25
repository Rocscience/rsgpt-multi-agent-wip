"""LiteLLM provider for Agent SDK integration"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class LiteLLMClient(BaseLLMClient):
    """Client for creating LiteLLM model instances for Agent SDK"""

    async def generate(
        self,
        prompt: str,
        stream: bool = False,
        model: Optional[str] = None,
        relevant_context: Optional[str] = None,
        expert_opinion: Optional[str] = None,
        user_permission: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate response from the LLM

        Note: This method is for compatibility with BaseLLMClient.
        For Agent SDK usage, use create_model() instead.

        Args:
            prompt: The input prompt
            stream: Whether to return streaming response
            model: Specific model to use
            relevant_context: RAG context (not used in this implementation)
            expert_opinion: Tech support context (not used in this implementation)
            user_permission: User permission level (not used in this implementation)
            **kwargs: Additional parameters

        Returns:
            LLMResponse for non-streaming, AsyncGenerator for streaming
        """
        raise NotImplementedError(
            "LiteLLMClient is designed for Agent SDK integration. "
            "Use create_model() to get a model instance for agents."
        )

    def create_model(self, model: str, **kwargs):
        """
        Create a LiteLLM model instance for use with Agent SDK

        Args:
            model: The model name (e.g., "anthropic/claude-3-5-sonnet-20240620", "openai/gpt-4o")
            **kwargs: Additional model configuration parameters

        Returns:
            LitellmModel instance for Agent SDK
        """
        try:
            from agents.extensions.models.litellm_model import LitellmModel
        except ImportError:
            raise ImportError(
                "LiteLLM support requires openai-agents[litellm]. "
                "Install it with: pip install 'openai-agents[litellm]'"
            )

        logger.info(f"Creating LiteLLM model for: {model}")
        return LitellmModel(model=model, api_key=self.api_key, **kwargs)

    @property
    def provider_name(self) -> str:
        """Get the provider name"""
        return "litellm"
