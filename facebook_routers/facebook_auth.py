from fastapi import APIRouter, HTTPException, Request
from supabase_client import supabase
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta, timezone
from config import (
    FACEBOOK_CLIENT_ID,
    FACEBOOK_CLIENT_SECRET,
    FACEBOOK_REDIRECT_URI,
    FRONTEND_PLATFORM_URL
)
from config.oauth_config import get_platform_scopes
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth/facebook",
    tags=["facebook_auth"]
)

# Get Facebook scopes from centralized config
FACEBOOK_SCOPES = get_platform_scopes("facebook")

async def get_facebook_profile(access_token: str):
    """Get Facebook profile information"""
    profile_url = f"https://graph.facebook.com/v23.0/me?fields=id,name&access_token={access_token}"
    async with httpx.AsyncClient() as client:
        response = await client.get(profile_url)
        response.raise_for_status()
        profile_data = response.json()

        return {
            "facebook_user_id": profile_data.get("id"),
            "facebook_name": profile_data.get("name")
        }

def upsert_facebook(provider_id: str, long_lived_token: str, expires_in_seconds: int, 
                    facebook_user_id: str, facebook_name: str, granted_scopes: list):
    """Store Facebook connection in database with granted scopes"""
    token_expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    current_time = datetime.now(timezone.utc).isoformat()

    # Delete existing record if any
    supabase.table("connected_accounts")\
        .delete()\
        .eq("provider_id", provider_id)\
        .eq("platform", "facebook")\
        .execute()

    # Insert new record with scopes as array
    account_data = {
        "provider_id": provider_id,
        "platform": "facebook",
        "platform_user_id": facebook_user_id,
        "platform_username": facebook_name,
        "scopes": granted_scopes,  # Store as array
        "access_token": long_lived_token,
        "token_expires_at": token_expiry_time.isoformat(),
        "connected": True,
        "connected_at": current_time,
        "updated_at": current_time,
    }

    result = supabase.table("connected_accounts").insert(account_data).execute()
    logger.info(f"Facebook OAuth successful for user {provider_id}, scopes: {granted_scopes}")
    return result


@router.get("/login")
def facebook_login(user_id: str, return_url: str = None):
    """Redirect user to Facebook OAuth consent screen"""
    # Use centralized scopes configuration
    scope_string = ",".join(FACEBOOK_SCOPES)
    
    # Combine user_id and return_url into the state parameter
    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"

    auth_url = (
        f"https://www.facebook.com/v23.0/dialog/oauth"
        f"?client_id={FACEBOOK_CLIENT_ID}"
        f"&redirect_uri={FACEBOOK_REDIRECT_URI}"
        f"&scope={scope_string}"
        f"&response_type=code&state={state_value}"
    )
    logger.info(f"Redirecting to Facebook auth URL for user_id: {user_id}")
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def facebook_oauth_callback(request: Request, code: str = "", state: str = ""):
    """Handle Facebook OAuth callback and exchange code for long-lived token"""
    # Set a default redirect URL in case the state is malformed
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None

    logger.info(f"Facebook callback received with state: {state}")

    # Parse the state to get user_id and the original return_url
    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state

    if not code or not user_id:
        logger.error("Missing code or user_id in Facebook callback")
        return RedirectResponse(url=f"{return_url}?error=authorization_failed")
    
    logger.info(f"Facebook OAuth callback for user: {user_id}, return URL: {return_url}")

    print("\n\n\n", code, user_id, return_url, "\n\n\n")

    async with httpx.AsyncClient() as client:
        # Step 1: Exchange authorization code for a short-lived access token
        token_url = "https://graph.facebook.com/v23.0/oauth/access_token"
        params = {
            "client_id": FACEBOOK_CLIENT_ID,
            "client_secret": FACEBOOK_CLIENT_SECRET,
            "redirect_uri": FACEBOOK_REDIRECT_URI,
            "code": code,
        }

        print("\n\n\n params : ", params, "\n\n\n")
        short_lived_token_response = await client.get(token_url, params=params)
        print("\n\n\n short lived token : ", short_lived_token_response.text, "\n\n\n")
        short_lived_token_response.raise_for_status()
        short_lived_token_data = short_lived_token_response.json()

        if "access_token" not in short_lived_token_data:
            raise HTTPException(status_code=400, detail="Short-lived access token not found.")

        short_lived_token = short_lived_token_data["access_token"]
        print("\n\n\n short_lived_token accessed : ", short_lived_token, "\n\n\n")

        # Step 2: Exchange for a long-lived token (60 days)
        long_lived_url = "https://graph.facebook.com/v23.0/oauth/access_token"
        long_lived_params = {
            "grant_type": "fb_exchange_token",
            "client_id": FACEBOOK_CLIENT_ID,
            "client_secret": FACEBOOK_CLIENT_SECRET,
            "fb_exchange_token": short_lived_token,
        }
        print("\n\n\n params for long lived token : ", long_lived_params, "\n\n\n")
        long_lived_token_response = await client.get(long_lived_url, params=long_lived_params)
        print("\n\n\n long lived token response : ", long_lived_token_response.text, "\n\n\n")
        long_lived_token_response.raise_for_status()
        long_lived_token_data = long_lived_token_response.json()
        print("\n\n\n long lived token data : ", long_lived_token_data, "\n\n\n")
        
        long_lived_token = long_lived_token_data.get("access_token")
        expires_in_seconds = long_lived_token_data.get("expires_in", 5184000)  # Default 60 days

        print("\n\n\n long_lived_token : ", long_lived_token, " expires_in_seconds: ", expires_in_seconds, "\n\n\n")

        # Step 3: Get profile info and save to database
        profile_data = await get_facebook_profile(long_lived_token)
        
        # Store with scopes as array
        upsert_facebook(
            user_id, 
            long_lived_token, 
            expires_in_seconds, 
            profile_data['facebook_user_id'], 
            profile_data['facebook_name'],
            FACEBOOK_SCOPES  # Pass scopes as array
        )

        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=facebook"

        return RedirectResponse(url=final_redirect_url)
