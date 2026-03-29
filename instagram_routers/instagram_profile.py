"""
Instagram Profile Router
Handles Instagram profile data endpoints including profile picture.
"""

from fastapi import APIRouter, HTTPException
from supabase_client import supabase
import httpx
import logging
import asyncio
import json

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds

router = APIRouter(
    prefix="/instagram/profile",
    tags=["Instagram Profile"]
)


async def get_access_token(platform_user_id: str) -> str:
    """Get access token for Instagram account from database."""
    try:
        response = supabase.table("connected_accounts").select("access_token").eq(
            "platform_user_id", platform_user_id).eq(
            "platform", "instagram").eq(
            "connected", True).limit(1).maybe_single().execute()

        if not response.data or not response.data.get("access_token"):
            raise ValueError("Connected account or access token not found.")

        return response.data["access_token"]
    except Exception as e:
        logger.error(f"Error fetching access token for {platform_user_id}: {str(e)}")
        raise


async def _fetch_from_instagram_api(url: str, params: dict, retry_count: int = 0) -> dict:
    """
    Fetch data from Instagram Graph API with exponential backoff retry logic.
    
    Args:
        url: API endpoint URL
        params: Query parameters including access_token
        retry_count: Current retry attempt (internal)
        
    Returns:
        JSON response from Instagram API
        
    Raises:
        HTTPException for various error conditions
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            
            # Success case
            if response.status_code == 200:
                return response.json()
            
            # Try to parse error details
            try:
                error_data = response.json()
            except:
                error_data = {"message": "Failed to parse error response"}
            
            logger.warning(f"Instagram API returned {response.status_code}: {error_data}")
            
            # Handle transient errors with retry logic
            is_transient = error_data.get("error", {}).get("is_transient", False) if isinstance(error_data.get("error"), dict) else False
            
            if response.status_code in [500, 502, 503] or is_transient:
                if retry_count < MAX_RETRIES:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = min(INITIAL_RETRY_DELAY * (2 ** retry_count), MAX_RETRY_DELAY)
                    logger.info(f"Transient error (attempt {retry_count + 1}/{MAX_RETRIES}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    return await _fetch_from_instagram_api(url, params, retry_count + 1)
                else:
                    logger.error(f"Max retries ({MAX_RETRIES}) exceeded for transient error: {error_data}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Instagram service temporarily unavailable. Please try again in a few moments."
                    )
            
            # Handle 401/403 (auth errors - don't retry)
            if response.status_code in [401, 403]:
                error_msg = error_data.get("error", {}).get("message", "Authentication failed") if isinstance(error_data.get("error"), dict) else str(error_data)
                logger.error(f"Authentication error: {error_msg}")
                raise HTTPException(
                    status_code=401,
                    detail="Instagram authentication failed. Please reconnect your account."
                )
            
            # Handle other HTTP errors
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Instagram API error: {error_data}"
            )
            
    except httpx.TimeoutException:
        if retry_count < MAX_RETRIES:
            logger.warning(f"Timeout (attempt {retry_count + 1}/{MAX_RETRIES}). Retrying...")
            delay = min(INITIAL_RETRY_DELAY * (2 ** retry_count), MAX_RETRY_DELAY)
            await asyncio.sleep(delay)
            return await _fetch_from_instagram_api(url, params, retry_count + 1)
        else:
            logger.error(f"Max retries exceeded for timeout")
            raise HTTPException(
                status_code=504,
                detail="Instagram request timed out. Please try again."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Instagram API call: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/picture/{platform_user_id}")
async def get_profile_picture(platform_user_id: str):
    """
    Fetch Instagram profile picture URL for the given platform_user_id.
    
    Args:
        platform_user_id: Instagram Business Account ID
        
    Returns:
        JSON with profile_picture_url and username
    """
    try:
        access_token = await get_access_token(platform_user_id)
        
        if not platform_user_id or not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Missing platform_user_id or access_token"
            )
        
        # Fetch profile information including profile picture
        url = f"https://graph.instagram.com/v21.0/{platform_user_id}"
        params = {
            "fields": "id,username,profile_picture_url",
            "access_token": access_token
        }
        
        data = await _fetch_from_instagram_api(url, params)
        
        return {
            "success": True,
            "data": {
                "profile_picture_url": data.get("profile_picture_url"),
                "username": data.get("username"),
                "platform_user_id": data.get("id")
            }
        }
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Value error for {platform_user_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error fetching profile picture for {platform_user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/info/{platform_user_id}")
async def get_profile_info(platform_user_id: str):
    """
    Fetch complete Instagram profile information.
    
    Args:
        platform_user_id: Instagram Business Account ID
        
    Returns:
        JSON with complete profile data including username, followers, media count, bio, etc.
    """
    try:
        access_token = await get_access_token(platform_user_id)
        
        if not platform_user_id or not access_token:
            raise HTTPException(
                status_code=400,
                detail="Missing platform_user_id or access_token"
            )
        
        url = f"https://graph.instagram.com/v21.0/{platform_user_id}"
        params = {
            "fields": "id,username,name,profile_picture_url,followers_count,follows_count,media_count,biography,website",
            "access_token": access_token
        }
        
        data = await _fetch_from_instagram_api(url, params)
        
        return {
            "success": True,
            "data": data
        }
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Value error for {platform_user_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error fetching profile info for {platform_user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )
