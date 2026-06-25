from typing import Optional, List, Tuple, AsyncGenerator
from uuid import UUID
import asyncio
import hashlib
import json
import logging
import time
import uuid

from fastapi import status
from fastapi.responses import StreamingResponse
from sqlalchemy import update

from app.db_interface.chats import (
    create_chat_session,
    delete_chat_session,
    get_chat_session,
    get_list_of_chat_sessions,
    create_user_message,
    create_ai_response,
    create_atomic_message_pair,
    update_ai_response_status,
    update_user_message_status,
    retry_user_message,
    get_conversation_history_for_user,
    update_ai_response_media_links,
    update_session_token_count
)
from app.db_interface.feedback import create_message_feedback
from app.db_interface.organizations import get_organization_by_user_id, increment_organization_questions_used
from app.db_interface.users import get_user_by_id, increment_user_agent_quota_used
from app.db_models.chats import ChatSessionsORM, UserMessagesORM, AIResponsesORM, MessageStatus
from app.db_models.organizations import OrganizationsORM
from app.db_models.feedback import MessageFeedbackORM
from app.models.consts import SOURCE_SELECTIONS
from app.models.chats import (
    UserMessageInitEvent,
    StreamErrorEvent,
    UserMessageDto,
    AIResponseDto,
    ConversationTurnDto,
    MediaData,
    MediaImage
)
from app.services.ai_core_client import ai_core_client
from app.services.timeline_coalescer import TimelineCoalescer
from app.services.media_extractor_service import extract_media_from_urls

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self):
        pass

    def create_chat_session(self, user_id: UUID, title: Optional[str] = None) -> ChatSessionsORM:
        """Create a new chat session for the user"""
        
        # Create the chat session entry
        return create_chat_session(title, user_id)
    
    def delete_chat_session(self, chat_session_id: UUID, user_id: UUID):
        """Soft Delete a chat session for the user"""

        return delete_chat_session(chat_session_id, user_id)

    def get_chat_session(self, chat_session_id: UUID, user_id: UUID) -> ChatSessionsORM:
        """Get chat session details"""

        # Obtain the ChatSessionORM
        return get_chat_session(chat_session_id, user_id)
    
    def get_list_chat_sessions(self, user_id: UUID, page: int, page_size: int) -> Tuple[List[ChatSessionsORM], int]:
        """Get paginated list of chat sessions for a user"""

        return get_list_of_chat_sessions(user_id, page, page_size)
    

    def get_conversation_history(self, user_id: UUID, session_id: UUID, page: int, page_size: int) -> tuple[List[ConversationTurnDto], int]:
        """
        Get hierarchical conversation history - user messages grouped with their AI responses.
        Returns conversation turns where each turn has a user message and all its AI responses.
        
        Args:
            user_id: The user ID (for authorization)
            session_id: The chat session UUID
            page: Page number for pagination
            page_size: Number of conversation turns per page
            
        Returns:
            tuple[List[ConversationTurnDto], int]: List of conversation turns and total count
        """
        # Get user messages with AI responses from db interface
        user_messages, total_count = get_conversation_history_for_user(user_id, session_id, page, page_size)
        
        # Create DTOs directly in the service layer
        conversation_turns = []
        
        for user_msg in user_messages:
            # Mark the latest AI response
            ai_responses_list = getattr(user_msg, 'ai_responses_list', [])
            latest_response_id = None
            if ai_responses_list:
                latest_response = ai_responses_list[-1]  # Most recent
                latest_response_id = latest_response.id
            
            # Create user message DTO
            user_message_dto = UserMessageDto(
                id=user_msg.id,
                message_text=user_msg.message_text,
                status=user_msg.status.value,
                sources_requested=user_msg.sources_requested or [],
                created_at=user_msg.created_at,
                client_temp_id=user_msg.client_temp_id,
                idempotency_key=user_msg.idempotency_key
            )
            
            # Create AI response DTOs
            ai_response_dtos = []
            for resp in ai_responses_list:
                ai_response_dtos.append(AIResponseDto(
                    id=resp.id,
                    message_text=resp.message_text,
                    status=resp.status.value,
                    response_time_ms=resp.response_time_ms,
                    sources_used=resp.sources_used or [],
                    media_links=self._convert_db_media_to_dto(resp.media_links),
                    search_results=resp.search_results,
                    token_count=resp.token_count,
                    run_id=resp.run_id,
                    trace_id=resp.trace_id,
                    model_used=resp.model_used,
                    created_at=resp.created_at,
                    is_latest=resp.id == latest_response_id,
                    is_agent_mode=resp.is_agent_mode,
                    timeline=resp.timeline,  # Include coalesced timeline blocks
                    usage_breakdown=resp.usage_breakdown  # NEW: Per-request usage breakdown (openai-agents v0.5.0)
                ))
            
            # Create conversation turn DTO
            conversation_turn = ConversationTurnDto(
                user_message=user_message_dto,
                ai_responses=ai_response_dtos,
                has_retries=len(ai_responses_list) > 1
            )
            
            conversation_turns.append(conversation_turn)
        
        return conversation_turns, total_count
    
    def _convert_db_media_to_dto(self, db_media_links: dict) -> MediaData:
        """Convert database media_links JSON to MediaData DTO"""
        if not db_media_links or not isinstance(db_media_links, dict):
            return MediaData(images=[])
        
        images = []
        raw_images = db_media_links.get("images", [])
        
        for img in raw_images:
            if isinstance(img, dict) and "image_url" in img and "source_url" in img:
                images.append(MediaImage(
                    image_url=img["image_url"],
                    source_url=img["source_url"]
                ))
            elif isinstance(img, str):
                # Fallback for old format - treat string as image_url with empty source_url
                images.append(MediaImage(
                    image_url=img,
                    source_url=""
                ))
        
        return MediaData(images=images)
    
    def retry_user_prompt(self, user_message_id: UUID) -> AIResponsesORM:
        """
        Retry a user prompt by creating a new AI response.
        
        Args:
            user_message_id: The ID of the user message to retry
            
        Returns:
            AIResponsesORM: The new AI response ready for streaming
        """
        return retry_user_message(user_message_id)
    
    def create_message_feedback(self, user_id: UUID, ai_response_id: UUID, helpfulness_feedback: bool, feedback_text: Optional[str] = None) -> MessageFeedbackORM:
        """
        Create feedback for an AI response.
        
        Args:
            user_id: The user ID (for authorization)
            ai_response_id: The AI response ID to provide feedback for
            helpfulness_feedback: Whether the feedback is positive (True) or negative (False)
            feedback_text: Optional text feedback
            
        Returns:
            MessageFeedbackORM: The created feedback object
        """
        return create_message_feedback(user_id, ai_response_id, helpfulness_feedback, feedback_text)
    
    def _error_stream(self, error_message: str) -> AsyncGenerator[str, None]:
        """Generate error stream for SSE"""
        async def stream():
            event = self.create_stream_error_event(error_message)
            yield event
        return stream()
    
    async def _validate_organization_quota(
        self,
        user_id: UUID,
        user_sub: str,
        check_quota: bool = True,
    ) -> Tuple[Optional[StreamingResponse], Optional[OrganizationsORM]]:
        """
        Fetch the user's organization, and (when check_quota=True) gate on
        organizations.question_quota vs questions_used.

        Agent mode passes check_quota=False — agent mode is gated solely by
        per-user agent_quota in _validate_agent_quota. The org is still
        fetched because downstream code needs user_org.access_level for RAG
        channel selection and user_org.id for tracing.
        See docs/rocportal-quota-strategy.md.

        Args:
            user_id: User's UUID
            user_sub: User's subscription ID
            check_quota: If True (ask mode), gate on org-level quota. If False
                (agent mode), only fetch the org without gating.

        Returns:
            Tuple of (error_response, organization). Error response if quota
            exceeded (when checked) or org not found, None if valid.
            Organization object is returned for successful validation.
        """
        try:
            user_org = get_organization_by_user_id(user_id=user_id)

            if check_quota and user_org.question_quota <= user_org.questions_used:
                logger.warning(f"Quota limit exceeded for user {user_sub}")
                return (StreamingResponse(
                    self._error_stream(f"You have reached your question quota. It will be reset at the end of the month."),
                    media_type="text/event-stream",
                    status_code=status.HTTP_400_BAD_REQUEST
                ), None)

            return (None, user_org)
            
        except Exception as e:
            logger.warning(f"Unable to find organization for user {user_sub}: {e}")
            return (StreamingResponse(
                self._error_stream("Unable to find user organization."),
                media_type="text/event-stream",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ), None)
    
    async def _validate_agent_quota(self, user_id: UUID, user_sub: str) -> Optional[StreamingResponse]:
        """
        Validate user's agent mode quota.
        
        Args:
            user_id: User's UUID
            user_sub: User's subscription ID
            
        Returns:
            StreamingResponse with error if quota exceeded, None if valid.
        """
        try:
            user = get_user_by_id(user_id=user_id)
            
            if not user:
                logger.warning(f"User not found for agent quota validation: {user_sub}")
                return StreamingResponse(
                    self._error_stream("User not found."),
                    media_type="text/event-stream",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            
            if user.agent_quota_used >= user.agent_quota:
                logger.warning(f"Agent quota exhausted for user {user_sub}: {user.agent_quota_used}/{user.agent_quota}")
                return StreamingResponse(
                    self._error_stream("You have used all your agent mode requests."),
                    media_type="text/event-stream",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating agent quota for user {user_sub}: {e}")
            return StreamingResponse(
                self._error_stream("Unable to validate agent quota."),
                media_type="text/event-stream",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    
    def _validate_source_selections(self, source_selections: List[str], user_sub: str) -> Optional[StreamingResponse]:
        """
        Validate source selections against allowed sources.
        
        Args:
            source_selections: List of selected knowledge sources
            user_sub: User's subscription ID (for logging)
            
        Returns:
            StreamingResponse with error if invalid sources found, None if all valid
        """
        try:
            for source in source_selections:
                if source not in SOURCE_SELECTIONS:
                    logger.warning(f"Invalid source selection '{source}' provided by user {user_sub}")
                    return StreamingResponse(
                        self._error_stream(f"Invalid source selection '{source}'. Valid options are: {', '.join(SOURCE_SELECTIONS)}"),
                        media_type="text/event-stream",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            return None
        except Exception as e:
            logger.error(f"Error validating source selections for user {user_sub}: {e}")
            return StreamingResponse(
                self._error_stream("Error validating source selections."),
                media_type="text/event-stream",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    

    
        
    def sse_event(self, event_type: str, data: dict) -> str:
        """Create SSE event with event type and data"""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    def create_user_init_event(self, client_temp_id: str, server_id: str, conversation_id: str) -> str:
        """Create user_message.init event"""
        event = UserMessageInitEvent(
            client_temp_id=client_temp_id,
            server_id=server_id,
            conversation_id=conversation_id
        )
        return self.sse_event("user_message.init", event.dict())
    
    def create_stream_error_event(self, error: str, assistant_server_id: Optional[str] = None) -> str:
        """Create stream.error event"""
        event = StreamErrorEvent(
            error=error,
            assistant_server_id=assistant_server_id
        )
        return self.sse_event("stream.error", event.dict())
    
    async def create_streaming_chat_message(
        self,
        session_id: UUID,
        prompt: str,
        source_selections: List[str],
        user_sub: str,
        user_email: str,
        user_id: UUID,
        client_temp_id: str,
        idempotency_key: str,
        model_name: str,
        is_agent_mode: bool = False,
        device_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        reasoning_level: Optional[str] = None
    ) -> StreamingResponse:
        """
        Stream a chat response as Server-Sent Events (SSE), validating quotas and sources, creating the conversation records, and proxying events from the AI core to the client.
        
        Parameters:
            session_id (UUID): Chat session identifier.
            prompt (str): The user's message text.
            source_selections (List[str]): Selected knowledge/source channels to use for retrieval.
            user_sub (str): User subject/identifier from authentication.
            user_email (str): User's email address from authentication.
            user_id (UUID): User database identifier.
            client_temp_id (str): Client-generated temporary message ID used to reconcile client-side messages with server-side records.
            idempotency_key (str): Key to deduplicate/retry the same request without creating duplicate records.
            model_name (str): Name of the model to invoke for generation.
            is_agent_mode (bool): When true, enable agent/tool execution events and agent-style streaming behavior.
            device_id (Optional[str]): Optional device identifier associated with the request.
            provider_name (Optional[str]): Optional AI provider name to route the request (e.g., 'anthropic/claude-sonnet-4-5').
            reasoning_level (Optional[str]): Optional reasoning level or chain-of-thought configuration for the model.
        
        Returns:
            StreamingResponse: An SSE streaming response that yields AI-core events (e.g., text deltas, completion, tool execution events) and ensures the final AI response record is saved with an appropriate status (COMPLETED, CANCELLED, or ERRORED).
        """
        try:
            # Decoupled quota gating:
            #  - Ask mode is gated only on organizations.question_quota
            #  - Agent mode is gated only on users.agent_quota
            # The org is still fetched in both modes because downstream code
            # needs user_org.access_level for RAG channel selection and
            # user_org.id for tracing — but org quota is not checked in agent
            # mode.
            # See docs/rocportal-quota-strategy.md.
            quota_error, user_org = await self._validate_organization_quota(
                user_id, user_sub, check_quota=not is_agent_mode,
            )
            if quota_error:
                return quota_error

            if is_agent_mode:
                agent_quota_error = await self._validate_agent_quota(user_id, user_sub)
                if agent_quota_error:
                    return agent_quota_error
            
            # Validate source selections
            source_error = self._validate_source_selections(source_selections, user_sub)
            if source_error:
                return source_error
            
            # Atomically create user and assistant message pair
            try:
                user_message, ai_response = create_atomic_message_pair(
                    session_id=session_id,
                    user_prompt=prompt,
                    sources_requested=source_selections,
                    idempotency_key=idempotency_key,
                    client_temp_id=client_temp_id,
                    model_name=model_name,
                    is_agent_mode=is_agent_mode,
                    device_id=device_id,
                    reasoning_level=reasoning_level
                )
            except Exception as e:
                logger.error(f"Failed to create atomic message pair: {e}")
                return StreamingResponse(
                    self._error_stream("Failed to initialize messages."),
                    media_type="text/event-stream",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create and return successful stream
            async def sse_stream():
                """
                Asynchronously consumes SSE-like chunks from the AI core, yields Server-Sent Event (SSE) strings for the client, accumulates the assistant's text output, and persists the AI response state when the stream ends.

                This generator:
                - Proxies allowed AI core events to the frontend as SSE-formatted strings.
                - Accumulates incremental text from `response.output_text.delta` and embeds tool markers for agent tool events.
                - Increments organization question usage when an agent run or response completes.
                - Coalesces streaming events into timeline blocks for efficient storage.
                - On stream termination (successful completion, client cancellation, or error) saves or updates the AI response with a final status:
                  - `COMPLETED` when the stream finished successfully,
                  - `CANCELLED` when the client cancelled the stream,
                  - `ERRORED` on other failures.
                - Handles asyncio.CancelledError as a client-initiated cancellation and still attempts to persist partial content.

                Returns:
                    An async generator that yields SSE-formatted event strings to stream to the client.
                """
                full_response_text = ""
                stream_start_time = None
                stream_successful = False
                stream_cancelled = False  # NEW: Track if stream was cancelled by user
                stream_started = False  # Track if we actually started receiving data from ai-core
                assistant_server_id = str(ai_response.id)
                buffer = ""
                captured_search_results = [] # NEW: Track search results as they are captured
                all_search_results = []  # Initialize early to prevent UnboundLocalError in exception handling
                trace_id = None  # NEW: Track trace_id for multi-agent workflows

                # Initialize timeline coalescer for block-based storage
                coalescer = TimelineCoalescer()
                
                # Define allowed events for multi-agent workflow
                # Note: We only support multi-agent workflow in agent mode
                # Unified allowed_events for both ask and agent modes
                # Both modes now use the same AI-Core agent endpoint
                # NOTE: "response.created" is NOT in this list because we emit our own
                # response.created event with the database ID (see above)
                allowed_events = {
                    # Search results event
                    "response.search_results",
                    
                    # Workflow lifecycle events
                    "agent.workflow.started",           # Workflow initialization with trace_id
                    "agent.workflow.status_changed",    # Status updates (classifying, planning, executing, etc.)
                    "agent.workflow.completed",         # Workflow completion with trace_id
                    "agent.workflow.failed",            # Workflow failure with error details
                    
                    # Agent communication events
                    "agent.transition",                 # Agent transitions (e.g., Orchestrator → Research Agent)
                    "agent.message.delta",              # Agent message text deltas (main output)
                    "agent.message.done",               # Agent message completion
                    
                    # Agent thinking/reasoning events
                    "agent.thinking",                   # Reasoning text from agents (deltas and complete)
                    "agent.text_output",                # Text output from agents (deltas) - legacy
                    
                    # Planning and execution events (agent mode only, but harmless for ask mode)
                    "agent.planning",                   # Plan creation from High-Level Planner
                    "agent.task_progress",              # Task execution progress updates
                    
                    # Tool execution events (agent mode only, but harmless for ask mode)
                    "agent.tool_execution.started",     # Tool execution started
                    "agent.tool_execution.completed",   # Tool execution completed with results
                    "agent.tool_execution.failed",      # Tool execution failed with error
                    
                    # Legacy run events (for compatibility)
                    "agent.run.completed",              # Run completion
                    "agent.run.failed",                 # Run failure
                    
                    # Context management events
                    "context.usage",                    # Token usage updates
                    "context.summarizing",              # Summarization/pruning in progress
                    "context.pruning_completed",        # Context pruning completed
                    "context.pruning_error",            # Summarization/pruning failed
                    
                    # Connection keepalive events
                    "agent.heartbeat",                  # Keepalive during long operations (tool execution)
                    
                    # Special cases
                    "agent.out_of_scope"                # Request is out of scope
                }
                
                # Track tool names for completion events (tool_call_id -> tool_name)
                tool_names = {}
                
                try:
                    # Send user message init event
                    yield self.create_user_init_event(
                        client_temp_id=client_temp_id,
                        server_id=str(user_message.id),
                        conversation_id=str(session_id)
                    )
                    
                    # Send AI response created event with database ID so frontend can submit feedback
                    # Note: Frontend only uses 'id' and 'sequence_number', but we include all fields
                    # to match the ResponseCreatedEvent interface for full type compatibility
                    response_created_event = {
                        "response": {
                            "id": str(ai_response.id),  # Database ID for feedback
                            "created_at": int(time.time() * 1000),  # Timestamp in milliseconds
                            "model": model_name,
                            "provider": provider_name or "unknown",
                            "status": "streaming"
                        },
                        "sequence_number": 0
                    }
                    yield self.sse_event("response.created", response_created_event)
                    
                    stream_start_time = time.time()
                    stream_started = True  # Mark that we've started streaming
                    
                    # Get stream from AI core (unified endpoint for both modes)
                    # mode="agent" for full tools + device control
                    # mode="ask" for knowledge retrieval only
                    agent_mode = "agent" if is_agent_mode else "ask"
                    ai_stream = ai_core_client.stream_agent_completion(
                        input=prompt,
                            session_id=str(session_id),
                        mode=agent_mode,
                        device_id=device_id if is_agent_mode else None,
                            provider=provider_name,
                            model=model_name,
                            user_permission=user_org.access_level,
                            source_channels=source_selections,
                        reasoning_effort=reasoning_level,
                        )
                    
                    # Stream events from AI core, parsing SSE format
                    async for chunk in ai_stream:
                        if not chunk:
                            continue
                        
                        buffer += chunk
                        
                        # Process complete SSE events (events end with \n\n)
                        while "\n\n" in buffer:
                            event_end = buffer.index("\n\n")
                            raw_event = buffer[:event_end]
                            buffer = buffer[event_end + 2:]
                            
                            if not raw_event.strip():
                                continue
                            
                            # Parse SSE event
                            lines = raw_event.split("\n")
                            event_type = ""
                            event_data = ""
                            
                            for line in lines:
                                if line.startswith("event:"):
                                    event_type = line[6:].strip()
                                elif line.startswith("data:"):
                                    event_data = line[5:].strip()
                            
                            if not event_type or not event_data:
                                continue
                            
                            try:
                                data = json.loads(event_data)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse event data: {event_data}")
                                continue
                            
                            # Filter out events not in allowed list
                            if event_type not in allowed_events:
                                continue

                            # Process event through coalescer for timeline storage
                            event_for_coalescer = {
                                'type': event_type,
                                'data': data,
                                'timestamp': time.time() * 1000
                            }
                            coalescer.process_event(event_for_coalescer)

                            # === Multi-Agent Workflow Event Handlers ===
                            
                            # Handle response.output_text.delta - for non-agent mode
                            if event_type == "response.output_text.delta":
                                delta_text = data.get("delta", "")
                                full_response_text += delta_text
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle response.completed - for non-agent mode (ask mode)
                            elif event_type == "response.completed":
                                # For ask mode, increment organization quota
                                increment_organization_questions_used(user_org.id)
                                stream_successful = True
                                logger.info(f"Stream completed successfully for session {session_id}")
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle response.failed - for non-agent mode
                            elif event_type == "response.failed":
                                logger.error(f"AI stream failed: {data.get('error', 'Unknown error')}")
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.tool_execution.started
                            elif event_type == "agent.tool_execution.started":
                                tool_call_id = data.get("tool_call_id", "unknown")
                                tool_name = data.get("tool_name", "unknown")
                                tool_args = data.get("tool_args", {})
                                
                                # Store tool name for tracking
                                tool_names[tool_call_id] = tool_name
                                
                                logger.debug(f"Tool execution started: {tool_name}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.tool_execution.completed
                            elif event_type == "agent.tool_execution.completed":
                                tool_call_id = data.get("tool_call_id", "unknown")
                                tool_name = data.get("tool_name", "unknown")
                                
                                logger.debug(f"Tool execution completed: {tool_name}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.tool_execution.failed
                            elif event_type == "agent.tool_execution.failed":
                                tool_call_id = data.get("tool_call_id", "unknown")
                                tool_name = data.get("tool_name", "unknown")
                                error = data.get("error", "Unknown error")
                                
                                logger.error(f"Tool execution failed: {tool_name} - {error}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.workflow.started - capture trace_id
                            elif event_type == "agent.workflow.started":
                                trace_id = data.get("trace_id")
                                logger.info(f"Multi-agent workflow started with trace_id: {trace_id}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.workflow.completed - capture trace_id, usage_breakdown, total_tokens, and mark complete
                            elif event_type == "agent.workflow.completed":
                                if not trace_id:
                                    trace_id = data.get("trace_id")
                                # Capture usage_breakdown if available (NEW in openai-agents v0.5.0)
                                usage_breakdown = data.get("usage_breakdown")
                                if usage_breakdown:
                                    logger.info(f"Captured usage_breakdown with {len(usage_breakdown)} request(s) for trace_id: {trace_id}")
                                # Capture total_tokens (cumulative tokens for the response)
                                total_tokens = data.get("total_tokens")
                                if total_tokens:
                                    logger.info(f"Captured total_tokens: {total_tokens} for trace_id: {trace_id}")
                                # Increment the appropriate quota based on mode
                                if is_agent_mode:
                                    increment_user_agent_quota_used(user_id)
                                    logger.info(f"Incremented agent quota used for user {user_id}")
                                else:
                                    increment_organization_questions_used(user_org.id)
                                stream_successful = True
                                logger.info(f"Multi-agent workflow completed with trace_id: {trace_id}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.workflow.failed - capture trace_id and mark as error
                            elif event_type == "agent.workflow.failed":
                                if not trace_id:
                                    trace_id = data.get("trace_id")
                                error = data.get("error", "Unknown error")
                                logger.error(f"Multi-agent workflow failed with trace_id: {trace_id} - {error}")
                                # Don't mark as successful, but don't cancel either - error will be handled in finally block
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.run.completed - legacy compatibility
                            elif event_type == "agent.run.completed":
                                logger.info(f"Agent run completed for session {session_id}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.run.failed - legacy compatibility
                            elif event_type == "agent.run.failed":
                                error = data.get("error", "Unknown error")
                                logger.error(f"Agent run failed: {error}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle search results events - proxy to frontend AND save to database
                            elif event_type == "response.search_results":
                                search_results = data.get("search_results", [])
                                if search_results:
                                    captured_search_results.extend(search_results)
                                    logger.info(f"Captured {len(search_results)} search results for response {ai_response.id}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.text_output - accumulate text deltas from multi-agent workflow
                            elif event_type == "agent.text_output":
                                delta_text = data.get("text", "")
                                is_complete = data.get("is_complete", False)
                                
                                # Only accumulate if not complete (deltas)
                                if not is_complete and delta_text:
                                    full_response_text += delta_text
                                
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.out_of_scope - mark as completed (valid response)
                            elif event_type == "agent.out_of_scope":
                                reason = data.get("reason", "Request is out of scope")
                                full_response_text = f"I can only assist with Rocscience and geotechnical engineering topics. {reason}"
                                stream_successful = True
                                logger.info(f"Request marked as out of scope for session {session_id}")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.planning - plan created by High-Level Planner
                            elif event_type == "agent.planning":
                                plan = data.get("plan", {})
                                num_tasks = len(plan.get("tasks", []))
                                logger.info(f"Plan created with {num_tasks} tasks for session {session_id}")
                                # Proxy full plan to frontend for display
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.task_progress - task execution updates
                            elif event_type == "agent.task_progress":
                                task_id = data.get("task_id", 0)
                                task_status = data.get("status", "unknown")
                                current_idx = data.get("current_task_index", 0)
                                total_tasks = data.get("total_tasks", 0)
                                logger.debug(f"Task {task_id} status: {task_status} ({current_idx + 1}/{total_tasks})")
                                # Proxy task progress to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.message.delta - main output from orchestrator (NEW)
                            elif event_type == "agent.message.delta":
                                delta_text = data.get("delta", "")
                                agent_name = data.get("agent_name", "Orchestrator")
                                
                                # Accumulate the delta text
                                if delta_text:
                                    full_response_text += delta_text
                                    logger.debug(f"{agent_name} message delta: {len(delta_text)} chars")
                                
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.message.done - message completion (NEW)
                            elif event_type == "agent.message.done":
                                agent_name = data.get("agent_name", "Agent")
                                logger.debug(f"{agent_name} message done")
                                # Proxy event to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.transition - agent transitions (NEW)
                            elif event_type == "agent.transition":
                                from_agent = data.get("from_agent", "Unknown")
                                to_agent = data.get("to_agent", "Unknown")
                                tool_name = data.get("tool_name", "")
                                logger.debug(f"Agent transition: {from_agent} → {to_agent} (via {tool_name})")
                                # Proxy event to frontend for display
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.thinking - reasoning/thinking steps
                            elif event_type == "agent.thinking":
                                agent_name = data.get("agent_name", "Agent")
                                is_complete = data.get("is_complete", False)
                                logger.debug(f"{agent_name} thinking event (complete: {is_complete})")
                                # Proxy thinking to frontend for display
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.workflow.status_changed - workflow status updates
                            elif event_type == "agent.workflow.status_changed":
                                status = data.get("status", "unknown")
                                agent_name = data.get("agent_name", "Agent")
                                logger.debug(f"Workflow status changed: {status} ({agent_name})")
                                # Proxy status change to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle context.usage - token usage updates (NEW)
                            elif event_type == "context.usage":
                                usage_type = data.get("type")
                                total_tokens = data.get("total_tokens", 0)
                                logger.debug(f"Context usage update: {total_tokens} tokens")
                                
                                # Update session's current_token_count in database
                                try:
                                    update_session_token_count(session_id, total_tokens)
                                except Exception as e:
                                    logger.error(f"Error updating token count for session {session_id}: {e}")
                                
                                # Forward to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle context.summarizing - summarization started
                            elif event_type == "context.summarizing":
                                logger.info(f"Context summarization started for session {session_id}")
                                # Forward to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle context.pruning_completed - summarization completed
                            elif event_type == "context.pruning_completed":
                                logger.info(f"Context summarization completed for session {session_id}")
                                # Forward to frontend (SDK session handles persistence)
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle context.pruning_error - summarization failed
                            elif event_type == "context.pruning_error":
                                logger.error(f"Context summarization failed for session {session_id}: {data.get('error')}")
                                # Forward to frontend
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle agent.heartbeat - keepalive during long operations
                            elif event_type == "agent.heartbeat":
                                # Heartbeats keep the SSE connection alive during long tool executions
                                # Just proxy to frontend, no special processing needed
                                logger.debug(f"Heartbeat for session {session_id}")
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                            
                            # Handle any other allowed events - proxy to frontend
                            else:
                                # Catch-all for any other allowed events
                                yield f"event: {event_type}\ndata: {event_data}\n\n"
                    
                
                except asyncio.CancelledError:
                    # Client disconnected (user clicked stop button)
                    logger.info(f"Stream cancelled by client for session {session_id}")
                    stream_cancelled = True
                    # Don't re-raise, we want to save partial content in finally block
                    
                except Exception as e:
                    logger.error(f"Error during streaming: {e}")
                    # Keep stream_cancelled = False, this is an error not a cancellation
                    
                    # Send stream.error event to frontend so it can handle the error
                    error_message = str(e)
                    
                    yield self.create_stream_error_event(error_message, assistant_server_id)
                    
                finally:
                    # Handle message saving based on whether streaming started and if we got content
                    if stream_started and full_response_text.strip():
                        # We got content - save it
                        try:
                            response_time_ms = int((time.time() - stream_start_time) * 1000) if stream_start_time else None
                            final_text = full_response_text.strip()

                            # Extract URLs from response text (simple regex, no validation)
                            import re
                            
                            # Extract URLs from markdown links and plain text
                            url_pattern = r'https?://[^\s\)\]>]+'
                            extracted_urls = list(set(re.findall(url_pattern, final_text)))
                            
                            extracted_search_results = [
                                {
                                    "url": url,
                                    "title": url.split("/")[-1] if url.split("/")[-1] else url,
                                    "source": "extracted_from_response"
                                }
                                for url in extracted_urls
                            ]
                            
                            logger.info(f"Extracted {len(extracted_urls)} URLs from response text")

                            # Merge with Perplexity search results if any
                            all_search_results = captured_search_results if captured_search_results else []
                            all_search_results.extend(extracted_search_results)

                            # Determine final status based on what happened
                            if stream_successful:
                                final_status = MessageStatus.COMPLETED
                            elif stream_cancelled:
                                final_status = MessageStatus.CANCELLED
                            else:
                                final_status = MessageStatus.ERRORED
                            
                            # Get final coalesced timeline
                            final_timeline = coalescer.get_timeline(is_cancelled=(final_status == MessageStatus.CANCELLED))

                            # Save to database with appropriate status
                            update_ai_response_status(
                                ai_response_id=ai_response.id,
                                status=final_status,
                                message_text=final_text,
                                response_time_ms=response_time_ms,
                                search_results=all_search_results if all_search_results else None,
                                trace_id=trace_id,  # Include trace_id if available
                                timeline=final_timeline if final_timeline['blocks'] else None,
                                usage_breakdown=usage_breakdown if 'usage_breakdown' in locals() else None,  # Per-request usage breakdown
                                token_count=total_tokens if 'total_tokens' in locals() else None  # Total cumulative tokens
                            )

                            # Trigger media extraction based on search results URLs
                            if all_search_results and len(all_search_results) > 0:
                                try:
                                    # Extract URLs from search results
                                    search_urls = [result.get('url') for result in all_search_results if result.get('url')]
                                    if search_urls:
                                        logger.info(f"Extracting media from search result URLs: {search_urls} for response {ai_response.id}")

                                        # Send media search start event
                                        yield self.sse_event("media.search_start", {"server_id": str(ai_response.id)})

                                        # Extract media asynchronously from the actual URLs used in search
                                        media_data = await extract_media_from_urls(search_urls)

                                    # Update media links in database
                                    update_ai_response_media_links(ai_response.id, media_data)

                                    # Send media search completed event
                                    yield self.sse_event("media.search_completed", {"server_id": str(ai_response.id), "media_data": media_data})

                                    logger.info(f"Extracted media for response {ai_response.id}: {len(media_data.get('images', []))} images, {len(media_data.get('videos', []))} videos")
                                except Exception as e:
                                    logger.error(f"Failed to extract media for response {ai_response.id}: {e}")

                            trace_log = f" with trace_id: {trace_id}" if trace_id else ""
                            logger.info(f"Saved partial message with status {final_status.value}{trace_log} for session {session_id}")
                        except Exception as e:
                            logger.error(f"Failed to save partial message: {e}")
                    else:
                        # No content to save, just mark status
                        # This happens when: 1) stream was cancelled before content, 2) error before content (e.g. device not connected)
                        try:
                            final_status = MessageStatus.CANCELLED if stream_cancelled else MessageStatus.ERRORED
                            # Get final coalesced timeline even for empty responses
                            final_timeline = coalescer.get_timeline(is_cancelled=(final_status == MessageStatus.CANCELLED))

                            update_ai_response_status(
                                ai_response_id=ai_response.id,
                                status=final_status,
                                trace_id=trace_id,  # Include trace_id if available
                                timeline=final_timeline if final_timeline['blocks'] else None
                            )

                            trace_log = f" with trace_id: {trace_id}" if trace_id else ""
                            logger.info(f"Set status to {final_status.value} (no content){trace_log} for session {session_id}")
                        except Exception as e:
                            logger.error(f"Failed to update message status: {e}")

            return StreamingResponse(
                sse_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Content-Encoding": "none",
                }
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in streaming chat service for user {user_sub}: {e}")
            return StreamingResponse(
                self._error_stream("Internal server error occurred."),
                media_type="text/event-stream",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    def create_message_feedback(self, user_id: UUID, ai_response_id: UUID, helpfulness_feedback: bool, feedback_text: Optional[str] = None) -> MessageFeedbackORM:
        """Create message feedback"""

        return create_message_feedback(user_id, ai_response_id, helpfulness_feedback, feedback_text)