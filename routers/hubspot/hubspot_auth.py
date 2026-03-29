from fastapi import Request, HTTPException, Query
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from typing import List
from supabase_client import supabase
import requests
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
import os
import logging
import json
import warnings
from datetime import datetime, timedelta
from urllib.parse import urlencode
import secrets

# Suppress OAuth scope warnings - we handle scope changes gracefully
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/hubspot",
    tags=["hubspot"]
)

logger = logging.getLogger(__name__)

# Temporary storage for OAuth state to user_id mapping
# In production, consider using Redis or a database
_oauth_state_cache = {}

# Fallback for development: store the last user_id that initiated OAuth
# This is NOT production-safe for multi-user scenarios
_last_oauth_user = {'user_id': None, 'return_url': None, 'timestamp': None}

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("hubspot")
SCOPES = get_platform_scopes("hubspot")
REDIRECT_URI = f"{BACKEND_URL}/auth/hubspot/oauth2callback"

# HubSpot OAuth URLs
HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"


def _load_hubspot_credentials():
    """Load HubSpot OAuth credentials from file"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"HubSpot OAuth credentials not found at {CLIENT_SECRETS_FILE}"
        )
    
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        creds = json.load(f)
    
    return {
        'client_id': creds['web']['client_id'],
        'client_secret': creds['web']['client_secret']
    }


@router.get("/login")
def hubspot_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to HubSpot OAuth2 consent screen"""
    try:
        creds = _load_hubspot_credentials()
        
        # Generate a unique state token
        state_token = secrets.token_urlsafe(32)
        
        # Store user_id and return_url in cache with state token as key
        _oauth_state_cache[state_token] = {
            'user_id': user_id,
            'return_url': return_url or f"{FRONTEND_PLATFORM_URL}/platforms",
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Also store as fallback (for when HubSpot doesn't return state)
        _last_oauth_user['user_id'] = user_id
        _last_oauth_user['return_url'] = return_url or f"{FRONTEND_PLATFORM_URL}/platforms"
        _last_oauth_user['timestamp'] = datetime.utcnow().isoformat()
        
        # Build HubSpot authorization URL using urlencode for proper encoding
        params = {
            "client_id": creds['client_id'],
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),  # Space-separated scopes
            "state": state_token
        }
        
        auth_url = f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"
        
        logger.info(f"Generated OAuth state token for user_id: {user_id}")
        logger.info(f"State token: {state_token}")
        logger.info(f"Redirecting to: {auth_url}")
        return RedirectResponse(auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating HubSpot OAuth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str = Query(None), state: str = Query(None)) -> RedirectResponse:
    """Handle HubSpot OAuth2 callback and save creds to Supabase"""
    default_return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    
    # Log received parameters for debugging
    logger.info(f"HubSpot callback received - code: {code[:20] if code else None}..., state: {state}")
    logger.info(f"Full query params: {dict(request.query_params)}")

    # Retrieve user_id from state cache
    user_id = None
    return_url = default_return_url
    
    if state and state in _oauth_state_cache:
        # New cache-based approach
        cached_data = _oauth_state_cache.pop(state)  # Remove from cache after retrieval
        user_id = cached_data.get('user_id')
        return_url = cached_data.get('return_url', default_return_url)
        logger.info(f"Retrieved user_id from cache: {user_id}")
    elif state and "__RETURN_URL__" in state:
        # Fallback: Old format (direct user_id in state)
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1] if len(parts) > 1 else default_return_url
        logger.info(f"Retrieved user_id from old-format state: {user_id}")
    elif state:
        # Fallback: State is just the user_id
        user_id = state
        logger.info(f"Retrieved user_id directly from state: {user_id}")
    else:
        # Last resort: Use the most recent OAuth attempt (development fallback)
        if _last_oauth_user.get('user_id'):
            user_id = _last_oauth_user['user_id']
            return_url = _last_oauth_user.get('return_url', default_return_url)
            logger.warning(f"Using fallback: last OAuth user_id: {user_id} (state parameter not returned by HubSpot)")
        else:
            logger.warning(f"State not found in cache or missing: {state}")
    
    if not code:
        logger.error("Missing authorization code in callback")
        return RedirectResponse(f"{return_url}?error=missing_code")
    
    if not user_id:
        logger.error("Could not retrieve user_id from state cache")
        return RedirectResponse(f"{return_url}?error=missing_user_id")
    
    try:
        creds = _load_hubspot_credentials()
        
        # Exchange authorization code for access token
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': creds['client_id'],
            'client_secret': creds['client_secret'],
            'redirect_uri': REDIRECT_URI,
            'code': code
        }
        
        token_response = requests.post(HUBSPOT_TOKEN_URL, data=token_data)
        
        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return RedirectResponse(f"{return_url}?error=token_exchange_failed")
        
        token_info = token_response.json()
        access_token = token_info.get('access_token')
        refresh_token = token_info.get('refresh_token')
        expires_in = token_info.get('expires_in', 21600)  # Default 6 hours
        
        # Calculate token expiry time
        token_expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        
        # Get HubSpot account info
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Fetch account details
        account_response = requests.get(
            'https://api.hubapi.com/oauth/v1/access-tokens/' + access_token,
            headers=headers
        )
        
        if account_response.status_code == 200:
            account_info = account_response.json()
            platform_user_id = str(account_info.get('hub_id', ''))
            platform_username = account_info.get('hub_domain', platform_user_id)
        else:
            logger.warning(f"Could not fetch account info: {account_response.text}")
            platform_user_id = token_info.get('hub_id', user_id)
            platform_username = f"hubspot_{platform_user_id}"
        
        # Prepare credentials data
        creds_data = json.dumps({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_expires_at': token_expires_at,
            'client_id': creds['client_id'],
            'client_secret': creds['client_secret']
        })
        
        # Delete existing record for this platform_user_id (to avoid conflicts)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("platform_user_id", platform_user_id)\
            .eq("platform", "hubspot")\
            .execute()
        
        # Also delete any existing record for this user
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "hubspot")\
            .execute()
        
        # Insert new record
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "hubspot",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": SCOPES,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
            "connected": True,
            "data": creds_data
        }).execute()

        logger.info(f"HubSpot OAuth successful for user {user_id}")
        logger.info(f"Granted scopes saved: {SCOPES}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=hubspot"

        return RedirectResponse(url=final_redirect_url)

    except Exception as e:
        logger.error(f"Error during HubSpot OAuth callback: {e}", exc_info=True)
        error_details = f"{type(e).__name__}: {str(e)}"
        return RedirectResponse(url=f"{return_url}?error=unexpected_error&details={error_details}")


@router.get("/contacts")
def read_contacts(user_id: str, limit: int = 10):
    """Fetch HubSpot contacts"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts")\
            .select("*")\
            .eq("provider_id", user_id)\
            .eq("platform", "hubspot")\
            .execute()

        if not result.data:
            return {"error": "❌ HubSpot not connected. Please authenticate first."}

        account = result.data[0]
        access_token = account.get("access_token")
        
        if not access_token:
            return {"error": "❌ No access token found for this account."}

        # Fetch contacts from HubSpot
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.hubapi.com/crm/v3/objects/contacts?limit={limit}',
            headers=headers
        )
        
        if response.status_code != 200:
            return {
                "error": "Failed to fetch contacts",
                "details": response.text
            }
        
        contacts_data = response.json()
        contacts = contacts_data.get('results', [])
        
        return {
            "contacts": contacts,
            "total": len(contacts)
        }

    except Exception as e:
        logger.error(f"Error reading contacts: {e}")
        return {"error": "Failed to fetch contacts", "details": str(e)}


@router.get("/scopes")
def get_granted_scopes(user_id: str):
    """Check which HubSpot scopes the user has granted"""
    try:
        result = supabase.table("connected_accounts")\
            .select("scopes, platform_username, connected")\
            .eq("provider_id", user_id)\
            .eq("platform", "hubspot")\
            .execute()

        if not result.data:
            return {
                "connected": False,
                "error": "HubSpot not connected"
            }

        account = result.data[0]
        granted_scopes = account.get("scopes", [])
        
        # Define all possible HubSpot scopes
        all_scopes = {
            "crm.objects.contacts.read": "Read contacts",
            "crm.objects.contacts.write": "Create and update contacts",
            "crm.objects.companies.read": "Read companies",
            "crm.objects.companies.write": "Create and update companies",
            "crm.objects.deals.read": "Read deals",
            "crm.objects.deals.write": "Create and update deals",
            "crm.schemas.contacts.read": "Read contact properties",
            "crm.schemas.companies.read": "Read company properties",
            "crm.schemas.deals.read": "Read deal properties",
            "automation": "Access automation",
            "forms": "Access forms",
            "content": "Access content"
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
            "scope_status": scope_status
        }

    except Exception as e:
        logger.error(f"Error checking scopes: {e}")
        return {"error": "Failed to check scopes", "details": str(e)}


@router.post("/update-scopes")
def update_scopes(user_id: str = Query(...), scopes: List[str] = Query(...), return_url: str = Query(None)):
    """Update HubSpot scopes by redirecting to HubSpot OAuth with new scopes"""
    try:
        if not scopes:
            raise HTTPException(status_code=400, detail="No scopes provided")
        
        logger.info(f"Updating HubSpot scopes for user {user_id} to: {scopes}")
        
        creds = _load_hubspot_credentials()
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        scope_string = " ".join(scopes)
        auth_url = (
            f"{HUBSPOT_AUTH_URL}?"
            f"client_id={creds['client_id']}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope={scope_string}&"
            f"state={state_value}"
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error updating scopes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-scope")
def add_scope(user_id: str = Query(...), scope: str = Query(...), return_url: str = Query(None)):
    """Add a single scope to existing HubSpot permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "hubspot")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="HubSpot not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Add new scope if not already present
        if scope not in current_scopes:
            new_scopes = current_scopes + [scope]
        else:
            new_scopes = current_scopes
        
        logger.info(f"Adding scope {scope} to HubSpot for user {user_id}")
        
        creds = _load_hubspot_credentials()
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        scope_string = " ".join(new_scopes)
        auth_url = (
            f"{HUBSPOT_AUTH_URL}?"
            f"client_id={creds['client_id']}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope={scope_string}&"
            f"state={state_value}"
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error adding scope: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/revoke-scope")
def revoke_scope(user_id: str, scope: str, return_url: str = None):
    """Remove a single scope from HubSpot permissions"""
    try:
        # Get current scopes
        result = supabase.table("connected_accounts")\
            .select("scopes")\
            .eq("provider_id", user_id)\
            .eq("platform", "hubspot")\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="HubSpot not connected")
        
        current_scopes = result.data[0].get("scopes", [])
        
        # Remove the scope
        new_scopes = [s for s in current_scopes if s != scope]
        
        if not new_scopes:
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke all scopes. At least one scope must remain."
            )
        
        logger.info(f"Revoking scope {scope} from HubSpot for user {user_id}")
        
        creds = _load_hubspot_credentials()
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        scope_string = " ".join(new_scopes)
        auth_url = (
            f"{HUBSPOT_AUTH_URL}?"
            f"client_id={creds['client_id']}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope={scope_string}&"
            f"state={state_value}"
        )
        
        return {"redirect_url": auth_url}
    
    except Exception as e:
        logger.error(f"Error revoking scope: {e}")
        raise HTTPException(status_code=500, detail=str(e))
