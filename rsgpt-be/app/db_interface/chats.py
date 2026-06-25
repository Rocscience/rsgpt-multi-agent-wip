"""Database interface for chat-related operations"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc

from app.db_models.chats import (
    AIResponsesORM,
    ChatSessionsORM,
    MessageStatus,
    UserMessagesORM,
)
from app.db_models.connection import Session
from app.services.timeline_coalescer import TimelineCoalescer

logger = logging.getLogger(__name__)

def create_chat_session(title: Optional[str], user_id: UUID) -> ChatSessionsORM:
    """Create a new chat session"""
    try:
        with Session() as session:
            new_chat = ChatSessionsORM(
                user_id=user_id,
                title=title,
                is_active=True,
                message_count=0
            )
            session.add(new_chat)
            session.commit()
            session.refresh(new_chat)
            session.expunge(new_chat)
            return new_chat
    except Exception as e:
        logger.error(f"Error occured while trying to create the chat session for user: {user_id}")
        raise e
    
def delete_chat_session(session_id: UUID, user_id: UUID) -> ChatSessionsORM:
    """Soft deletes a chat session"""
    try:
        with Session() as session:
            chat_session = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id,
                ChatSessionsORM.user_id == user_id,
                ChatSessionsORM.deleted_at.is_(None)
            ).first()

            if not chat_session:
                raise ValueError(f"Chat session {session_id} for user {user_id} not found or already deleted")
            
            chat_session.deleted_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(chat_session)
            session.expunge(chat_session)

            return chat_session
    except Exception as e:
        logger.error(f"Error occured while trying to soft delete chat session: {session_id}")
        raise e

def get_chat_session(session_id: UUID, user_id: UUID) -> ChatSessionsORM:
    """Get the chat session from ID"""
    try:
        with Session() as session:
            chat_session = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id,
                ChatSessionsORM.user_id == user_id,
                ChatSessionsORM.deleted_at.is_(None)
            ).first()

            if chat_session:
                session.expunge(chat_session)
                return chat_session
            else:
                logger.info(f"No chat session found with the matching id: {session_id}")
                return None
    except Exception as e:
        logger.error(f"Error occured, trying to obtain chat session with id: {session_id}")
        raise e

def get_list_of_chat_sessions(
    user_id: UUID, 
    page: int = 1, 
    page_size: int = 20,
) -> tuple[List[ChatSessionsORM], int]:
    """Get paginated list of chat sessions"""
    try:
        with Session() as session:
            # Base query
            base_query = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.user_id == user_id,
                ChatSessionsORM.deleted_at.is_(None)
            )
            
            # Get total count (before pagination)
            total_count = base_query.count()
            
            # Apply ordering and pagination
            offset = (page - 1) * page_size
            chat_sessions = base_query.order_by(
                ChatSessionsORM.created_at.desc()  # Most recent first
            ).offset(offset).limit(page_size).all()
            
            for chat_session in chat_sessions:
                session.expunge(chat_session)
            return chat_sessions, total_count
    except Exception as e:
        logger.error(f"Error obtaining paginated chat sessions for user: {user_id}")
        raise e

def create_user_message(
        session_id: UUID,
        message_text: str,
        sources_requested: list[str],
        idempotency_key: str,
        client_temp_id: str,
        status: MessageStatus = MessageStatus.SUBMITTED
    ) -> UserMessagesORM:
    """Create new user message with simple retry logic"""
    try:
        with Session() as session:
            # Check for existing message with same idempotency key
            existing_message = session.query(UserMessagesORM).filter(
                UserMessagesORM.idempotency_key == idempotency_key
            ).first()
            
            if existing_message:
                logger.info(f"Found existing user message with idempotency key: {idempotency_key}")
                session.expunge(existing_message)
                return existing_message

            new_user_message = UserMessagesORM(
                session_id=session_id,
                message_text=message_text,
                sources_requested=sources_requested,
                status=status,
                idempotency_key=idempotency_key,
                client_temp_id=client_temp_id
            )

            session.add(new_user_message)

            # Update the session message count
            chat_session = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id
            ).first()
            
            if chat_session:
                chat_session.message_count += 1

            session.commit()
            session.refresh(new_user_message)
            session.expunge(new_user_message)

            return new_user_message

    except Exception as e:
        logger.error(f"Error creating user message in chat session: {session_id}")
        raise e


def create_ai_response(
        user_message_id: UUID,
        session_id: UUID,
        message_text: str = "",
        status: MessageStatus = MessageStatus.STREAMING,
        response_time_ms: Optional[int] = None,
        sources_used: Optional[list[str]] = None,
        token_count: Optional[int] = None,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        reasoning_level: Optional[str] = None,
        timeline: Optional[dict] = None,
        usage_breakdown: Optional[list[dict]] = None
    ) -> AIResponsesORM:
    """Create new AI response"""
    try:
        with Session() as session:
            new_ai_response = AIResponsesORM(
                user_message_id=user_message_id,
                session_id=session_id,
                message_text=message_text,
                status=status,
                response_time_ms=response_time_ms,
                sources_used=sources_used or [],
                token_count=token_count,
                run_id=run_id,
                trace_id=trace_id,
                reasoning_level=reasoning_level,
                timeline=timeline,
                usage_breakdown=usage_breakdown
            )

            session.add(new_ai_response)

            # Update the session message count
            chat_session = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id
            ).first()
            
            if chat_session:
                chat_session.message_count += 1

            session.commit()
            session.refresh(new_ai_response)
            session.expunge(new_ai_response)

            return new_ai_response

    except Exception as e:
        logger.error(f"Error creating AI response for user message: {user_message_id}")
        raise e


def create_atomic_message_pair(
        session_id: UUID,
        user_prompt: str,
        sources_requested: list[str],
        idempotency_key: str,
        client_temp_id: str,
        model_name: str,
        is_agent_mode: bool = False,
        device_id: Optional[str] = None,
        reasoning_level: Optional[str] = None
    ) -> tuple[UserMessagesORM, AIResponsesORM]:
    """
    Atomically create user and assistant message pair for hybrid init-in-stream.
    Returns (user_message, ai_response)
    """
    try:
        with Session() as session:
            # Check for existing user message with same idempotency key
            existing_user_msg = session.query(UserMessagesORM).filter(
                UserMessagesORM.idempotency_key == idempotency_key
            ).first()
            
            if existing_user_msg:
                # Find corresponding AI response
                existing_ai_response = session.query(AIResponsesORM).filter(
                    AIResponsesORM.user_message_id == existing_user_msg.id
                ).order_by(AIResponsesORM.created_at.desc()).first()
                
                if not existing_ai_response:
                    # Create AI response if it doesn't exist (recovery scenario)
                    existing_ai_response = AIResponsesORM(
                        user_message_id=existing_user_msg.id,
                        session_id=session_id,
                        message_text="",
                        status=MessageStatus.STREAMING,
                        sources_used=sources_requested,
                        model_used=model_name,
                        is_agent_mode=is_agent_mode,
                        device_id=device_id,
                        reasoning_level=reasoning_level
                    )
                    session.add(existing_ai_response)
                    session.commit()
                    session.refresh(existing_ai_response)
                
                # Load all attributes while session is active
                _ = existing_user_msg.id, existing_user_msg.created_at, existing_user_msg.message_text
                _ = existing_ai_response.id, existing_ai_response.created_at, existing_ai_response.message_text, existing_ai_response.status
                
                # Detach objects from session
                session.expunge(existing_user_msg)
                session.expunge(existing_ai_response)
                
                return existing_user_msg, existing_ai_response

            # Create user message FIRST
            user_message = UserMessagesORM(
                session_id=session_id,
                message_text=user_prompt,
                sources_requested=sources_requested,
                status=MessageStatus.SUBMITTED,
                idempotency_key=idempotency_key,
                client_temp_id=client_temp_id,
                model_requested=model_name,
                device_id=device_id
            )

            session.add(user_message)
            
            # Update the session message count for user message
            chat_session = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id
            ).first()
            
            if chat_session:
                chat_session.message_count += 1

            # Commit user message first to ensure ordering
            session.commit()
            session.refresh(user_message)

            # Now create AI response shell AFTER user message is committed
            ai_response = AIResponsesORM(
                user_message_id=user_message.id,
                session_id=session_id,
                message_text="",
                status=MessageStatus.STREAMING,
                sources_used=sources_requested,
                model_used=model_name,
                is_agent_mode=is_agent_mode,
                device_id=device_id,
                reasoning_level=reasoning_level
            )

            session.add(ai_response)
            
            # Update session message count for AI response
            if chat_session:
                chat_session.message_count += 1

            # Commit AI response
            session.commit()
            session.refresh(ai_response)
            
            # Make sure all attributes are loaded while session is active
            _ = user_message.id, user_message.created_at, user_message.message_text
            _ = ai_response.id, ai_response.created_at, ai_response.message_text, ai_response.status
            
            # Detach objects from session so they can be used outside session context
            session.expunge(user_message)
            session.expunge(ai_response)

            return user_message, ai_response

    except Exception as e:
        logger.error(f"Error creating atomic message pair in chat session: {session_id}")
        raise e


def retry_user_message(user_message_id: UUID) -> AIResponsesORM:
    """Retry a user message by creating new AI response"""
    try:
        with Session() as session:
            user_msg = session.query(UserMessagesORM).filter(
                UserMessagesORM.id == user_message_id
            ).first()
            
            if not user_msg:
                raise ValueError(f"User message {user_message_id} not found")
                
            # Create new AI response for retry
            return create_ai_response(user_message_id, user_msg.session_id)
            
    except Exception as e:
        logger.error(f"Error retrying user message: {user_message_id}")
        raise e


def update_ai_response_status(
        ai_response_id: UUID,
        status: MessageStatus,
        message_text: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        token_count: Optional[int] = None,
        run_id: Optional[str] = None,
        search_results: Optional[list[dict]] = None,
        trace_id: Optional[str] = None,
        timeline: Optional[dict] = None,
        usage_breakdown: Optional[list[dict]] = None
    ) -> AIResponsesORM:
    """Update AI response status and optionally text, response time, token count, run ID, search results, trace ID, and timeline"""
    try:
        with Session() as session:
            ai_response = session.query(AIResponsesORM).filter(
                AIResponsesORM.id == ai_response_id
            ).first()
            
            if not ai_response:
                raise ValueError(f"AI response {ai_response_id} not found")
            
            ai_response.status = status
            if message_text is not None:
                ai_response.message_text = message_text
            if response_time_ms is not None:
                ai_response.response_time_ms = response_time_ms
            if token_count is not None:
                ai_response.token_count = token_count
            if run_id is not None:
                ai_response.run_id = run_id
            if search_results is not None:
                ai_response.search_results = search_results
            if trace_id is not None:
                ai_response.trace_id = trace_id
            if timeline is not None:
                ai_response.timeline = timeline
            elif timeline is None and status == MessageStatus.COMPLETED and message_text and message_text.strip():
                # Create a basic timeline for regular AI responses that don't have streaming events
                ai_response.timeline = TimelineCoalescer.create_basic_timeline(message_text)
            if usage_breakdown is not None:
                ai_response.usage_breakdown = usage_breakdown

            session.commit()
            session.refresh(ai_response)
            session.expunge(ai_response)
            
            return ai_response

    except Exception as e:
        logger.error(f"Error updating AI response status for message: {ai_response_id}")
        raise e

def update_ai_response_media_links(ai_response_id: UUID, media_links: list[str]) -> AIResponsesORM:
    """Update AI response media links"""
    try:
        with Session() as session:
            ai_response = session.query(AIResponsesORM).filter(
                AIResponsesORM.id == ai_response_id
            ).first()
            
            if not ai_response:
                raise ValueError(f"AI response {ai_response_id} not found")
            
            ai_response.media_links = media_links
            session.commit()
            session.refresh(ai_response)
            session.expunge(ai_response)
            
            return ai_response

    except Exception as e:
        logger.error(f"Error updating AI response media links for message: {ai_response_id}")
        raise e

def update_user_message_status(user_message_id: UUID, status: MessageStatus) -> UserMessagesORM:
    """Update user message status"""
    try:
        with Session() as session:
            user_message = session.query(UserMessagesORM).filter(
                UserMessagesORM.id == user_message_id
            ).first()
            
            if not user_message:
                raise ValueError(f"User message {user_message_id} not found")
            
            user_message.status = status
            session.commit()
            session.refresh(user_message)
            session.expunge(user_message)
            
            return user_message

    except Exception as e:
        logger.error(f"Error updating user message status for message: {user_message_id}")
        raise e
    
def get_user_messages_for_session(session_id: UUID) -> List[UserMessagesORM]:
    """Get all user messages for a session (for building chat history)"""
    try:
        with Session() as session:
            messages = session.query(UserMessagesORM).filter(
                UserMessagesORM.session_id == session_id,
                UserMessagesORM.deleted_at.is_(None)
            ).order_by(UserMessagesORM.created_at.asc()).all()
            for message in messages:
                session.expunge(message)
            return messages
    except Exception as e:
        logger.error(f"Error getting user messages for session: {session_id}")
        raise e


def get_ai_responses_for_session(session_id: UUID) -> List[AIResponsesORM]:
    """Get all AI responses for a session (for building chat history)"""
    try:
        with Session() as session:
            responses = session.query(AIResponsesORM).filter(
                AIResponsesORM.session_id == session_id,
                AIResponsesORM.deleted_at.is_(None)
            ).order_by(AIResponsesORM.created_at.asc()).all()
            for response in responses:
                session.expunge(response)
            return responses
    except Exception as e:
        logger.error(f"Error getting AI responses for session: {session_id}")
        raise e


def get_conversation_history_for_user(user_id: UUID, session_id: UUID, page: int = 1, page_size: int = 10) -> tuple[List[UserMessagesORM], int]:
    """
    Get user messages with their AI responses for a specific user and session.
    Uses efficient queries with eager loading to minimize database calls.
    
    Args:
        user_id: The user ID (for authorization)
        session_id: The chat session UUID
        page: Page number for pagination
        page_size: Number of conversation turns per page
        
    Returns:
        tuple[List[UserMessagesORM], int]: List of user messages with loaded AI responses and total count
    """
    try:
        with Session() as session:
            # First verify the session belongs to the user
            session_check = session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id,
                ChatSessionsORM.user_id == user_id,
                ChatSessionsORM.deleted_at.is_(None)
            ).first()
            
            if not session_check:
                raise ValueError(f"Session {session_id} not found or not accessible to user {user_id}")
            
            # Get total count of user messages for pagination
            total_count = session.query(UserMessagesORM).filter(
                UserMessagesORM.session_id == session_id,
                UserMessagesORM.deleted_at.is_(None)
            ).count()
            
            # Get user messages with pagination
            offset = (page - 1) * page_size
            user_messages = session.query(UserMessagesORM).filter(
                UserMessagesORM.session_id == session_id,
                UserMessagesORM.deleted_at.is_(None)
            ).order_by(UserMessagesORM.created_at.desc()).offset(offset).limit(page_size).all()
            
            # Get all user message IDs for this page
            user_message_ids = [msg.id for msg in user_messages]
            
            # Efficiently get ALL AI responses for these user messages in one query
            ai_responses = session.query(AIResponsesORM).filter(
                AIResponsesORM.user_message_id.in_(user_message_ids),
                AIResponsesORM.deleted_at.is_(None)
            ).order_by(AIResponsesORM.user_message_id, AIResponsesORM.created_at.desc()).all()
            
            # Group AI responses by user_message_id for efficient lookup
            responses_by_user_msg = {}
            for resp in ai_responses:
                if resp.user_message_id not in responses_by_user_msg:
                    responses_by_user_msg[resp.user_message_id] = []
                responses_by_user_msg[resp.user_message_id].append(resp)
            
            # Attach AI responses to user messages and expunge all objects
            for user_msg in user_messages:
                user_msg.ai_responses_list = responses_by_user_msg.get(user_msg.id, [])
                session.expunge(user_msg)
            
            for resp in ai_responses:
                session.expunge(resp)
            
            return user_messages, total_count
            
    except Exception as e:
        logger.error(f"Error getting conversation history for user {user_id}, session: {session_id}")
        raise e


def update_ai_response_media_links(ai_response_id: UUID, media_links: dict) -> None:
    """Update the media_links field for an AI response"""
    try:
        with Session() as session:
            ai_response = session.query(AIResponsesORM).filter(
                AIResponsesORM.id == ai_response_id,
                AIResponsesORM.deleted_at.is_(None)
            ).first()
            
            if not ai_response:
                raise ValueError(f"AI response {ai_response_id} not found")
            
            ai_response.media_links = media_links
            session.commit()
            
            logger.info(f"Updated media links for AI response {ai_response_id}")
            
    except Exception as e:
        logger.error(f"Error updating media links for AI response {ai_response_id}: {e}")
        raise e


def update_session_token_count(session_id: UUID, token_count: int) -> None:
    """
    Update the current token count for a chat session.
    
    Args:
        session_id: The chat session UUID
        token_count: The new token count
    """
    try:
        with Session() as session:
            session.query(ChatSessionsORM).filter(
                ChatSessionsORM.id == session_id
            ).update({"current_token_count": token_count})
            session.commit()
            
    except Exception as e:
        logger.error(f"Error updating token count for session {session_id}: {e}")
        raise e
