from fastapi import Request, HTTPException, Query
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from typing import List
from supabase_client import supabase
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
import os
import logging
import json
import warnings

# Suppress OAuth scope warnings - we handle scope changes gracefully
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/gmail",
    tags=["gmail"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("gmail")
SCOPES = get_platform_scopes("gmail")
REDIRECT_URI = f"{BACKEND_URL}/auth/gmail/oauth2callback"


@router.get("/login")
def gmail_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to Gmail OAuth2 consent screen"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500, 
            detail=f"Gmail OAuth credentials not found at {CLIENT_SECRETS_FILE}"
        )
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"

    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",  # Allow incremental authorization
        state=state_value
    )
    logger.info(f"Redirecting to Gmail auth URL for user_id: {user_id}, requesting scopes: {SCOPES}")
    return RedirectResponse(auth_url)


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Handle Gmail OAuth2 callback and save creds to Supabase"""
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None

    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state

    if not code or not user_id:
        return RedirectResponse(f"{return_url}?error=authorization_failed")

    try:
        # Parse the actual granted scopes from Google's response
        granted_scopes = []
        if scope:
            granted_scopes = scope.split()
            logger.info(f"Requested scopes: {SCOPES}")
            logger.info(f"Granted scopes by user: {granted_scopes}")
            
            # Check if user granted at least basic scopes
            required_basic_scopes = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
            has_basic_scopes = any(s in granted_scopes for s in required_basic_scopes)
            
            if not has_basic_scopes:
                logger.error("User did not grant required basic scopes")
                return RedirectResponse(f"{return_url}?error=insufficient_permissions")
        
        if not granted_scopes:
            granted_scopes = SCOPES
            logger.warning("No scope parameter in callback, using requested scopes")
        
        # Create flow with the GRANTED scopes, not the requested ones
        # This prevents scope mismatch errors
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=granted_scopes,  # Use actual granted scopes
            redirect_uri=REDIRECT_URI
        )
        
        # Disable scope validation to handle partial grants gracefully
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        
        try:
            # Fetch token with the authorization code
            flow.fetch_token(code=code)
        except Exception as token_error:
            logger.error(f"Error fetching token: {token_error}")
            # If token fetch fails, try one more time with relaxed settings
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=granted_scopes,
                redirect_uri=REDIRECT_URI
            )
            flow.fetch_token(code=code)
        
        creds = flow.credentials

        # Get user profile - try Gmail API first, fallback to OAuth2 API
        platform_user_id = None
        platform_username = None
        
        try:
            # Check if user granted Gmail read scope
            gmail_scopes = [s for s in granted_scopes if 'gmail' in s.lower()]
            if gmail_scopes:
                service = build("gmail", "v1", credentials=creds)
                profile = service.users().getProfile(userId="me").execute()
                platform_user_id = profile["emailAddress"]
                platform_username = profile["emailAddress"]
        except Exception as profile_error:
            logger.warning(f"Could not get Gmail profile: {profile_error}")
        
        # Fallback: get profile from OAuth2 API (requires only basic scopes)
        if not platform_user_id:
            try:
                oauth_service = build("oauth2", "v2", credentials=creds)
                oauth_profile = oauth_service.userinfo().get().execute()
                platform_user_id = oauth_profile.get("email")
                platform_username = oauth_profile.get("name", oauth_profile.get("email", "Unknown"))
            except Exception as oauth_error:
                logger.error(f"Could not get OAuth profile: {oauth_error}")
                return RedirectResponse(f"{return_url}?error=profile_fetch_failed")

        creds_data = creds.to_json()

        # Delete existing record for this platform_user_id (to avoid conflicts when same account switches users)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("platform_user_id", platform_user_id)\
            .eq("platform", "gmail")\
            .execute()
        
        # Also delete any existing record for this user (to clean up old connections)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "gmail")\
            .execute()
        
        # Insert new record with actual granted scopes
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "gmail",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": granted_scopes,  # Store actual granted scopes as array
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
            "connected": True,
            "data": creds_data
        }).execute()

        logger.info(f"Gmail OAuth successful for user {user_id}")
        logger.info(f"Granted scopes saved: {granted_scopes}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=gmail"

        return RedirectResponse(url=final_redirect_url)

    except Exception as e:
        logger.error(f"Error during Gmail OAuth callback: {e}", exc_info=True)
        error_details = f"{type(e).__name__}: {str(e)}"
        return RedirectResponse(url=f"{return_url}?error=unexpected_error&details={error_details}")
    

@router.get("/emails")
def read_emails(user_id: str):
    """Fetch last 5 Gmail messages"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq("provider_id", user_id).eq("platform", "gmail").execute()

        if not result.data:
            return {"error": "❌ Gmail not connected. Please authenticate first."}

        account = result.data[0]
        creds_data = account.get("data")
        granted_scopes = account.get("scopes", [])

        if not creds_data:
            return {"error": "❌ No stored credentials found for this account."}

        # Check if user granted necessary scopes for reading emails
        required_scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify"
        ]
        has_read_permission = any(scope in granted_scopes for scope in required_scopes)
        
        if not has_read_permission:
            return {
                "error": "❌ Insufficient permissions. Please re-authenticate and grant Gmail read access.",
                "missing_scopes": required_scopes,
                "granted_scopes": granted_scopes
            }

        # Create credentials from stored data
        creds = Credentials.from_authorized_user_info(json.loads(creds_data))
        service = build("gmail", "v1", credentials=creds)

        # Fetch last 5 messages
        results = service.users().messages().list(userId="me", maxResults=5).execute()
        messages = results.get("messages", [])

        emails = []
        for msg in messages:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            snippet = msg_data.get("snippet", "")
            emails.append({"id": msg["id"], "snippet": snippet})

        return emails

    except Exception as e:
        logger.error(f"Error reading emails: {e}")
        
        # Check if it's a permission error
        error_str = str(e).lower()
        if 'insufficient' in error_str or 'permission' in error_str or '403' in error_str:
            return {
                "error": "❌ Permission denied. Please re-authenticate and grant required Gmail permissions.",
                "details": str(e)
            }
        
        return {"error": "Failed to fetch emails", "details": str(e)}


