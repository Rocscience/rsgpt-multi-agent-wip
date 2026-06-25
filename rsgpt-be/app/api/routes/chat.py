from fastapi import APIRouter, Request, Path, HTTPException, Query, Body, status, Depends
from fastapi.responses import StreamingResponse
from uuid import UUID
import logging
import re
from typing import Dict, Any, Optional
from app.models.chats import (
    CreateChatSessionRequest,
    CreateChatSessionResponse,
    GetChatSessionMetaResponse,
    GetChatSessionsListResponse,
    GetConversationHistoryResponse,
    ConversationTurnDto,
    UserMessageDto,
    AIResponseDto,
    RetryUserPromptResponse,
    StreamPromptRequest,
)
from app.models.feedback import (
    CreateMessageFeedbackRequest,
    CreateMessageFeedbackResponse
)
from app.models.system import DeleteResponse
from app.services.chat_service import ChatService
from app.dependencies import get_current_user
from app.models.enums import (
    ProviderEnum,
    PROVIDER_MODELS,
    AGENT_MODE_PROVIDERS
)


logger = logging.getLogger(__name__)

chat_router = APIRouter()

"""
    This route allows a client to create a chat session,
    and optionally passing in a title field
    @param request: Request
    @return: JSON response with the rocportal status
"""
@chat_router.post("/sessions", response_model=CreateChatSessionResponse)
async def create_chat_session(
    chat_data: CreateChatSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]
    # Strip @[filepath] patterns from title to make it user-friendly
    raw_title = chat_data.title or ""
    clean_title = re.sub(r'@\[[^\]]+\]', '', raw_title).strip()
    title = clean_title[:255] if clean_title else "New Chat"

    try:
        chat_service = ChatService()

        chat_session_obj = chat_service.create_chat_session(
            user_id=user_id,
            title=title
        )

        return CreateChatSessionResponse(
            id=chat_session_obj.id,
            user_id=user_id,
            title=chat_session_obj.title,
            message_count=chat_session_obj.message_count
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e)})
    except Exception as e:
        logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This route allows a client to submit a chat message,
    and recieve a streamed response back
    @param request: Request
    @param request_body: StreamPromptRequest
    @return: StreamedResponse
