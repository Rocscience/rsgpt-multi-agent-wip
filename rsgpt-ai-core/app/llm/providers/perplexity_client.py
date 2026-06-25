"""Perplexity client implementation"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from app.services.streaming.chat_instructions import PERPLEXITY_CHAT_RESPONSE_TEMPLATE

from ..enums import LLMProvider
from .base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class PerplexityClient(BaseLLMClient):
    """Perplexity client using httpx"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
        self.model = "sonar-pro"

    def _handle_perplexity_exceptions(self, e: Exception) -> Exception:
        """Handle Perplexity exceptions and provide user-friendly error messages"""
        if isinstance(e, BadRequestError):
            logger.error(f"Perplexity bad request error: {e}")
            return Exception(
                f"Invalid request to Perplexity API. Please check your input parameters: {e}"
            )

        elif isinstance(e, AuthenticationError):
            logger.error(f"Perplexity authentication error: {e}")
            return Exception(
                "Perplexity API authentication failed. "
                "Please check your API key and ensure it's valid."
            )

        elif isinstance(e, PermissionDeniedError):
            logger.error(f"Perplexity permission denied error: {e}")
            return Exception(
                "Access denied to Perplexity API. "
                "Please check your account permissions and subscription status."
            )

        elif isinstance(e, NotFoundError):
            logger.error(f"Perplexity not found error: {e}")
            return Exception(
                f"Requested Perplexity resource not found. "
                f"Please check the model name and availability: {e}"
            )

        elif isinstance(e, ConflictError):
            logger.error(f"Perplexity conflict error: {e}")
            return Exception(
                f"Request conflict with Perplexity API. Please try again: {e}"
            )

        elif isinstance(e, UnprocessableEntityError):
            logger.error(f"Perplexity unprocessable entity error: {e}")
            return Exception(
                f"Perplexity API couldn't process the request. Please check your input format: {e}"
            )

        elif isinstance(e, RateLimitError):
            logger.error(f"Perplexity rate limit error: {e}")
            return Exception(
                f"Perplexity rate limit exceeded. Please wait before making more requests: {e}"
            )

        elif isinstance(e, InternalServerError):
            logger.error(f"Perplexity internal server error: {e}")
            return Exception(
                "Perplexity API is experiencing internal issues. Please try again later."
            )

        elif isinstance(e, APIError):
            logger.error(f"Perplexity API error: {e}")
            return Exception(f"Perplexity API error: {e}")

        else:
            logger.error(f"Perplexity unexpected error: {e}")
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
        """Generate response using Perplexity's API"""
        try:
            model_to_use = model or self.model

            # Format prompt with template if relevant_context is provided
            # Perplexity always uses its own template (has web search capability)
            # Note: Perplexity doesn't separate expert_opinion, so combine contexts
            formatted_prompt = prompt
            combined_context = relevant_context or ""
            if expert_opinion:
                combined_context = (
                    expert_opinion
                    + ("\n\n" if relevant_context else "")
                    + (relevant_context or "")
                )

            if combined_context:
                # Put user query FIRST so Perplexity's search classifier knows what to search for
                formatted_prompt = (
                    f"USER QUESTION: {prompt}\n\n"
                    + PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
                        relevant_context=combined_context or ""
                    )
                )
                logger.info(
                    "Using Perplexity template with web search capability and RAG context"
                )

            if stream:
                return self._generate_streaming(
                    formatted_prompt, model_to_use, **kwargs
                )
            else:
                return await self._generate_non_streaming(
                    formatted_prompt, model_to_use, **kwargs
                )
        except Exception as e:
            raise self._handle_perplexity_exceptions(e)

    async def _generate_non_streaming(
        self, prompt: str, model: str, **kwargs
    ) -> LLMResponse:
        """Generate non-streaming response"""
        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        # Add standard OpenAI parameters
        if "max_tokens" in kwargs:
            request_params["max_tokens"] = kwargs["max_tokens"]
        if "temperature" in kwargs:
            request_params["temperature"] = kwargs["temperature"]

        # Add Perplexity-specific parameters using extra_body
        # This bypasses OpenAI SDK's parameter validation
        request_params["extra_body"] = {
            "enable_search_classifier": True,  # Let Perplexity decide when to search
        }

        response = await self.client.chat.completions.create(
            **request_params
        )  # type: ignore[call-overload]

        # Check if response is a string (error case) instead of expected object
        if isinstance(response, str):
            logger.error(f"Perplexity API returned string response: {response}")
            raise Exception(f"Perplexity API error: {response}")

        # Check if response has the expected structure
        if not hasattr(response, "choices") or not response.choices:
            logger.error(
                f"Perplexity API returned unexpected response format: {response}"
            )
            raise Exception("Perplexity API returned unexpected response format")

        return LLMResponse(
            content=response.choices[0].message.content,
            provider=self.provider_name,
            model=model,
            usage={
                "prompt_tokens": (
                    response.usage.prompt_tokens
                    if hasattr(response, "usage") and response.usage
                    else 0
                ),
                "completion_tokens": (
                    response.usage.completion_tokens
                    if hasattr(response, "usage") and response.usage
                    else 0
                ),
                "total_tokens": (
                    response.usage.total_tokens
                    if hasattr(response, "usage") and response.usage
                    else 0
                ),
            },
        )

    async def _generate_streaming(
        self, prompt: str, model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        logger.info(f"Generating streaming response for model: {model}")
        logger.info(f"Kwargs: {kwargs}")

        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        # Add standard OpenAI parameters
        if "max_tokens" in kwargs:
            request_params["max_tokens"] = kwargs["max_tokens"]
        if "temperature" in kwargs:
            request_params["temperature"] = kwargs["temperature"]

        # Add Perplexity-specific parameters using extra_body
        # This bypasses OpenAI SDK's parameter validation
        request_params["extra_body"] = {
            "enable_search_classifier": True,  # Let Perplexity decide when to search
        }

        try:
            completion = await self.client.chat.completions.create(
                **request_params
            )  # type: ignore[call-overload]

            # Track if we've already sent search results
            search_results_sent = False
            usage_info = None

            async for chunk in completion:
                # Collect and yield search results as soon as they're available
                if (
                    hasattr(chunk, "search_results")
                    and chunk.search_results
                    and not search_results_sent
                ):
                    search_results_sent = True
                    try:
                        # Yield search results as a special JSON marker
                        # Convert to list/dict to handle any serialization issues
                        results_list = (
                            list(chunk.search_results)
                            if not isinstance(chunk.search_results, (list, dict))
                            else chunk.search_results
                        )

                        search_results_data = {
                            "_metadata": "search_results",
                            "results": results_list,
                        }
                        search_json = json.dumps(search_results_data)
                        yield f"\n__SEARCH_RESULTS__{search_json}__SEARCH_RESULTS__\n"
                        logger.info("Perplexity search results yielded")
                    except (TypeError, ValueError) as e:
                        # If we can't serialize the search results, log and continue
                        logger.warning(f"Could not serialize search results: {e}")

                if hasattr(chunk, "usage") and chunk.usage:
                    usage_info = chunk.usage

                # Yield content
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Log usage when streaming is complete
                if chunk.choices and chunk.choices[0].finish_reason:
                    if usage_info:
                        logger.info(f"Perplexity usage: {usage_info}")

        except Exception as e:
            raise self._handle_perplexity_exceptions(e)

    @property
    def provider_name(self) -> str:
        return LLMProvider.PERPLEXITY.value
