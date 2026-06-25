"""Chat endpoints for AI conversation"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies import verify_be_auth, verify_service_auth
from app.llm import llm_service
from app.models.chat import ChatRequest, ChatResponse
from app.services import streaming_service

logger = logging.getLogger(__name__)
chat_router = APIRouter()


def _prepare_chat_request(chat_request: ChatRequest) -> tuple[str, Dict[str, Any]]:
    """
    Prepare prompt and LLM kwargs from chat request.

    Args:
        chat_request: The chat request

    Returns:
        Tuple of (prompt, llm_kwargs)
    """
    # Convert messages to a single prompt
    prompt = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_request.messages])

    # Prepare kwargs for the LLM call
    llm_kwargs: Dict[str, Any] = {}
    if chat_request.max_tokens:
        llm_kwargs["max_tokens"] = chat_request.max_tokens
    if chat_request.temperature:
        llm_kwargs["temperature"] = chat_request.temperature
    if chat_request.reasoning_effort:
        llm_kwargs["reasoning_effort"] = chat_request.reasoning_effort.value

    return prompt, llm_kwargs


def _validate_provider(provider: str | None) -> None:
    """
    Validate that the provider is supported.

    Args:
        provider: The provider to validate (optional, uses default if None)

    Raises:
        HTTPException: If provider is not supported
    """
    try:
        logger.info(f"Creating client for provider: {provider}")
        from app.llm.factory import LLMClientFactory

        LLMClientFactory.create_client(provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@chat_router.get("/")
async def chat_info() -> Dict[str, Any]:
    """
    Chat service information endpoint.
    """
    available_providers = llm_service.get_available_providers()
    # Convert enum keys to their string values for JSON serialization
    providers_dict = {
        k.value if hasattr(k, "value") else str(k): v
        for k, v in available_providers.items()
    }
    return {
        "status": "success",
        "service": "rsgpt-ai-core-chat",
        "available_providers": providers_dict,
    }


@chat_router.post("/", response_model=ChatResponse)
async def chat_completion_non_streaming(
    chat_request: ChatRequest,
    request: Request,
    service_name: str = Depends(verify_service_auth),
):
    """
    Generate non-streaming chat completion using specified LLM provider.

    Supports configurable models, provider-specific parameters, RAG context retrieval,
    and tool calling (function calling).

    Tool Calling:
    - Pass `tools` array with tool definitions (OpenAI format)
    - Response includes `tool_calls` if the model wants to call functions
    - Client is responsible for executing tools and making follow-up requests

    Requires MCP service token authentication (X-Service-Token header).
    Used by MCP servers (Settle3, RS2, etc.) for LLM calls.
    """
    try:
        prompt, llm_kwargs = _prepare_chat_request(chat_request)
        _validate_provider(chat_request.provider)

        # Generate non-streaming response
        result = await streaming_service.generate_chat_response(
            prompt, chat_request, llm_kwargs
        )

        return ChatResponse(**result)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors (like unsupported provider)
        logger.error(f"Chat completion validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating response: {str(e)}"
        )


@chat_router.post("/stream")
async def chat_completion_streaming(
    chat_request: ChatRequest,
    request: Request,
    auth_info: dict = Depends(verify_be_auth),
):
    """
    Generate streaming chat completion using specified LLM provider.

    Supports streaming responses with configurable models, provider-specific parameters,
    and RAG context retrieval.

    Requires BE service token authentication (X-Service-Token header).
    """
    try:
        prompt, llm_kwargs = _prepare_chat_request(chat_request)
        _validate_provider(chat_request.provider)

        # Return streaming response with proper SSE headers
        return StreamingResponse(
            streaming_service.generate_stream_events(
                prompt, chat_request, llm_kwargs, request
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle validation errors (like unsupported provider)
        logger.error(f"Chat completion validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating response: {str(e)}"
        )
