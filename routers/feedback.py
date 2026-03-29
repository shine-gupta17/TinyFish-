"""
Feedback Router - Handles user feedback submissions
"""

from fastapi import APIRouter, HTTPException, status, Request
from typing import Optional
import logging
from supabase_client_async import async_supabase
from models.feedback_model import FeedbackCreate, FeedbackResponse, FeedbackUpdate
from services.email_service import email_service

logger = logging.getLogger(__name__)

feedback_router = APIRouter(
    prefix="/api/feedback",
    tags=["feedback"]
)

@feedback_router.post("/submit", response_model=dict)
async def submit_feedback(
    feedback: FeedbackCreate,
    request: Request,
    user_id: Optional[str] = None
):
    """
    Submit user feedback
    
    Args:
        feedback: Feedback data from user
        request: HTTP request object
        user_id: Optional authenticated user ID
    
    Returns:
        Success response with feedback ID
    """
    try:
        # Extract additional data
        page_url = feedback.page_url or request.headers.get("referer", "")
        user_agent = request.headers.get("user-agent", "")
        
        # Prepare feedback data
        feedback_data = {
            "name": feedback.name,
            "email": feedback.email,
            "feedback_type": feedback.feedback_type,
            "rating": feedback.rating,
            "message": feedback.message,
            "page_url": page_url,
            "user_agent": user_agent,
            "status": "new"
        }
        
        # If user is authenticated, add user_id
        if user_id:
            feedback_data["user_id"] = user_id
        
        # Insert into Supabase using async client
        db = await async_supabase.get_instance()
        response = await db.insert(table="feedback", data=feedback_data)
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to submit feedback"
            )
        
        if response.get("data"):
            feedback_id = response["data"][0]['id'] if isinstance(response["data"], list) else response["data"]['id']
            logger.info(f"Feedback submitted successfully. ID: {feedback_id}")
            
            # Send email notification to admin
            email_sent = email_service.send_feedback_email(
                user_name=feedback.name,
                user_email=feedback.email,
                feedback_type=feedback.feedback_type,
                rating=feedback.rating,
                message=feedback.message,
                page_url=page_url,
                feedback_id=str(feedback_id)
            )
            
            if email_sent:
                logger.info(f"Feedback email sent for ID: {feedback_id}")
            else:
                logger.warning(f"Failed to send email for feedback ID: {feedback_id}, but feedback was saved")
            
            return {
                "success": True,
                "message": "Thank you for your feedback!",
                "feedback_id": feedback_id,
                "email_sent": email_sent
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to submit feedback"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting feedback"
        )

@feedback_router.get("/user/{user_id}", response_model=list[FeedbackResponse])
async def get_user_feedback(user_id: str):
    """
    Get all feedback submitted by a specific user
    """
    try:
        db = await async_supabase.get_instance()
        response = await db.select(
            table="feedback",
            select="*",
            filters={"user_id": user_id},
            order="created_at.desc"
        )
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving feedback"
            )
        
        return response.get("data", [])
        
    except Exception as e:
        logger.error(f"Error retrieving user feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving feedback"
        )

@feedback_router.get("/", response_model=list[FeedbackResponse])
async def get_all_feedback():
    """
    Get all feedback (admin only)
    Note: Add authentication/authorization check if needed
    """
    try:
        db = await async_supabase.get_instance()
        response = await db.select(
            table="feedback",
            select="*",
            order="created_at.desc"
        )
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving feedback"
            )
        
        return response.get("data", [])
        
    except Exception as e:
        logger.error(f"Error retrieving feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving feedback"
        )

@feedback_router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(feedback_id: str):
    """
    Get specific feedback by ID
    """
    try:
        db = await async_supabase.get_instance()
        response = await db.select(
            table="feedback",
            select="*",
            filters={"id": feedback_id}
        )
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving feedback"
            )
        
        data = response.get("data", [])
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        return data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving feedback"
        )

@feedback_router.patch("/{feedback_id}", response_model=dict)
async def update_feedback_status(
    feedback_id: str,
    update_data: FeedbackUpdate
):
    """
    Update feedback status (admin only)
    """
    try:
        db = await async_supabase.get_instance()
        response = await db.update(
            table="feedback",
            data={"status": update_data.status},
            filters={"id": feedback_id}
        )
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating feedback"
            )
        
        if not response.get("data"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        logger.info(f"Feedback {feedback_id} status updated to {update_data.status}")
        return {
            "success": True,
            "message": "Feedback status updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating feedback"
        )

@feedback_router.delete("/{feedback_id}", response_model=dict)
async def delete_feedback(feedback_id: str):
    """
    Delete feedback by ID
    """
    try:
        db = await async_supabase.get_instance()
        response = await db.delete(
            table="feedback",
            filters={"id": feedback_id}
        )
        
        if response.get("error"):
            logger.error(f"Database error: {response['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting feedback"
            )
        
        logger.info(f"Feedback {feedback_id} deleted successfully")
        return {
            "success": True,
            "message": "Feedback deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error deleting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting feedback"
        )
