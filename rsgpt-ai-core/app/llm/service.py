"""High-level LLM service with provider switching"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from app.config import settings

from .enums import LLMProvider
from .factory import LLMClientFactory
from .providers.base import LLMResponse

logger = logging.getLogger(__name__)


class LLMService:
    """High-level LLM service with provider switching"""

    def __init__(self, default_provider: Optional[str] = None):
        self.default_provider = default_provider or settings.default_llm_provider

    async def generate(
        self,
        prompt: str,
        stream: bool = False,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        relevant_context: Optional[str] = None,
        expert_opinion: Optional[str] = None,
        user_permission: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate response using specified or default provider

        Args:
            prompt: The input prompt
            stream: Whether to return streaming response
            provider: Provider to use (overrides default)
            model: Specific model to use
            relevant_context: RAG context to pass separately (not concatenated with prompt)
            expert_opinion: Tech support context for flexible users
            user_permission: User permission level (basic/flexible) for template selection
            tools: List of tool definitions for function calling (OpenAI format)
            messages: Full message history (for multi-turn tool calling)
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse for non-streaming, AsyncGenerator for streaming
        """
        logger.info(
            f"Generating response with provider: {provider}, model: {model}, "
            f"tools: {len(tools) if tools else 0}, kwargs: {kwargs}"
        )
        client = LLMClientFactory.create_client(provider or self.default_provider)
        return await client.generate(
            prompt,
            stream,
            model,
            relevant_context,
            expert_opinion,
            user_permission,
            tools=tools,
            messages=messages,
            **kwargs,
        )

    def get_available_providers(self) -> Dict[str, bool]:
        """Get list of available providers based on configured API keys

        Returns:
            Dict mapping provider names to availability status
        """
        return {
            LLMProvider.OPENAI: bool(settings.openai_api_key),
            LLMProvider.ANTHROPIC: bool(settings.anthropic_api_key),
            LLMProvider.PERPLEXITY: bool(settings.perplexity_api_key),
        }


# Global service instance
llm_service = LLMService()
