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
import warnings

# Suppress OAuth scope warnings
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/google-calendar",
    tags=["google-calendar"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("google_calendar")
SCOPES = get_platform_scopes("google_calendar")
REDIRECT_URI = f"{BACKEND_URL}/auth/google-calendar/oauth2callback"


@router.get("/login")
def google_calendar_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to Google OAuth2 consent screen for Calendar access"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"Google Calendar OAuth credentials not found at {CLIENT_SECRETS_FILE}"
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
    logger.info(f"Redirecting to Google Calendar auth URL for user_id: {user_id}")
    return RedirectResponse(auth_url)


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str, scope: str = None) -> RedirectResponse:
    """Handle Google Calendar OAuth2 callback and save creds to Supabase"""
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
            .eq("platform", "google_calendar")\
            .execute()
        
        # Also delete any existing record for this user (to clean up old connections)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "google_calendar")\
            .execute()
        
        # Insert new record with actual granted scopes
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "google_calendar",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": granted_scopes,  # Store actual granted scopes as array
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
            "connected": True,
            "data": creds_data
        }).execute()

        logger.info(f"Google Calendar OAuth successful for user {user_id}")
        logger.info(f"Granted scopes saved: {granted_scopes}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=google_calendar"
        
        return RedirectResponse(url=final_redirect_url)
    
    except Exception as e:
        logger.error(f"Error during Google Calendar OAuth callback: {e}", exc_info=True)
        error_details = f"{type(e).__name__}: {str(e)}"
        return RedirectResponse(url=f"{return_url}?error=unexpected_error&details={error_details}")
    

@router.get("/calendars")
def read_calendars(user_id: str):
    """Fetch user's Google Calendars"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq(
            "provider_id", user_id
        ).eq("platform", "google_calendar").execute()

        if not result.data:
            return {"error": "❌ Google Calendar not connected. Please authenticate first."}

        account = result.data[0]
        creds_data = account.get("data")
        granted_scopes = account.get("scopes", [])

        if not creds_data:
            return {"error": "❌ No stored credentials found for this account."}

        # Check if user granted necessary scopes for reading calendar
        required_scopes = [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events"
        ]
        has_calendar_permission = any(scope in granted_scopes for scope in required_scopes)
        
        if not has_calendar_permission:
            return {
                "error": "❌ Insufficient permissions. Please re-authenticate and grant Calendar access.",
                "missing_scopes": required_scopes,
                "granted_scopes": granted_scopes
            }

        # Create credentials from stored data
        import json
        creds = Credentials.from_authorized_user_info(json.loads(creds_data))
        calendar_service = build("calendar", "v3", credentials=creds)

        # Fetch user's calendars
        calendars_result = calendar_service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])

        calendar_list = []
        for calendar in calendars:
            calendar_list.append({
                "id": calendar["id"],
                "summary": calendar.get("summary", ""),
                "description": calendar.get("description", ""),
                "timeZone": calendar.get("timeZone", ""),
                "primary": calendar.get("primary", False),
                "accessRole": calendar.get("accessRole", "")
            })

        return calendar_list

    except Exception as e:
        logger.error(f"Error reading calendars: {e}")
        
        # Check if it's a permission error
        error_str = str(e).lower()
        if 'insufficient' in error_str or 'permission' in error_str or '403' in error_str:
            return {
                "error": "❌ Permission denied. Please re-authenticate and grant required Calendar permissions.",
                "details": str(e)
            }
        
        return {"error": "Failed to fetch calendars", "details": str(e)}


@router.get("/events")
def read_events(user_id: str, calendar_id: str = "primary", max_results: int = 10):
    """Fetch events from a specific Google Calendar"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq(
            "provider_id", user_id
        ).eq("platform", "google_calendar").execute()

        if not result.data:
            return {"error": "❌ Google Calendar not connected. Please authenticate first."}

        account = result.data[0]
        creds_data = account.get("data")
        granted_scopes = account.get("scopes", [])

        if not creds_data:
            return {"error": "❌ No stored credentials found for this account."}

        # Check if user granted necessary scopes for reading calendar
        required_scopes = [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events"
        ]
        has_calendar_permission = any(scope in granted_scopes for scope in required_scopes)
        
        if not has_calendar_permission:
            return {
                "error": "❌ Insufficient permissions. Please re-authenticate and grant Calendar access.",
                "missing_scopes": required_scopes,
                "granted_scopes": granted_scopes
            }

        # Create credentials from stored data
        import json
        creds = Credentials.from_authorized_user_info(json.loads(creds_data))
        calendar_service = build("calendar", "v3", credentials=creds)

        # Fetch upcoming events
        from datetime import datetime
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        
        events_result = calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            event_list.append({
                "id": event["id"],
                "summary": event.get("summary", "No Title"),
                "description": event.get("description", ""),
                "start": start,
                "end": event['end'].get('dateTime', event['end'].get('date')),
                "location": event.get("location", ""),
                "htmlLink": event.get("htmlLink", "")
            })

        return event_list

    except Exception as e:
        logger.error(f"Error reading events: {e}")
        
        # Check if it's a permission error
        error_str = str(e).lower()
        if 'insufficient' in error_str or 'permission' in error_str or '403' in error_str:
            return {
                "error": "❌ Permission denied. Please re-authenticate and grant required Calendar permissions.",
                "details": str(e)
            }
        
        return {"error": "Failed to fetch events", "details": str(e)}


