"""Factory for creating LLM clients with provider switching"""

import logging
from typing import Optional

from app.config import settings

from .enums import LLMProvider
from .providers.base import BaseLLMClient
from .providers.claude_client import ClaudeClient
from .providers.litellm_client import LiteLLMClient
from .providers.openai_client import OpenAIClient
from .providers.perplexity_client import PerplexityClient

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """Factory for creating LLM clients with provider switching"""

    @staticmethod
    def create_client(provider: Optional[str] = None) -> BaseLLMClient:
        """Create an LLM client for the specified provider

        Args:
            provider: The provider name (openai, claude, perplexity)
                     If None, uses default from settings

        Returns:
            BaseLLMClient instance

        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        if provider is None:
            provider = settings.default_llm_provider

        provider = provider.lower()

        if provider == LLMProvider.OPENAI:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required but not configured")
            return OpenAIClient(settings.openai_api_key)

        elif provider == LLMProvider.ANTHROPIC:
            logger.info("Creating Claude client")
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key is required but not configured")
            return ClaudeClient(settings.anthropic_api_key)

        elif provider == LLMProvider.PERPLEXITY:
            if not settings.perplexity_api_key:
                raise ValueError("Perplexity API key is required but not configured")
            return PerplexityClient(settings.perplexity_api_key)

        elif provider == LLMProvider.LITELLM:
            # For LiteLLM, we need to check which provider is being used
            # Default to anthropic for now, but this should be configurable
            if settings.anthropic_api_key:
                return LiteLLMClient(settings.anthropic_api_key)
            elif settings.openai_api_key:
                return LiteLLMClient(settings.openai_api_key)
            else:
                raise ValueError(
                    "LiteLLM requires an API key for the underlying provider"
                )

        else:
            raise ValueError(f"Unsupported provider: {provider}")
