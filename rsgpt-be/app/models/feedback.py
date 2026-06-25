from typing import Optional
from pydantic import BaseModel, Field

class CreateMessageFeedbackRequest(BaseModel):
    """Request model for creating message feedback"""
    helpfulness_feedback: bool = Field(..., description="Helpfulness feedback")
    feedback_text: Optional[str] = Field(None, description="Feedback text")

class CreateMessageFeedbackResponse(BaseModel):
    """Response model for creating message feedback"""
    is_success: bool = Field(..., description="Whether the message feedback was created successfully")
    message: Optional[str] = Field(None, description="Optional message explaining the status")