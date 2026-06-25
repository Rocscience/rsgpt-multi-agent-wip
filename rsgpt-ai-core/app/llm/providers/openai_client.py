"""OpenAI client implementation"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    ContentFilterFinishReasonError,
    InternalServerError,
    LengthFinishReasonError,
    NotFoundError,
    OpenAI,
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


def _convert_chat_messages_to_responses_input(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Chat Completions history to Responses API input items.

    The RS3 inner agent (and other MCP clients) send multi-turn tool loops using
    ``role: "tool"`` and assistant ``tool_calls``. The Responses API expects
    ``function_call`` / ``function_call_output`` items instead.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not msg:
            continue

        msg_type = msg.get("type")
        role = msg.get("role")

        if msg_type == "function_call":
            out.append(
                {
                    "type": "function_call",
                    "call_id": msg.get("call_id") or msg.get("id") or "",
                    "name": msg.get("name") or "",
                    "arguments": msg.get("arguments") or "{}",
                }
            )
            continue

        if msg_type == "function_call_output":
            out.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.get("call_id") or msg.get("tool_call_id") or "",
                    "output": msg.get("output") or msg.get("content") or "",
                }
            )
            continue

        if role == "tool":
            out.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.get("tool_call_id") or msg.get("call_id") or "",
                    "output": msg.get("content") or msg.get("output") or "",
                }
            )
            continue

        if role == "assistant":
            content = msg.get("content")
            tool_calls = msg.get("tool_calls") or []
            if content:
                out.append({"role": "assistant", "content": content})
            for tc in tool_calls:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments", tc.get("arguments", "{}"))
                if not isinstance(raw_args, str):
                    raw_args = json.dumps(raw_args)
                out.append(
                    {
                        "type": "function_call",
                        "call_id": tc.get("id") or "",
                        "name": fn.get("name") or tc.get("name") or "",
                        "arguments": raw_args,
                    }
                )
            if not content and not tool_calls:
                out.append({"role": "assistant", "content": ""})
            continue

        if role in ("user", "system", "developer"):
            out.append({"role": role, "content": msg.get("content") or ""})
            continue

        out.append(msg)
    return out


class OpenAIClient(BaseLLMClient):
    """OpenAI client using responses API"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-5"  # Default model

    def _handle_openai_exceptions(self, e: Exception) -> Exception:
        """Handle OpenAI exceptions and provide user-friendly error messages"""
        if isinstance(e, BadRequestError):
            logger.error(f"OpenAI bad request error: {e}")
            return Exception(
                f"Invalid request to OpenAI API. Please check your input parameters: {e}"
            )

        elif isinstance(e, AuthenticationError):
            logger.error(f"OpenAI authentication error: {e}")
            return Exception(
                "OpenAI API authentication failed. Please check your API key and ensure it's valid."
            )

        elif isinstance(e, PermissionDeniedError):
            logger.error(f"OpenAI permission denied error: {e}")
            return Exception(
                "Access denied to OpenAI API. "
                "Please check your account permissions and subscription status."
            )

        elif isinstance(e, NotFoundError):
            logger.error(f"OpenAI not found error: {e}")
            return Exception(
                f"Requested OpenAI resource not found. "
                f"Please check the model name and availability: {e}"
            )

        elif isinstance(e, ConflictError):
            logger.error(f"OpenAI conflict error: {e}")
            return Exception(f"Request conflict with OpenAI API. Please try again: {e}")

        elif isinstance(e, UnprocessableEntityError):
            logger.error(f"OpenAI unprocessable entity error: {e}")
            return Exception(
                f"OpenAI API couldn't process the request. Please check your input format: {e}"
            )

        elif isinstance(e, RateLimitError):
            if "insufficient_quota" in str(e):
                logger.error(f"OpenAI quota exceeded: {e}")
                return Exception(
                    "OpenAI API quota exceeded. Please check your billing and "
                    "usage limits at https://platform.openai.com/account/billing"
                )
            else:
                logger.error(f"OpenAI rate limit error: {e}")
                return Exception(
                    f"OpenAI rate limit exceeded. Please wait before making more requests: {e}"
                )

        elif isinstance(e, InternalServerError):
            logger.error(f"OpenAI internal server error: {e}")
            return Exception(
                "OpenAI API is experiencing internal issues. Please try again later."
            )

        elif isinstance(e, LengthFinishReasonError):
            logger.error(f"OpenAI length finish reason error: {e}")
            return Exception(
                "OpenAI response was truncated due to length limits. "
                "Consider increasing max_tokens or reducing input length."
            )

        elif isinstance(e, ContentFilterFinishReasonError):
            logger.error(f"OpenAI content filter error: {e}")
            return Exception(
                "OpenAI content filter blocked the request or response. "
                "Please review your content for policy violations."
            )

        elif isinstance(e, APIError):
            logger.error(f"OpenAI API error: {e}")
            return Exception(f"OpenAI API error: {e}")

        else:
            logger.error(f"OpenAI unexpected error: {e}")
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
        messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Generate response using OpenAI's API"""
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
                logger.info(f"Using {user_permission or 'basic'} template for OpenAI")

            # Format tools to OpenAI responses API format (instead of chat completion API format)
            if tools:
                for i in range(len(tools)):
                    tools[i].update(tools[i].pop("function"))

            if stream:
                return self._generate_streaming(
                    formatted_prompt, model_to_use, **kwargs
                )
            else:
                return await self._generate_non_streaming(
                    formatted_prompt,
                    model_to_use,
                    tools=tools,
                    messages=messages,
                    **kwargs,
                )
        except Exception as e:
            raise self._handle_openai_exceptions(e)

    async def _generate_non_streaming(
        self,
        prompt: str,
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate non-streaming response with optional tool calling support"""
        # Run the sync OpenAI call in a thread to avoid blocking
        loop = asyncio.get_event_loop()

        def _make_request():
            # Extract reasoning effort if provided
            reasoning_effort = kwargs.get("reasoning_effort")

            # Build input messages - use provided messages or create from prompt
            if messages:
                input_messages = _convert_chat_messages_to_responses_input(messages)
            else:
                input_messages = [{"role": "user", "content": prompt}]

            request_params = {
                "model": model,
                "input": input_messages,
                "stream": False,
            }

            # Add tools if provided (for function calling)
            if tools:
                request_params["tools"] = tools
                logger.info(f"Tool calling enabled with {len(tools)} tools")

            # Add reasoning effort for gpt models (including "none")
            if reasoning_effort is not None and model.startswith("gpt"):
                request_params["reasoning"] = {"effort": reasoning_effort}

            # Add other parameters
            if "max_tokens" in kwargs:
                request_params["max_tokens"] = kwargs["max_tokens"]
            if "temperature" in kwargs:
                request_params["temperature"] = kwargs["temperature"]

            response = self.client.responses.create(**request_params)
            return response

        response = await loop.run_in_executor(None, _make_request)

        # Extract content (may be empty if model wants to call tools)
        content = response.output_text or ""

        usage = {
            "prompt_tokens": response.usage.input_tokens if response.usage else 0,
            "completion_tokens": response.usage.output_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }

        tool_calls = None
        if hasattr(response, "output") and response.output:
            if isinstance(response.output, list):
                for item in response.output:
                    if hasattr(item, "type") and item.type == "function_call":
                        tool_calls = tool_calls or []
                        tool_calls.append(
                            {
                                "id": (
                                    item.call_id
                                    if hasattr(item, "call_id")
                                    else item.id
                                ),
                                "type": "function",
                                "function": {
                                    "name": item.name,
                                    "arguments": (
                                        item.arguments
                                        if isinstance(item.arguments, str)
                                        else json.dumps(item.arguments)
                                    ),
                                },
                            }
                        )
                        logger.info(f"Tool call detected: {item.name}")
        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=model,
            usage=usage,
            tool_calls=tool_calls,
        )

    async def _generate_streaming(
        self, prompt: str, model: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        logger.info(f"Generating streaming response for model: {model}")
        logger.info(f"Kwargs: {kwargs}")

        reasoning_effort = kwargs.get("reasoning_effort")
        request_params: dict[str, Any] = {
            "model": model,
            "input": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        # Add reasoning effort for gpt models (including "none")
        if reasoning_effort is not None and model.startswith("gpt"):
            request_params["reasoning"] = {"effort": reasoning_effort}

        # Add other parameters
        if "max_tokens" in kwargs:
            request_params["max_tokens"] = kwargs["max_tokens"]
        if "temperature" in kwargs:
            request_params["temperature"] = kwargs["temperature"]

        try:
            # Use async client to prevent blocking the event loop
            stream = await self.async_client.responses.create(**request_params)

            # Iterate over events asynchronously
            async for event in stream:
                # Yield control back to event loop to prevent buffering
                await asyncio.sleep(0)

                if hasattr(event, "type"):
                    if event.type == "response.output_text.delta":
                        # For delta events, use the 'delta' field
                        if hasattr(event, "delta") and event.delta:
                            yield event.delta
                    elif event.type == "response.output_text.done":
                        # For done events, we could yield the full text, but it's usually better
                        # to just rely on the deltas for streaming. Skip this to avoid duplication.
                        pass
                    elif event.type == "response.created":
                        logger.info(f"Response created: {event.response.id}")
                    elif event.type == "response.in_progress":
                        logger.info(f"Response in progress: {event.response.id}")
                    elif event.type == "response.completed":
                        logger.info(f"Response completed: {event.response.id}")
                    elif event.type == "response.failed":
                        error_msg = (
                            event.response.error
                            if hasattr(event.response, "error")
                            else "Unknown error"
                        )
                        logger.error(f"Response failed: {error_msg}")
                        raise Exception(
                            f"OpenAI streaming response failed: {error_msg}"
                        )
        except Exception as e:
            raise self._handle_openai_exceptions(e)

    @property
    def provider_name(self) -> str:
        return LLMProvider.OPENAI.value
