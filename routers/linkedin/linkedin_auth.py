from fastapi import Request
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from supabase_client import supabase
import requests
import logging
import json
import urllib.parse
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
import os

router = APIRouter(
    prefix="/auth/linkedin",
    tags=["linkedin"]
)

logger = logging.getLogger(__name__)

# LinkedIn OAuth2 configuration
# You'll need to set these environment variables or create a linkedin.json file
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")

# LinkedIn OAuth2 scopes (Sign In with LinkedIn using OpenID Connect)
SCOPES = [
    "openid",          # OpenID Connect authentication
    "profile",         # Basic profile information
    "email",           # Email address
    "w_member_social"  # Share content on LinkedIn
]

REDIRECT_URI = f"{BACKEND_URL}/auth/linkedin/oauth2callback"


@router.get("/login")
def linkedin_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to LinkedIn OAuth2 consent screen"""
    
    if not LINKEDIN_CLIENT_ID:
        logger.error("LinkedIn Client ID not configured")
        return RedirectResponse(f"{FRONTEND_PLATFORM_URL}/platforms?error=linkedin_not_configured")
    
    # Build state parameter
    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"
    
    # Build LinkedIn authorization URL
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state_value,
        "scope": " ".join(SCOPES)
    }
    
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urllib.parse.urlencode(params)}"
    
    logger.info(f"Redirecting to LinkedIn auth URL for user_id: {user_id}")
    return RedirectResponse(auth_url)


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str, error: str = None) -> RedirectResponse:
    """Handle LinkedIn OAuth2 callback and save credentials to Supabase"""
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None

    # Parse state parameter
    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state

    # Handle OAuth errors
    if error:
        logger.error(f"LinkedIn OAuth error: {error}")
        return RedirectResponse(f"{return_url}?error=linkedin_auth_failed")

    if not code or not user_id:
        return RedirectResponse(f"{return_url}?error=authorization_failed")

    try:
        # Exchange authorization code for access token
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        token_info = token_response.json()
        
        access_token = token_info.get("access_token")
        expires_in = token_info.get("expires_in")  # Usually 60 days for LinkedIn
        
        if not access_token:
            logger.error("No access token received from LinkedIn")
            return RedirectResponse(f"{return_url}?error=token_exchange_failed")

        # Get user profile information using OpenID Connect userinfo endpoint
        userinfo_url = "https://api.linkedin.com/v2/userinfo"
        profile_headers = {"Authorization": f"Bearer {access_token}"}
        
        userinfo_response = requests.get(userinfo_url, headers=profile_headers)
        userinfo_response.raise_for_status()
        userinfo_data = userinfo_response.json()
        
        # Extract user information from userinfo (OpenID Connect standard)
        linkedin_id = userinfo_data.get("sub")  # Subject identifier (user ID)
        platform_username = userinfo_data.get("name", "")
        email_address = userinfo_data.get("email", "")
        
        # Store both userinfo and attempt to get extended profile
        profile_data = userinfo_data
        email_data = {"email": email_address}
        
        platform_user_id = linkedin_id
        
        logger.info(f"LinkedIn profile retrieved for user {user_id}: {platform_username} ({email_address})")
        
        # Log granted permissions
        logger.info("="*60)
        logger.info("🔐 LINKEDIN PERMISSIONS GRANTED BY USER")
        logger.info("="*60)
        logger.info(f"👤 User: {user_id}")
        logger.info(f"🔗 LinkedIn ID: {linkedin_id}")
        logger.info(f"👨‍💼 Name: {platform_username}")
        logger.info(f"📧 Email: {email_address}")
        logger.info("✅ Basic profile access")
        logger.info("✅ Email address access")
        logger.info("✅ Content sharing permissions")
        logger.info("="*60)

        # Store credentials in database
        credential_data = {
            "access_token": access_token,
            "expires_in": expires_in,
            "profile": profile_data,
            "email": email_data
        }

        try:
            supabase.table("connected_accounts").upsert({
                "provider_id": user_id,
                "platform": "linkedin",
                "platform_user_id": platform_user_id,
                "platform_username": platform_username,
                "scopes": SCOPES,
                "access_token": access_token,
                "refresh_token": None,  # LinkedIn doesn't provide refresh tokens
                "token_expires_at": None,  # We'll handle expiration differently
                "connected": True,
                "data": json.dumps(credential_data)
            }).execute()
            
            logger.info(f"LinkedIn account connected successfully for user {user_id}")
            
        except Exception as db_error:
            logger.error(f"Database error when storing LinkedIn connection: {db_error}")
            # Try to update existing record
            try:
                supabase.table("connected_accounts").update({
                    "provider_id": user_id,
                    "scopes": SCOPES,
                    "access_token": access_token,
                    "connected": True,
                    "data": json.dumps(credential_data)
                }).eq("platform_user_id", platform_user_id).eq("platform", "linkedin").execute()
                
                logger.info(f"LinkedIn account updated successfully for user {user_id}")
                
            except Exception as update_error:
                logger.error(f"Failed to update existing LinkedIn connection: {update_error}")
                return RedirectResponse(url=f"{return_url}?error=database_error")

        # Redirect back to frontend with success
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=linkedin"

        return RedirectResponse(url=final_redirect_url)

    except requests.RequestException as req_error:
        logger.error(f"LinkedIn API request error: {req_error}")
        return RedirectResponse(url=f"{return_url}?error=linkedin_api_error")
    
    except Exception as e:
        logger.error(f"Error during LinkedIn OAuth callback: {e}")
        return RedirectResponse(url=f"{return_url}?error=unexpected_error")


@router.get("/profile")
def get_linkedin_profile(user_id: str):
    """Get LinkedIn profile information for connected user"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq("provider_id", user_id).eq("platform", "linkedin").execute()
        
        if not result.data:
            return {"error": "❌ LinkedIn not connected. Please authenticate first."}
        
        account = result.data[0]
        credential_data = json.loads(account["data"])
        access_token = credential_data["access_token"]
        
        # Get current profile from LinkedIn API using userinfo endpoint
        userinfo_url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(userinfo_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    except requests.RequestException as req_error:
        logger.error(f"LinkedIn API request error: {req_error}")
        return {"error": "Failed to fetch LinkedIn profile"}
    
    except Exception as e:
        logger.error(f"Error reading LinkedIn profile: {e}")
        return {"error": "Failed to fetch profile"}


@router.post("/share")
def share_on_linkedin(user_id: str, content: dict):
    """Share content on LinkedIn"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq("provider_id", user_id).eq("platform", "linkedin").execute()
        
        if not result.data:
            return {"error": "❌ LinkedIn not connected. Please authenticate first."}
        
        account = result.data[0]
        credential_data = json.loads(account["data"])
        access_token = credential_data["access_token"]
        platform_user_id = account["platform_user_id"]
        
        # Prepare LinkedIn share payload
        share_url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"  # Required header for LinkedIn API
        }
        
        share_data = {
            "author": f"urn:li:person:{platform_user_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content.get("text", "")
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = requests.post(share_url, headers=headers, json=share_data)
        response.raise_for_status()
        
        post_id = response.headers.get("X-RestLi-Id", "Unknown")
        logger.info(f"LinkedIn post created successfully: {post_id}")
        
        return {"success": True, "message": "Content shared successfully on LinkedIn", "post_id": post_id}
    
    except requests.RequestException as req_error:
        logger.error(f"LinkedIn API request error: {req_error}")
        return {"error": "Failed to share on LinkedIn"}
    
    except Exception as e:
        logger.error(f"Error sharing on LinkedIn: {e}")
        return {"error": "Failed to share content"}