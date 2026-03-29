from fastapi import Request, HTTPException, Query
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from supabase_client import supabase
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
from typing import List
import os
import logging
import warnings

# Suppress OAuth scope warnings
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/google-drive",
    tags=["google-drive"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("google_drive")
SCOPES = get_platform_scopes("google_drive")
REDIRECT_URI = f"{BACKEND_URL}/auth/google-drive/oauth2callback"


@router.get("/login")
def google_drive_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to Google OAuth2 consent screen for Drive access"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"Google Drive OAuth credentials not found at {CLIENT_SECRETS_FILE}"
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
    logger.info(f"Redirecting to Google Drive auth URL for user_id: {user_id}")
    return RedirectResponse(auth_url)


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Handle Google Drive OAuth2 callback and save creds to Supabase"""
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
            .eq("platform", "google_drive")\
            .execute()
        
        # Also delete any existing record for this user (to clean up old connections)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "google_drive")\
            .execute()
        
        # Insert new record with actual granted scopes
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "google_drive",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": granted_scopes,  # Store actual granted scopes as array
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
            "connected": True,
            "data": creds_data
        }).execute()

        logger.info(f"Google Drive OAuth successful for user {user_id}")
        logger.info(f"Granted scopes saved: {granted_scopes}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=google_drive"
        
        return RedirectResponse(url=final_redirect_url)
    
    except Exception as e:
        logger.error(f"Error during Google Drive OAuth callback: {e}", exc_info=True)
        return RedirectResponse(url=f"{return_url}?error=unexpected_error")
    

@router.get("/files")
def read_files(user_id: str, max_results: int = 10):
    """Fetch user's Google Drive files"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq(
            "provider_id", user_id
        ).eq("platform", "google_drive").execute()

        if not result.data:
            return {"error": "❌ Google Drive not connected. Please authenticate first."}

        account = result.data[0]
        creds_data = account.get("data")
        granted_scopes = account.get("scopes", [])

        if not creds_data:
            return {"error": "❌ No stored credentials found for this account."}

        # Check if user granted necessary scopes for accessing Drive
        required_scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        has_drive_permission = any(scope in granted_scopes for scope in required_scopes)
        
        if not has_drive_permission:
            return {
                "error": "❌ Insufficient permissions. Please re-authenticate and grant Drive access.",
                "missing_scopes": required_scopes,
                "granted_scopes": granted_scopes
            }

        # Create credentials from stored data
        import json
        creds = Credentials.from_authorized_user_info(json.loads(creds_data))
        drive_service = build("drive", "v3", credentials=creds)

        # Fetch files
        results = drive_service.files().list(
            pageSize=max_results,
            fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink, iconLink)",
            orderBy="modifiedTime desc"
        ).execute()
        files = results.get('files', [])

        return {
            "files": files,
            "count": len(files)
        }

    except Exception as e:
        logger.error(f"Error reading Drive files: {e}")
        
        # Check if it's a permission error
        error_str = str(e).lower()
        if 'insufficient' in error_str or 'permission' in error_str or '403' in error_str:
            return {
                "error": "❌ Permission denied. Please re-authenticate and grant required Drive permissions.",
                "details": str(e)
            }
        
        return {"error": "Failed to fetch Drive files", "details": str(e)}


@router.get("/scopes")
def get_granted_scopes(user_id: str):
    """Check which Google Drive scopes the user has granted"""
    try:
        result = supabase.table("connected_accounts")\
            .select("scopes, platform_username, connected")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_drive")\
            .execute()

        if not result.data:
            return {
                "connected": False,
                "error": "Google Drive not connected"
            }

        account = result.data[0]
        granted_scopes = account.get("scopes", [])
        
        # Define all possible Google Drive scopes
        all_scopes = {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/drive": "Full access to your Google Drive",
            "https://www.googleapis.com/auth/drive.file": "Access files created by this app",
            "https://www.googleapis.com/auth/drive.readonly": "View your Google Drive files",
            "https://www.googleapis.com/auth/drive.metadata.readonly": "View metadata of your Drive files"
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
            "can_access_drive": any(s in granted_scopes for s in [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive.readonly"
            ])
        }

    except Exception as e:
        logger.error(f"Error checking scopes: {e}")
        return {"error": "Failed to check scopes", "details": str(e)}


@router.get("/status")
def get_connection_status(user_id: str):
    """Check if Google Drive is connected for a user"""
    try:
        result = supabase.table("connected_accounts").select("*").eq(
            "provider_id", user_id
        ).eq("platform", "google_drive").execute()
        
        if not result.data:
            return {
                "connected": False,
                "message": "Google Drive not connected"
            }
        
        account = result.data[0]
        return {
            "connected": account.get("connected", False),
            "platform_username": account.get("platform_username"),
            "platform_user_id": account.get("platform_user_id")
        }
    except Exception as e:
        logger.error(f"Error checking Google Drive connection status: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


@router.post("/update-scopes")
def update_scopes(user_id: str = Query(...), scopes: List[str] = Query(...), return_url: str = Query(None)):
    """
    Trigger re-authentication with updated scopes
    This endpoint initiates OAuth flow with modified scope list
    """
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        if not scopes or len(scopes) == 0:
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
        logger.error(f"Error updating scopes for Google Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/revoke-scope")
def revoke_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """
    Revoke a specific scope by initiating re-authentication without it
    """
    try:
        if not user_id or not scope:
            raise HTTPException(status_code=400, detail="user_id and scope are required")
        
        # Get current scopes from database
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_drive")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Google Drive account not connected")
        
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
        logger.error(f"Error revoking scope for Google Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-scope")
def add_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """
    Add a new scope by initiating re-authentication with additional permission
    """
    try:
        if not user_id or not scope:
            raise HTTPException(status_code=400, detail="user_id and scope are required")
        
        # Get current scopes from database
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_drive")\
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
        logger.error(f"Error adding scope for Google Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))
