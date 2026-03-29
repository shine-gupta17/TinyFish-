from fastapi import APIRouter, HTTPException, Request
from supabase_client import supabase
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta, timezone
from config import (
    INSTAGRAM_CLIENT_ID,
    INSTAGRAM_CLIENT_SECRET,
    INSTAGRAM_REDIRECT_URI,
    FRONTEND_PLATFORM_URL
)
from config.oauth_config import get_platform_scopes
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth/instagram",
    tags=["insta_auth"]
)

# Get Instagram scopes from centralized config
INSTAGRAM_SCOPES = get_platform_scopes("instagram")

async def get_instagram_profile(access_token: str):
    """Get Instagram profile information"""
    profile_url = f"https://graph.instagram.com/v23.0/me?fields=id,user_id,username&access_token={access_token}"
    async with httpx.AsyncClient() as client:
        response = await client.get(profile_url)
        response.raise_for_status()
        profile_data = response.json()

        return {
            "insta_user_id": profile_data.get("user_id"),
            "insta_username": profile_data.get("username")
        }

async def upsert_instagram(provider_id: str, long_lived_token: str, expires_in_seconds: int, 
                     insta_user_id: str, insta_username: str, granted_scopes: list):
    """Store Instagram connection in database with granted scopes"""
    from supabase_client_async import async_supabase
    
    token_expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    current_time = datetime.now(timezone.utc).isoformat()

    # Delete existing record for this provider_id and platform
    await async_supabase.delete(
        "connected_accounts",
        {"provider_id": provider_id, "platform": "instagram"}
    )

    # Delete any existing record with the same platform_user_id linked to a different provider_id
    # This ensures the Instagram account can only be linked to one user at a time
    await async_supabase.delete(
        "connected_accounts",
        {"platform_user_id": insta_user_id, "platform": "instagram"}
    )
    logger.info(f"Removed any previous Instagram account links for platform_user_id: {insta_user_id}")

    # Insert new record with scopes as array
    account_data = {
        "provider_id": provider_id,
        "platform": "instagram",
        "platform_user_id": insta_user_id,
        "platform_username": insta_username,
        "scopes": granted_scopes,  # Store as array
        "access_token": long_lived_token,
        "token_expires_at": token_expiry_time.isoformat(),
        "connected": True,
        "connected_at": current_time,
        "updated_at": current_time,
    }

    result = await async_supabase.insert("connected_accounts", account_data)
    logger.info(f"Instagram OAuth successful for user {provider_id}, scopes: {granted_scopes}")
    return result


@router.get("/login")
def instagram_login(user_id: str, return_url: str = None):
    """Redirect user to Instagram OAuth consent screen"""
    # Use centralized scopes configuration
    scope_string = ",".join(INSTAGRAM_SCOPES)
    
    # Combine user_id and return_url into the state parameter
    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"

    auth_url = (
        f"https://api.instagram.com/oauth/authorize"
        f"?client_id={INSTAGRAM_CLIENT_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        f"&scope={scope_string}"
        f"&response_type=code&state={state_value}"
    )
    logger.info(f"Redirecting to Instagram auth URL for user_id: {user_id}")
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def instagram_oauth_callback(request: Request, code: str = "", state: str = ""):
    """Handle Instagram OAuth callback and exchange code for long-lived token"""
    # Set a default redirect URL in case the state is malformed
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None

    logger.info(f"Instagram callback received with state: {state}")

    # Parse the state to get user_id and the original return_url
    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state

    if not code or not user_id:
        logger.error("Missing code or user_id in Instagram callback")
        return RedirectResponse(url=f"{return_url}?error=authorization_failed")
    
    logger.info(f"Instagram OAuth callback - User: {user_id}, Code: {code[:10]}..., Return URL: {return_url}")

    async with httpx.AsyncClient() as client:
        # Step 1: Exchange authorization code for a short-lived access token
        token_url = "https://api.instagram.com/oauth/access_token"
        payload = {
            "client_id": INSTAGRAM_CLIENT_ID,
            "client_secret": INSTAGRAM_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "code": code,
        }

        logger.debug(f"Exchanging code for short-lived token - Payload: {payload}")
        short_lived_token_response = await client.post(token_url, data=payload)
        logger.debug(f"Short-lived token response: {short_lived_token_response.text}")
        short_lived_token_response.raise_for_status()
        short_lived_token_data = short_lived_token_response.json()

        if "access_token" not in short_lived_token_data:
            raise HTTPException(status_code=400, detail="Short-lived access token not found.")

        short_lived_token = short_lived_token_data["access_token"]
        logger.info(f"Short-lived token obtained successfully")

        # Step 2: Exchange for a long-lived token
        long_lived_url = "https://graph.instagram.com/access_token"
        params = {
            "grant_type": "ig_exchange_token",
            "client_secret": INSTAGRAM_CLIENT_SECRET,
            "access_token": short_lived_token,
        }
        logger.debug(f"Exchanging for long-lived token")
        long_lived_token_response = await client.get(long_lived_url, params=params)
        logger.debug(f"Long-lived token response: {long_lived_token_response.text}")
        long_lived_token_response.raise_for_status()
        long_lived_token_data = long_lived_token_response.json()
        logger.debug(f"Long-lived token data: {long_lived_token_data}")
        
        long_lived_token = long_lived_token_data.get("access_token")
        expires_in_seconds = long_lived_token_data.get("expires_in")

        logger.info(f"Long-lived token obtained - Expires in: {expires_in_seconds} seconds")

        # Step 3: Get profile info and save to database
        profile_data = await get_instagram_profile(long_lived_token)
        
        # Store with scopes as array
        await upsert_instagram(
            user_id, 
            long_lived_token, 
            expires_in_seconds, 
            profile_data['insta_user_id'], 
            profile_data['insta_username'],
            INSTAGRAM_SCOPES  # Pass scopes as array
        )
        
        # Step 4: Enable webhook subscriptions for this account
        try:
            webhook_fields = ["messages", "messaging_postbacks", "comments", "mentions"]
            webhook_url = f"https://graph.instagram.com/v23.0/{profile_data['insta_user_id']}/subscribed_apps"
            webhook_params = {
                "subscribed_fields": ",".join(webhook_fields),
                "access_token": long_lived_token
            }
            
            webhook_response = await client.post(webhook_url, params=webhook_params)
            webhook_response.raise_for_status()
            logger.info(f"Webhook subscription enabled for {profile_data['insta_user_id']}: {webhook_fields}")
        except Exception as webhook_error:
            logger.error(f"Failed to enable webhook subscription for {profile_data['insta_user_id']}: {webhook_error}")
            # Don't fail the OAuth flow if webhook subscription fails

        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=instagram"

        return RedirectResponse(url=final_redirect_url)