@router.get("/scopes")
def get_granted_scopes(user_id: str):
    """Check which Google Calendar scopes the user has granted"""
    try:
        result = supabase.table("connected_accounts")\
            .select("scopes, platform_username, connected")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_calendar")\
            .execute()

        if not result.data:
            return {
                "connected": False,
                "error": "Google Calendar not connected"
            }

        account = result.data[0]
        granted_scopes = account.get("scopes", [])
        
        # Define all possible Google Calendar scopes with exact Google permission text
        all_scopes = {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/calendar.events": "View and edit events on all your calendars",
            "https://www.googleapis.com/auth/calendar": "See, edit, share, and permanently delete all the calendars you can access using Google Calendar"
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
            "can_read_calendar": any(s in granted_scopes for s in [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events"
            ])
        }

    except Exception as e:
        logger.error(f"Error checking scopes: {e}")
        return {"error": "Failed to check scopes", "details": str(e)}


@router.get("/status")
def get_connection_status(user_id: str):
    """Check if Google Calendar is connected for a user"""
    try:
        result = supabase.table("connected_accounts").select("*").eq(
            "provider_id", user_id
        ).eq("platform", "google_calendar").execute()
        
        if not result.data:
            return {
                "connected": False,
                "message": "Google Calendar not connected"
            }
        
        account = result.data[0]
        return {
            "connected": account.get("connected", False),
            "platform_username": account.get("platform_username"),
            "platform_user_id": account.get("platform_user_id")
        }
    except Exception as e:
        logger.error(f"Error checking Google Calendar connection status: {e}")
        return {
            "connected": False,
            "error": str(e)
        }


@router.post("/update-scopes")
def update_scopes(user_id: str = Query(...), scopes: List[str] = Query(...), return_url: str = Query(None)):
    """Update Google Calendar scopes by redirecting to Google OAuth with new scopes"""
    try:
        if not scopes:
            raise HTTPException(status_code=400, detail="No scopes provided")
        
        logger.info(f"Updating Google Calendar scopes for user {user_id} to: {scopes}")
        
        # Redirect to OAuth with the new set of scopes
        if not os.path.exists(CLIENT_SECRETS_FILE):
            raise HTTPException(
                status_code=500,
                detail=f"Google Calendar OAuth credentials not found at {CLIENT_SECRETS_FILE}"
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
    """Add a single scope to existing Google Calendar permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_calendar")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Google Calendar not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Add new scope if not already present
        if scope not in current_scopes:
            new_scopes = current_scopes + [scope]
        else:
            new_scopes = current_scopes
        
        logger.info(f"Adding scope {scope} to Google Calendar for user {user_id}")
        
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
    """Remove a single scope from Google Calendar permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "google_calendar")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Google Calendar not connected")
        
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
        
        logger.info(f"Revoking scope {scope} from Google Calendar for user {user_id}")
        
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
