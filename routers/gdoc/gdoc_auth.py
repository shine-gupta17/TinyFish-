from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from supabase_client import supabase
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
import os
import logging
import warnings

# Suppress OAuth scope warnings
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/gdoc",
    tags=["gdoc"]
)
router_callback = APIRouter(
    prefix="/auth",
    tags=["gdoc"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("google_docs")
SCOPES = get_platform_scopes("google_docs")

# Use generic callback to match OAuth client configuration already present
REDIRECT_URI = f"{BACKEND_URL}/auth/callback"


@router.get("/login")
def gdoc_login(user_id: str, return_url: str | None = None) -> RedirectResponse:
    """Redirect user to Google Docs OAuth2 consent screen"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"Google Docs OAuth credentials not found at {CLIENT_SECRETS_FILE}"
        )

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"

    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",  # Allow incremental authorization
        state=state_value,
    )
    logger.info(f"Redirecting to Google Docs auth URL for user_id: {user_id}")
    return RedirectResponse(auth_url)


def _handle_oauth_callback(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Shared OAuth2 callback handler for Docs."""
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None
    
    try:
        if "__RETURN_URL__" in state:
            user_id, return_url = state.split("__RETURN_URL__", 1)
        else:
            user_id = state

        if not code or not user_id:
            logger.error(f"Missing code or user_id. code={bool(code)}, user_id={user_id}")
            return RedirectResponse(f"{return_url}?error=authorization_failed")

        logger.info(f"Starting OAuth callback for user {user_id}")
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
            redirect_uri=REDIRECT_URI,
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
                redirect_uri=REDIRECT_URI,
            )
            flow.fetch_token(code=code)
        
        creds = flow.credentials

        # Get user profile from OAuth2 API (requires only basic scopes)
        platform_user_id = None
        platform_username = None
        
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
            .eq("platform", "docs")\
            .execute()
        
        # Also delete any existing record for this user (to clean up old connections)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "docs")\
            .execute()
        
        # Insert new record with actual granted scopes
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "docs",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": granted_scopes,  # Store actual granted scopes as array
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
            "connected": True,
            "data": creds_data,
        }).execute()

        logger.info(f"Google Docs OAuth successful for user {user_id}")
        logger.info(f"Granted scopes saved: {granted_scopes}")
        
        sep = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{sep}auth_success=docs"
        return RedirectResponse(url=final_redirect_url)

    except Exception as e:
        logger.error(f"Error during Google Docs OAuth callback: {e}", exc_info=True)
        # Use a fallback return_url if it's not set
        safe_return_url = return_url if return_url else f"{FRONTEND_PLATFORM_URL}/platforms"
        return RedirectResponse(url=f"{safe_return_url}?error=unexpected_error&details={str(e)[:100]}")


@router.get("/oauth2callback")
def gdoc_oauth2callback_prefixed(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Support legacy/prefixed callback if configured in Google Cloud."""
    return _handle_oauth_callback(request, code, state, scope)


@router_callback.get("/callback")
def gdoc_oauth2callback_root(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Root-level callback to match existing Google OAuth configuration."""
    return _handle_oauth_callback(request, code, state, scope)


@router.get("/scopes")
def get_granted_scopes(user_id: str):
    """Check which Google Docs scopes the user has granted"""
    try:
        result = supabase.table("connected_accounts")\
            .select("scopes, platform_username, connected")\
            .eq("provider_id", user_id)\
            .eq("platform", "docs")\
            .execute()

        if not result.data:
            return {
                "connected": False,
                "error": "Google Docs not connected"
            }

        account = result.data[0]
        granted_scopes = account.get("scopes", [])
        
        # Define all possible Google Docs scopes
        all_scopes = {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/drive.file": "See, edit, create and delete only the specific Google Drive files that you use with this app",
            "https://www.googleapis.com/auth/documents": "See, edit, create, and delete all your Google Docs documents",
            "https://www.googleapis.com/auth/documents.readonly": "See all your Google Docs documents",
            "https://www.googleapis.com/auth/drive.readonly": "See and download all your Google Drive files"
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
            "can_read_docs": any(s in granted_scopes for s in [
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/documents.readonly"
            ])
        }

    except Exception as e:
        logger.error(f"Error checking scopes: {e}")
        return {"error": "Failed to check scopes", "details": str(e)}


@router.post("/update-scopes")
def update_scopes(user_id: str = Query(...), scopes: list[str] = Query(...), return_url: str = Query(None)):
    """
    Trigger re-authentication with updated scopes
    This endpoint initiates OAuth flow with modified scope list
    """
    try:
        if not user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="user_id is required")
        
        if not scopes:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="scopes list is required")
        
        # Validate scopes - ensure basic scopes are included
        basic_scopes = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
        final_scopes = list(set(basic_scopes + scopes))
        
        # Create OAuth flow with new scopes
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=final_scopes,
            redirect_uri=REDIRECT_URI
        )
        
        # Include return_url in state if provided
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="false",  # Force re-consent with exact scopes
            state=state_value
        )
        
        return {
            "success": True,
            "auth_url": auth_url,
            "message": "Redirect user to auth_url to update permissions"
        }
        
    except Exception as e:
        logger.error(f"Error updating scopes for Google Docs: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/revoke-scope")
def revoke_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """
    Revoke a specific scope by initiating re-authentication without it
    """
    try:
        if not user_id or not scope:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="user_id and scope are required")
        
        # Get current scopes from database
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "docs")\
            .execute()
        
        if not result.data:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Google Docs account not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Remove the scope to revoke
        new_scopes = [s for s in current_scopes if s != scope]
        
        # Ensure basic scopes remain
        basic_scopes = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
        final_scopes = list(set(basic_scopes + new_scopes))
        
        # Create OAuth flow with reduced scopes
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=final_scopes,
            redirect_uri=REDIRECT_URI
        )
        
        # Include return_url in state if provided
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="false",  # Force re-consent with exact scopes
            state=state_value
        )
        
        return {
            "success": True,
            "auth_url": auth_url,
            "removed_scope": scope,
            "message": "Redirect user to auth_url to complete scope revocation"
        }
        
    except Exception as e:
        logger.error(f"Error revoking scope for Google Docs: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-scope")
def add_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """
    Add a new scope by initiating re-authentication with additional permission
    """
    try:
        if not user_id or not scope:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="user_id and scope are required")
        
        # Get current scopes from database
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "docs")\
            .execute()
        
        current_scopes = []
        if result.data:
            current_scopes = result.data[0].get("scopes", [])
        
        # Add the new scope
        new_scopes = list(set(current_scopes + [scope]))
        
        # Create OAuth flow with expanded scopes
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=new_scopes,
            redirect_uri=REDIRECT_URI
        )
        
        # Include return_url in state if provided
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="false",  # Force re-consent with exact scopes
            state=state_value
        )
        
        return {
            "success": True,
            "auth_url": auth_url,
            "added_scope": scope,
            "message": "Redirect user to auth_url to grant additional permission"
        }
        
    except Exception as e:
        logger.error(f"Error adding scope for Google Docs: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
