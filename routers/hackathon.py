from fastapi import APIRouter, Body, HTTPException, Depends
from fastapi.responses import JSONResponse
from supabase_client_async import async_supabase
from models.api_models import CreateUserProfilePayload
from utils.api_responses import APIResponse
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hackathon",
    tags=["Hackathon"]
)


class HackathonRegistration:
    """Pydantic model for hackathon registration"""
    def __init__(self, **data):
        self.__dict__.update(data)


@router.post("/register")
async def register_for_hackathon(
    provider_id: str = Body(...),
    full_name: str = Body(...),
    email: str = Body(...),
    college_name: str = Body(...),
    phone_number: Optional[str] = Body(None),
    college_email: Optional[str] = Body(None),
    major: Optional[str] = Body(None),
    graduation_year: Optional[int] = Body(None),
    linkedin_profile: Optional[str] = Body(None),
    github_profile: Optional[str] = Body(None),
    team_name: Optional[str] = Body(None),
    team_member_emails: Optional[List[str]] = Body(None),
    skills: Optional[List[str]] = Body(None),
    idea_summary: Optional[str] = Body(None),
    experience_level: Optional[str] = Body("Beginner"),
    dietary_restrictions: Optional[str] = Body(None),
) -> JSONResponse:
    """
    Register a user for the Agenticverse Hackathon.
    
    Parameters:
    - provider_id: User's provider ID (from ChatVerse auth)
    - full_name: Full name of participant
    - email: Email address
    - college_name: Name of college/university
    - Optional fields: phone, team info, skills, etc.
    """
    try:
        # Validate that user exists
        user_check = await async_supabase.select(
            "user_profiles",
            select="provider_id",
            filters={"provider_id": provider_id},
            limit=1
        )
        
        if not user_check["data"]:
            return APIResponse.error(404, "User profile not found. Please sign up first.")
        
        # Prepare registration data
        registration_data = {
            "provider_id": provider_id,
            "full_name": full_name,
            "email": email,
            "college_name": college_name,
            "phone_number": phone_number,
            "college_email": college_email,
            "major": major,
            "graduation_year": graduation_year,
            "linkedin_profile": linkedin_profile,
            "github_profile": github_profile,
            "team_name": team_name,
            "team_member_emails": team_member_emails or [],
            "skills": skills or [],
            "idea_summary": idea_summary,
            "experience_level": experience_level,
            "dietary_restrictions": dietary_restrictions,
            "registration_status": "confirmed"
        }
        
        # Check if user already registered
        existing = await async_supabase.select(
            "hackathon_registrations",
            select="registration_id",
            filters={"provider_id": provider_id},
            limit=1
        )
        
        if existing["data"]:
            # Update existing registration
            response = await async_supabase.update(
                "hackathon_registrations",
                registration_data,
                {"provider_id": provider_id}
            )
            
            if response["error"]:
                logger.error(f"Error updating hackathon registration: {response['error']}")
                return APIResponse.error(500, "Failed to update registration")
            
            return APIResponse.success(
                data=response["data"][0],
                message="Registration updated successfully!"
            )
        else:
            # Create new registration
            response = await async_supabase.insert(
                "hackathon_registrations",
                registration_data
            )
            
            if response["error"]:
                logger.error(f"Error creating hackathon registration: {response['error']}")
                return APIResponse.error(500, f"Failed to create registration: {response['error']}")
            
            if not response["data"]:
                return APIResponse.error(500, "No data returned from registration")
            
            return APIResponse.success(
                data=response["data"][0],
                message="Registration successful! Welcome to Agenticverse Hackathon 🚀"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in hackathon registration: {str(e)}")
        return APIResponse.error(500, str(e))


@router.get("/registration-status/{provider_id}")
async def get_registration_status(provider_id: str) -> JSONResponse:
    """
    Get the hackathon registration status for a user.
    
    Returns:
    - registered: boolean - whether user is registered
    - registration_data: dict - registration details if registered
    """
    try:
        response = await async_supabase.select(
            "hackathon_registrations",
            filters={"provider_id": provider_id},
            limit=1
        )
        
        if response["error"]:
            logger.error(f"Error fetching registration: {response['error']}")
            return APIResponse.error(500, response["error"])
        
        if response["data"]:
            return APIResponse.success(
                data={
                    "registered": True,
                    "registration": response["data"][0]
                }
            )
        else:
            return APIResponse.success(
                data={
                    "registered": False,
                    "registration": None
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in get_registration_status: {str(e)}")
        return APIResponse.error(500, str(e))


@router.get("/registrations")
async def get_all_registrations(limit: int = 100, offset: int = 0) -> JSONResponse:
    """
    Get all hackathon registrations (admin endpoint).
    
    Parameters:
    - limit: Maximum number of records to return
    - offset: Number of records to skip
    """
    try:
        response = await async_supabase.select(
            "hackathon_registrations",
            limit=limit,
            offset=offset
        )
        
        if response["error"]:
            logger.error(f"Error fetching registrations: {response['error']}")
            return APIResponse.error(500, response["error"])
        
        # Get total count
        count_response = await async_supabase.query(
            "select count(*) as total from hackathon_registrations"
        )
        
        total = count_response["data"][0]["total"] if count_response["data"] else 0
        
        return APIResponse.success(
            data={
                "registrations": response["data"],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in get_all_registrations: {str(e)}")
        return APIResponse.error(500, str(e))


@router.delete("/registration/{provider_id}")
async def cancel_registration(provider_id: str) -> JSONResponse:
    """
    Cancel a hackathon registration.
    """
    try:
        response = await async_supabase.update(
            "hackathon_registrations",
            {"registration_status": "cancelled"},
            {"provider_id": provider_id}
        )
        
        if response["error"]:
            logger.error(f"Error cancelling registration: {response['error']}")
            return APIResponse.error(500, response["error"])
        
        if not response["data"]:
            return APIResponse.error(404, "Registration not found")
        
        return APIResponse.success(
            data=response["data"][0],
            message="Registration cancelled successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in cancel_registration: {str(e)}")
        return APIResponse.error(500, str(e))
