"""Anthropic Claude client implementation"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from anthropic import (
    APIError,
    AsyncAnthropic,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from app.services.streaming.chat_instructions import (
    BASIC_USERS_CHAT_RESPONSE_TEMPLATE,
    FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE,
)

from ..enums import LLMProvider
from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class ClaudeClient(BaseLLMClient):
    """Anthropic Claude client"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def _handle_anthropic_exceptions(self, e: Exception) -> Exception:
        """Handle Anthropic exceptions and provide user-friendly error messages"""
        if isinstance(e, BadRequestError):
            logger.error(f"Anthropic bad request error: {e}")
            return Exception(
                f"Invalid request to Anthropic API. Please check your input parameters: {e}"
            )

        elif isinstance(e, AuthenticationError):
            logger.error(f"Anthropic authentication error: {e}")
            return Exception(
                "Anthropic API authentication failed. "
                "Please check your API key and ensure it's valid."
            )

        elif isinstance(e, PermissionDeniedError):
            logger.error(f"Anthropic permission denied error: {e}")
            return Exception(
                "Access denied to Anthropic API. "
                "Please check your account permissions and subscription status."
            )

        elif isinstance(e, NotFoundError):
            logger.error(f"Anthropic not found error: {e}")
            return Exception(
                f"Requested Anthropic resource not found. "
                f"Please check the model name and availability: {e}"
            )

        elif isinstance(e, ConflictError):
            logger.error(f"Anthropic conflict error: {e}")
            return Exception(
                f"Request conflict with Anthropic API. Please try again: {e}"
            )

        elif isinstance(e, UnprocessableEntityError):
            logger.error(f"Anthropic unprocessable entity error: {e}")
            return Exception(
                f"Anthropic API couldn't process the request. Please check your input format: {e}"
            )

        elif isinstance(e, RateLimitError):
            logger.error(f"Anthropic rate limit error: {e}")
            return Exception(
                f"Anthropic rate limit exceeded. Please wait before making more requests: {e}"
            )

        elif isinstance(e, InternalServerError):
            logger.error(f"Anthropic internal server error: {e}")
            return Exception(
                "Anthropic API is experiencing internal issues. Please try again later."
            )

        elif isinstance(e, APIError):
            logger.error(f"Anthropic API error: {e}")
            return Exception(f"Anthropic API error: {e}")

        else:
            logger.error(f"Anthropic unexpected error: {e}")
            return e

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
        """Generate response using Anthropic's API"""
        try:
            model_to_use = model or self.model

            # Format prompt with template if relevant_context is provided
            formatted_prompt = prompt
            if relevant_context or expert_opinion:
                # Select template based on user permission
                if user_permission == "flexible":
                    template = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE
                    formatted_prompt = (
                        template.safe_substitute(
                            expert_opinion=expert_opinion or "",
                            relevant_context=relevant_context or "",
                        )
                        + f"\n\nUser Query: {prompt}"
                    )
                else:
                    template = BASIC_USERS_CHAT_RESPONSE_TEMPLATE
                    formatted_prompt = (
                        template.safe_substitute(
                            relevant_context=relevant_context or ""
                        )
                        + f"\n\nUser Query: {prompt}"
                    )
                logger.info(f"Using {user_permission or 'basic'} template for Claude")

            if stream:
                return self._generate_streaming(
                    formatted_prompt, model_to_use, **kwargs
                )
            else:
                return await self._generate_non_streaming(
                    formatted_prompt, model_to_use, **kwargs
                )
        except Exception as e:
            raise self._handle_anthropic_exceptions(e)

    async def _generate_non_streaming(
        self, prompt: str, model: str, **kwargs
    ) -> LLMResponse:
        """Generate non-streaming response"""
        request_params = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
        }

        if "temperature" in kwargs:
            request_params["temperature"] = kwargs["temperature"]

        response = await self.client.messages.create(**request_params)

        content = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

        return LLMResponse(
            content=content, provider=self.provider_name, model=model, usage=usage
        )

    async def _generate_streaming(
        self, prompt: str, model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        request_params = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "messages": [{"role": "user", "content": prompt}],
        }

        if "temperature" in kwargs:
            request_params["temperature"] = kwargs["temperature"]

        try:
            async with self.client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    if text:  # Only yield non-empty text
                        yield text
        except Exception as e:
            raise self._handle_anthropic_exceptions(e)

    @property
    def provider_name(self) -> str:
        return LLMProvider.ANTHROPIC.value
