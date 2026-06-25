"""Streaming service for chat responses with OpenAI-style events"""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator, Optional, cast

from fastapi import Request

from app.llm import llm_service
from app.llm.providers.base import LLMResponse
from app.models.channels import Channel
from app.models.chat import (
    ChatRequest,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseInfo,
    ResponseInProgressEvent,
    ResponseOutputTextDeltaEvent,
    ResponseSearchResultsEvent,
    ResponseStatus,
    ResponseUsage,
)
from app.services.search.rag_service import get_rag_service

logger = logging.getLogger(__name__)


class CancellationToken:
    """Token to signal cancellation across async operations"""

    def __init__(self):
        self._cancelled = asyncio.Event()

    def cancel(self):
        """Mark as cancelled"""
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        """Check if cancelled"""
        return self._cancelled.is_set()

    async def wait_for_cancellation(self):
        """Wait until cancelled"""
        await self._cancelled.wait()


class StreamingService:
    """Service for handling streaming chat responses with structured events"""

    def __init__(self):
        """Initialize streaming service with RAG support"""
        self.rag_service = get_rag_service()

    async def _retrieve_rag_context(
        self, request: ChatRequest
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Retrieve RAG context if enabled.

        Args:
            request: The chat request with RAG parameters

        Returns:
            Tuple of (expert_opinion, relevant_context)
        """
        relevant_context = None
        expert_opinion = None

        if not request.use_rag:
            return expert_opinion, relevant_context

        logger.info("RAG enabled, retrieving context...")
        try:
            # Get the user's query (last message in conversation)
            query = request.messages[-1].content

            # Execute RAG pipeline
            rag_result = await self.rag_service.retrieve_and_rerank(
                query=query,
                source_channels=request.rag_source_channels,
                user_permission=request.rag_user_permission,
                top_k=request.rag_top_k,
            )

            # Store context separately for flexible users with tech support access
            if rag_result.contexts:
                # For flexible users, separate tech support from other contexts
                if request.rag_user_permission.value == "flexible" and any(
                    c == Channel.TECH_SUPPORT.value
                    for c in rag_result.channels_searched
                ):
                    expert_opinion, relevant_context = (
                        rag_result.format_context_by_channel()
                    )
                    logger.info(
                        f"RAG: Retrieved {len(rag_result.contexts)} contexts "
                        f"from {rag_result.channels_searched} "
                        f"(tech_support separated as expert_opinion) "
                        f"(reranker: {rag_result.reranker_used})"
                    )
                else:
                    relevant_context = rag_result.format_context()
                    logger.info(
                        f"RAG: Retrieved {len(rag_result.contexts)} contexts "
                        f"from {rag_result.channels_searched} "
                        f"(reranker: {rag_result.reranker_used})"
                    )
            else:
                logger.warning("RAG: No contexts retrieved")

        except Exception:
            logger.exception("RAG pipeline failed, continuing without context")

        return expert_opinion, relevant_context

    async def generate_stream_events(
        self,
        prompt: str,
        request: ChatRequest,
        llm_kwargs: dict,
        http_request: Optional[Request] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming chat responses with OpenAI-style events.

        Args:
            prompt: The processed prompt string
            request: The original chat request
            llm_kwargs: Additional LLM parameters
            http_request: The FastAPI Request object to check for client disconnection

        Yields:
            Server-sent event strings with structured response events
        """
        # Generate unique response ID and track state
        response_id = str(uuid.uuid4())
        created_at = time.time()
        sequence_number = 0
        accumulated_text = ""

        def emit_event(event_type: str, data: dict):
            """Helper to emit a server-sent event with proper format"""
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        try:
            # 1. Send response.created event
            response_info = ResponseInfo(
                id=response_id,
                created_at=created_at,
                model=request.model or "default",
                provider=request.provider or "default",
                status=ResponseStatus.IN_PROGRESS,
                usage=None,
            )

            sequence_number += 1
            created_event = ResponseCreatedEvent(
                sequence_number=sequence_number, response=response_info
            )
            yield emit_event("response.created", created_event.model_dump())

            # 2. Send response.in_progress event
            sequence_number += 1
            in_progress_event = ResponseInProgressEvent(
                sequence_number=sequence_number, response=response_info
            )
            yield emit_event("response.in_progress", in_progress_event.model_dump())

            # 3. If RAG is enabled, retrieve context
            expert_opinion, relevant_context = await self._retrieve_rag_context(request)

            # 4. Start streaming and emit delta events
            reserved = {
                "prompt",
                "stream",
                "provider",
                "model",
                "relevant_context",
                "expert_opinion",
                "user_permission",
            }
            safe_llm_kwargs = {k: v for k, v in llm_kwargs.items() if k not in reserved}

            stream_result = await llm_service.generate(
                prompt=prompt,
                stream=True,
                provider=request.provider,
                model=request.model,
                relevant_context=relevant_context,
                expert_opinion=expert_opinion,
                user_permission=(
                    request.rag_user_permission.value if request.use_rag else None
                ),
                **safe_llm_kwargs,
            )

            # Since we called with stream=True, we know this is an AsyncGenerator
            stream = cast(AsyncGenerator[str, None], stream_result)

            # Create cancellation token and monitor task
            cancellation_token = CancellationToken()

            async def monitor_disconnection():
                """Monitor for client disconnection and cancel streaming"""
                try:
                    while True:
                        if http_request and await http_request.is_disconnected():
                            logger.warning(
                                f"[Monitor] Client disconnected for response {response_id}, "
                                "cancelling LLM stream"
                            )
                            cancellation_token.cancel()
                            # Force close the async generator to abort the HTTP request
                            try:
                                await stream.aclose()
                            except Exception as e:
                                logger.debug(f"Error closing stream: {e}")
                            return
                        await asyncio.sleep(0.5)  # Check every 500ms
                except Exception as e:
                    logger.debug(f"Disconnection monitor ended: {e}")

            # Start monitor task if we have an http_request
            monitor_task = None
            if http_request:
                monitor_task = asyncio.create_task(monitor_disconnection())

            # Process streaming chunks from any provider
            async for chunk in stream:
                # Check cancellation token
                if cancellation_token.is_cancelled():
                    logger.info(
                        f"Stream cancelled for response {response_id}, breaking loop"
                    )
                    break

                if chunk:  # Only send non-empty chunks
                    # Check if this chunk contains search results metadata (Perplexity)
                    if "__SEARCH_RESULTS__" in chunk:
                        # Extract and parse search results
                        try:
                            pattern = re.compile(
                                r"__SEARCH_RESULTS__(.+?)__SEARCH_RESULTS__", re.DOTALL
                            )

                            emitted_event = None

                            def _emit_results(payload: str) -> None:
                                data = json.loads(payload)
                                nonlocal sequence_number
                                sequence_number += 1
                                evt = ResponseSearchResultsEvent(
                                    sequence_number=sequence_number,
                                    response_id=response_id,
                                    search_results=data.get("results", []),
                                )
                                nonlocal emitted_event
                                emitted_event = emit_event(
                                    "response.search_results", evt.model_dump()
                                )
                                # log
                                logger.info(
                                    "Search results event emitted with %d results",
                                    len(data.get("results", [])),
                                )

                            # Emit events for every occurrence and remove them from the chunk
                            for m in pattern.finditer(chunk):
                                _emit_results(m.group(1))
                            chunk = pattern.sub("", chunk)
                            if emitted_event:
                                yield emitted_event

                        except Exception:
                            logger.exception("Failed to parse search results")
                            # If parsing fails, treat as regular content

                    # Regular content chunk
                    accumulated_text += chunk
                    sequence_number += 1

                    delta_event = ResponseOutputTextDeltaEvent(
                        sequence_number=sequence_number,
                        delta=chunk,
                        response_id=response_id,
                    )
                    yield emit_event(
                        "response.output_text.delta", delta_event.model_dump()
                    )

            # 4.5. Extract and emit search results from accumulated text
            # (for non-Perplexity models only)
            # This runs after streaming is complete but before response.completed event
            if accumulated_text.strip() and request.provider != "perplexity":
                # Extract URLs from markdown links and plain text
                url_pattern = r"https?://[^\s\)\]>]+"
                extracted_urls = list(set(re.findall(url_pattern, accumulated_text)))

                if extracted_urls:
                    # Convert URLs to search results format
                    search_results = [
                        {
                            "url": url,
                            "title": url.split("/")[-1] if url.split("/")[-1] else url,
                            "source": "extracted_from_response",
                        }
                        for url in extracted_urls
                    ]

                    # Deduplicate by URL (same logic as frontend and agent service)
                    seen_urls = set()
                    deduplicated_results = []
                    for result in search_results:
                        url = result.get("url")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            deduplicated_results.append(result)

                    search_results = deduplicated_results

                    sequence_number += 1
                    search_results_event = ResponseSearchResultsEvent(
                        sequence_number=sequence_number,
                        response_id=response_id,
                        search_results=search_results,
                    )
                    yield emit_event(
                        "response.search_results", search_results_event.model_dump()
                    )
                    logger.info(
                        f"Emitted {len(search_results)} extracted search results for "
                        f"non-Perplexity response {response_id}"
                    )

            # 5. Send response.completed event with final usage info
            sequence_number += 1
            final_response_info = ResponseInfo(
                id=response_id,
                created_at=created_at,
                model=request.model or "default",
                provider=request.provider or "default",
                status=ResponseStatus.COMPLETED,
                usage=ResponseUsage(
                    input_tokens=len(prompt.split()),  # Rough estimate
                    output_tokens=len(accumulated_text.split()),  # Rough estimate
                    total_tokens=len(prompt.split()) + len(accumulated_text.split()),
                ),
            )

            completed_event = ResponseCompletedEvent(
                sequence_number=sequence_number, response=final_response_info
            )
            yield emit_event("response.completed", completed_event.model_dump())

        except asyncio.CancelledError:
            # Client disconnected - log and exit gracefully
            logger.info(
                f"Chat response {response_id} cancelled due to client disconnection"
            )
            # Ensure the stream is closed (in case exception came from elsewhere)
            if "stream" in locals():
                try:
                    await stream.aclose()
                except Exception as e:
                    logger.debug(f"Error closing stream during cancellation: {e}")
            # Don't send failure event if client disconnected, they won't receive it anyway

        except ValueError as e:
            logger.error(f"Streaming validation error: {e}")
            sequence_number += 1
            error_event = ResponseErrorEvent(
                sequence_number=sequence_number, error=str(e)
            )
            yield emit_event("error", error_event.model_dump())

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            sequence_number += 1

            # Send failed event with error info
            failed_response_info = ResponseInfo(
                id=response_id,
                created_at=created_at,
                model=request.model or "default",
                provider=request.provider or "default",
                status=ResponseStatus.FAILED,
                usage=None,
            )

            failed_event = ResponseFailedEvent(
                sequence_number=sequence_number,
                response=failed_response_info,
                error=str(e),
            )
            yield emit_event("response.failed", failed_event.model_dump())

        finally:
            # Clean up monitor task if it exists
            if "monitor_task" in locals() and monitor_task and not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

    async def generate_chat_response(
        self,
        prompt: str,
        request: ChatRequest,
        llm_kwargs: dict,
    ) -> dict:
        """
        Generate non-streaming chat response.

        Args:
            prompt: The processed prompt string
            request: The original chat request
            llm_kwargs: Additional LLM parameters

        Returns:
            Dictionary with response data including content, provider, model, usage, and tool_calls
        """
        try:
            # 1. If RAG is enabled, retrieve context
            expert_opinion, relevant_context = await self._retrieve_rag_context(request)

            # 2. Generate response with non-streaming mode
            reserved = {
                "prompt",
                "stream",
                "provider",
                "model",
                "relevant_context",
                "expert_opinion",
                "user_permission",
                "tools",
                "messages",
            }
            safe_llm_kwargs = {k: v for k, v in llm_kwargs.items() if k not in reserved}

            # Convert tools from Pydantic models to dicts if provided
            tools_dict = None
            if request.tools:
                tools_dict = [tool.model_dump() for tool in request.tools]
                logger.info(f"Tool calling enabled with {len(tools_dict)} tools")

            # Convert messages to dict format for multi-turn conversations
            messages_dict = None
            if request.messages:
                messages_dict = [msg.model_dump() for msg in request.messages]
                # remove null field
                messages_dict = [
                    {k: v for k, v in msg.items() if v is not None}
                    for msg in messages_dict
                ]
            result = await llm_service.generate(
                prompt=prompt,
                stream=False,
                provider=request.provider,
                model=request.model,
                relevant_context=relevant_context,
                expert_opinion=expert_opinion,
                user_permission=(
                    request.rag_user_permission.value if request.use_rag else None
                ),
                tools=tools_dict,
                messages=messages_dict,
                **safe_llm_kwargs,
            )

            # Since we called with stream=False, we know this is an LLMResponse
            llm_response = cast(LLMResponse, result)

            # 3. Return response data (including tool_calls if present)
            response_data: dict[str, Any] = {
                "content": llm_response.content,
                "provider": llm_response.provider,
                "model": llm_response.model,
                "usage": llm_response.usage,
            }

            # Add tool_calls if the model requested function calls
            if llm_response.tool_calls:
                response_data["tool_calls"] = llm_response.tool_calls
                logger.info(
                    f"Response includes {len(llm_response.tool_calls)} tool calls"
                )

            return response_data

        except Exception as e:
            logger.exception(f"Chat completion error: {e}")
            raise


# Create a singleton instance for easy importing
streaming_service = StreamingService()