@router.get("/scopes")
def get_granted_scopes(user_id: str):
    """Check which Gmail scopes the user has granted"""
    try:
        result = supabase.table("connected_accounts")\
            .select("scopes, platform_username, connected")\
            .eq("provider_id", user_id)\
            .eq("platform", "gmail")\
            .execute()

        if not result.data:
            return {
                "connected": False,
                "error": "Gmail not connected"
            }

        account = result.data[0]
        granted_scopes = account.get("scopes", [])
        
        # Define all possible Gmail scopes with exact Google permission text
        all_scopes = {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/gmail.readonly": "View your email messages and settings",
            "https://www.googleapis.com/auth/gmail.send": "Send email on your behalf",
            "https://www.googleapis.com/auth/gmail.compose": "Manage drafts and send emails",
            "https://www.googleapis.com/auth/gmail.modify": "Read, compose, and send emails from your Gmail account"
        }
        
        # Check which scopes are granted vs missing
        scope_status = {}
        for scope, description in all_scopes.items():
            scope_status[scope] = {
                "description": description,
                "granted": scope in granted_scopes
            }
        
        return {
            "connected": account.get("connected", False),
            "platform_username": account.get("platform_username"),
            "granted_scopes": granted_scopes,
            "scope_status": scope_status,
            "can_read_emails": any(s in granted_scopes for s in [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify"
            ]),
            "can_send_emails": any(s in granted_scopes for s in [
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.compose"
            ])
        }

    except Exception as e:
        logger.error(f"Error checking scopes: {e}")
        return {"error": "Failed to check scopes", "details": str(e)}


@router.post("/update-scopes")
def update_scopes(user_id: str = Query(...), scopes: List[str] = Query(...), return_url: str = Query(None)):
    """Update Gmail scopes by redirecting to Google OAuth with new scopes"""
    try:
        if not scopes:
            raise HTTPException(status_code=400, detail="No scopes provided")
        
        logger.info(f"Updating Gmail scopes for user {user_id} to: {scopes}")
        
        # Redirect to OAuth with the new set of scopes
        if not os.path.exists(CLIENT_SECRETS_FILE):
            raise HTTPException(
                status_code=500,
                detail=f"Gmail OAuth credentials not found at {CLIENT_SECRETS_FILE}"
            )
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=scopes,
            redirect_uri=REDIRECT_URI
        )
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
            state=state_value
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error updating scopes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-scope")
def add_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """Add a single scope to existing Gmail permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "gmail")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Gmail not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Add new scope if not already present
        if scope not in current_scopes:
            new_scopes = current_scopes + [scope]
        else:
            new_scopes = current_scopes
        
        logger.info(f"Adding scope {scope} to Gmail for user {user_id}")
        
        # Redirect to OAuth with updated scopes
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=new_scopes,
            redirect_uri=REDIRECT_URI
        )
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
            state=state_value
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error adding scope: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revoke-scope")
def revoke_scope(user_id: str, scope: str, return_url: str = None):
    """Remove a single scope from Gmail permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "gmail")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Gmail not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Basic scopes that should always remain
        basic_scopes = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        
        # Don't allow revoking basic scopes
        if scope in basic_scopes:
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke basic authentication scopes"
            )
        
        # Remove the scope
        new_scopes = [s for s in current_scopes if s != scope]
        
        # Ensure we keep at least basic scopes
        for basic_scope in basic_scopes:
            if basic_scope not in new_scopes:
                new_scopes.append(basic_scope)
        
        logger.info(f"Revoking scope {scope} from Gmail for user {user_id}")
        
        # Redirect to OAuth with updated scopes
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=new_scopes,
            redirect_uri=REDIRECT_URI
        )
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
            state=state_value
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error revoking scope: {e}")
        raise HTTPException(status_code=500, detail=str(e))
