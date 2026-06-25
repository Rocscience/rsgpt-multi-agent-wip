"""Base classes for LLM providers"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Union


class LLMResponse:
    """Standardized LLM response format"""

    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        usage: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ):
        self.content = content
        self.provider = provider
        self.model = model
        self.usage = usage or {}
        self.tool_calls = tool_calls


class BaseLLMClient(ABC):
    """Base class for all LLM clients"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        stream: bool = False,
        model: Optional[str] = None,
        relevant_context: Optional[str] = None,
        expert_opinion: Optional[str] = None,
        user_permission: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate response from the LLM

        Args:
            prompt: The input prompt
            stream: Whether to return streaming response
            model: Specific model to use (overrides default)
            relevant_context: RAG context to pass separately (not concatenated with prompt)
            expert_opinion: Tech support context for flexible users
            user_permission: User permission level (basic/flexible) for template selection
            tools: List of tool definitions for function calling (OpenAI format)
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse for non-streaming, AsyncGenerator for streaming
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name"""
        pass
