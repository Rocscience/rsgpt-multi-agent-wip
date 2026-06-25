from app.db_models.feedback import (
    MessageFeedbackORM
)
from typing import Optional
from uuid import UUID
import logging
from app.db_models.connection import Session

logger = logging.getLogger(__name__)

def create_message_feedback(user_id: UUID, ai_response_id: UUID, helpfulness_feedback: bool, feedback_text: Optional[str] = None) -> MessageFeedbackORM:
    """Create message feedback for an AI response"""
    try:
        with Session() as session:
            # Verify the AI response exists and belongs to a session owned by the user
            from app.db_models.chats import AIResponsesORM, ChatSessionsORM
            
            ai_response = session.query(AIResponsesORM).join(
                ChatSessionsORM, AIResponsesORM.session_id == ChatSessionsORM.id
            ).filter(
                AIResponsesORM.id == ai_response_id,
                ChatSessionsORM.user_id == user_id,
                AIResponsesORM.deleted_at.is_(None),
                ChatSessionsORM.deleted_at.is_(None)
            ).first()
            
            if not ai_response:
                raise ValueError(f"AI response {ai_response_id} not found or not accessible to user {user_id}")
            
            message_feedback = MessageFeedbackORM(
                user_id=user_id,
                ai_response_id=ai_response_id,
                feedback_type="positive" if helpfulness_feedback else "negative",
                feedback_text=feedback_text,
                feedback_score=1 if helpfulness_feedback else 0
            )
            session.add(message_feedback)
            session.commit()
            session.refresh(message_feedback)
            session.expunge(message_feedback)
            return message_feedback
    except Exception as e:
        logger.error(f"Error occured while trying to create the message feedback for user: {user_id} and AI response: {ai_response_id}")
        raise e