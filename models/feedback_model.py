from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

class FeedbackCreate(BaseModel):
    """Model for creating feedback"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    feedback_type: Literal['bug', 'feature', 'general', 'complaint'] = 'general'
    rating: Optional[int] = Field(None, ge=1, le=5)
    message: str = Field(..., min_length=10, max_length=5000)
    page_url: Optional[str] = None

class FeedbackResponse(BaseModel):
    """Model for feedback response"""
    id: UUID
    user_id: Optional[UUID] = None
    name: Optional[str] = None
    email: Optional[str] = None
    feedback_type: str
    rating: Optional[int] = None
    message: str
    page_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FeedbackUpdate(BaseModel):
    """Model for updating feedback status"""
    status: Literal['new', 'reviewed', 'resolved']