"""
@chat_router.post("/sessions/stream/{session_id}")
async def create_chat_message(
    request_body: StreamPromptRequest = Body(...),
    session_id: UUID = Path(..., description="Chat Session ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a streaming chat message in the specified session.
    Follows the clean service pattern used by other endpoints.
    """
    try:
        chat_service = ChatService()

        # Check if chat session exists
        chat_session_obj = chat_service.get_chat_session(session_id, current_user["user_id"])
        if chat_session_obj is None:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Chat session {session_id} not found"}
            )

        # Validate provider
        if not request_body.provider_name:
            raise HTTPException(
                status_code=400,
                detail={"message": "Provider name is required"}
            )
        
        try:
            provider = ProviderEnum(request_body.provider_name)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Invalid provider: {request_body.provider_name}. Must be one of: {', '.join([p.value for p in ProviderEnum])}"}
            )
        
        # Validate model for the given provider
        if request_body.model_name not in PROVIDER_MODELS[provider]:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Invalid model '{request_body.model_name}' for provider '{provider.value}'. Valid models: {', '.join(PROVIDER_MODELS[provider])}"}
            )
        
        # Validate provider is allowed in agent mode
        if request_body.is_agent_mode and provider not in AGENT_MODE_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail={"message": f"Provider '{provider.value}' is not supported in agent mode. Supported providers: {', '.join([p.value for p in AGENT_MODE_PROVIDERS])}"}
            )
        
        return await chat_service.create_streaming_chat_message(
            session_id=session_id,
            prompt=request_body.prompt,
            source_selections=request_body.source_selections,
            user_sub=current_user["user_sub"],
            user_email=current_user["user_email"],
            user_id=current_user["user_id"],
            client_temp_id=request_body.client_temp_id,
            idempotency_key=request_body.idempotency_key,
            model_name=request_body.model_name,
            is_agent_mode=request_body.is_agent_mode,
            device_id=request_body.device_id,
            provider_name=request_body.provider_name,
            reasoning_level=request_body.reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in streaming chat endpoint: {e}")
        async def error_stream():
            yield f"event: stream.error\ndata: {{\"error\": \"Internal server error occurred.\"}}\n\n"
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

"""
    This route allows a client to get a paginated list of chat sessions.
    For RSinsight FE, they should rely on has_next to know when the infinite
    scroller needs to stop
    @param request: Request
    @query page: int
    @page_size: int
    @return: GetChatSessionsListResponse
"""
@chat_router.get("/sessions", response_model=GetChatSessionsListResponse)
async def get_list_of_sessions(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    try:
        chat_service = ChatService()
        list_of_chat_sessions, total_count = chat_service.get_list_chat_sessions(
            user_id, page, page_size
        )
        
        # Transform sessions
        sessions = [
            GetChatSessionMetaResponse(
                user_id=session.user_id,
                chat_session_id=session.id,
                title=session.title,
                message_count=session.message_count,
                created_at=session.created_at,
                updated_at=session.updated_at
            )
            for session in list_of_chat_sessions
        ]
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        
        return GetChatSessionsListResponse(
            sessions=sessions,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e)})
    except Exception as e:
        logger.error(f"Error getting chat sessions: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This route allows a client to get the chat session metadata
    @param request: Request
    @param session_id: UUID
    @return: result
"""
@chat_router.get("/sessions/{session_id}", response_model=GetChatSessionMetaResponse)
async def get_session_details(
    session_id: UUID = Path(..., description="Chat Session ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    try:
        chat_service = ChatService()

        chat_session_obj = chat_service.get_chat_session(session_id, user_id)
        
        # Check if chat session exists
        if chat_session_obj is None:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Chat session {session_id} not found"}
            )

        return GetChatSessionMetaResponse(
            user_id=user_id,
            chat_session_id=chat_session_obj.id,
            title=chat_session_obj.title,
            message_count=chat_session_obj.message_count,
            created_at=chat_session_obj.created_at,
            updated_at=chat_session_obj.updated_at
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e)})
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})


"""
    This route allows a client to soft delete a chat session
    @param request: Request
    @param session_id: UUID
    @return: result
"""
@chat_router.delete("/sessions/{session_id}", response_model=DeleteResponse)
async def delete_chat_session(
    session_id: UUID = Path(..., description="Chat Session ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    try:
        chat_service = ChatService()

        # Check if chat session exists
        chat_session_obj = chat_service.get_chat_session(session_id, user_id)
        if chat_session_obj is None:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Chat session {session_id} not found"}
            )

        chat_service.delete_chat_session(
            chat_session_id=session_id,
            user_id=user_id
        )

        return DeleteResponse(message="Chat session deleted successfully")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e)})
    except Exception as e:
        logger.error(f"Error trying to delete the chat session: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This route allows a client to get the hierarchical conversation history for a session (paginated)
    Each conversation turn contains a user message and all its AI responses (including retries)
    @param request: Request
    @param session_id: UUID
    @return: result
"""
@chat_router.get("/sessions/conversation/{session_id}", response_model=GetConversationHistoryResponse)
async def get_conversation_history(
    session_id: UUID = Path(..., description="Chat Session ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get hierarchical conversation history where each turn contains a user message 
    and all its AI responses (including retries).
    """
    try:
        chat_service = ChatService()

        # Check if chat session exists
        chat_session_obj = chat_service.get_chat_session(session_id, current_user["user_id"])
        if chat_session_obj is None:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Chat session {session_id} not found"}
            )
        
        conversation, total_count = chat_service.get_conversation_history(
            user_id=current_user["user_id"],
            session_id=session_id,
            page=page,
            page_size=page_size
        )

        total_pages = (total_count + page_size - 1) // page_size

        return GetConversationHistoryResponse(
            conversation=conversation,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
            current_token_count=chat_session_obj.current_token_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This route allows a client to retry a user prompt by creating a new AI response
    @param user_message_id: UUID - The ID of the user message to retry
    @return: RetryUserPromptResponse
"""
@chat_router.post("/sessions/retry/{user_message_id}", response_model=RetryUserPromptResponse)
async def retry_user_prompt(
    user_message_id: UUID = Path(..., description="User Message ID to retry"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retry a user prompt by creating a new AI response.
    This creates a new AI response for an existing user message.
    """
    try:
        chat_service = ChatService()
        
        # Create new AI response for the existing user message
        new_ai_response = chat_service.retry_user_prompt(user_message_id)
        
        return RetryUserPromptResponse(
            success=True,
            ai_response_id=new_ai_response.id,
            user_message_id=new_ai_response.user_message_id,
            status=new_ai_response.status.value,
            message="Retry initiated successfully"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"message": f"User message not found: {str(e)}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying user prompt: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})

"""
    This route allows a client to create message feedback
    @param request: Request
    @return: CreateMessageFeedbackResponse
"""
@chat_router.post("/sessions/feedback/{ai_response_id}", response_model=CreateMessageFeedbackResponse)
async def create_message_feedback(
    request_body: CreateMessageFeedbackRequest = Body(...),
    ai_response_id: UUID = Path(..., description="AI Response ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    try:
        chat_service = ChatService()
        chat_service.create_message_feedback(
            user_id=user_id,
            ai_response_id=ai_response_id,
            helpfulness_feedback=request_body.helpfulness_feedback,
            feedback_text=request_body.feedback_text
        )

        return CreateMessageFeedbackResponse(
            is_success=True,
            message="Message feedback created successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating message feedback: {e}")
        raise HTTPException(status_code=500, detail={"message": "Internal server error"})