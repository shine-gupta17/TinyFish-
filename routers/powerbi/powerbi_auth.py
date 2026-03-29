from fastapi import Request, HTTPException, Query
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from typing import List
from supabase_client import supabase
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
import os
import logging
import json
import warnings
from azure.identity import ClientSecretCredential
from azure.identity.aio import ClientSecretCredential as AsyncClientSecretCredential
import requests

# Suppress OAuth scope warnings
warnings.filterwarnings("ignore", message=".*Scope has changed.*")

router = APIRouter(
    prefix="/auth/powerbi",
    tags=["powerbi"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("powerbi")
SCOPES = get_platform_scopes("powerbi")
REDIRECT_URI = f"{BACKEND_URL}/auth/powerbi/oauth2callback"

# Microsoft Identity Platform endpoints
AUTHORITY_URL = "https://login.microsoftonline.com/common"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
GRAPH_API_URL = "https://graph.microsoft.com/v1.0"


def load_powerbi_credentials() -> dict:
    """Load Power BI credentials from JSON file"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"Power BI OAuth credentials not found at {CLIENT_SECRETS_FILE}"
        )
    
    with open(CLIENT_SECRETS_FILE, "r") as f:
        return json.load(f)


@router.get("/login")
def powerbi_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to Power BI OAuth2 consent screen"""
    try:
        credentials = load_powerbi_credentials()
        client_id = credentials.get("client_id")
        
        if not client_id:
            raise HTTPException(
                status_code=500,
                detail="Power BI client_id not configured in credentials"
            )
        
        state_value = user_id
        if return_url:
            state_value = f"{user_id}__RETURN_URL__{return_url}"
        
        # Build authorization URL
        auth_params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "response_mode": "query",
            "scope": " ".join(SCOPES),
            "state": state_value,
            "prompt": "select_account"
        }
        
        auth_url = AUTHORIZE_URL + "?" + "&".join(
            f"{key}={requests.utils.quote(str(value))}" 
            for key, value in auth_params.items()
        )
        
        logger.info(f"Redirecting to Power BI auth URL for user_id: {user_id}")
        return RedirectResponse(auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating Power BI login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initiate Power BI authentication")


@router.get("/oauth2callback")
def powerbi_oauth2callback(request: Request, code: str = None, state: str = None, error: str = None) -> RedirectResponse:
    """Handle Power BI OAuth2 callback and save credentials to Supabase"""
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None
    
    if error:
        logger.error(f"Power BI OAuth error: {error}")
        return RedirectResponse(f"{return_url}?error=authorization_failed")
    
    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state
    
    if not code or not user_id:
        return RedirectResponse(f"{return_url}?error=authorization_failed")
    
    try:
        credentials = load_powerbi_credentials()
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        tenant_id = credentials.get("tenant_id", "common")
        
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=500,
                detail="Power BI credentials not properly configured"
            )
        
        # Exchange authorization code for access token
        token_params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": " ".join(SCOPES)
        }
        
        token_response = requests.post(TOKEN_URL, data=token_params)
        
        if token_response.status_code != 200:
            logger.error(f"Failed to exchange authorization code: {token_response.text}")
            return RedirectResponse(f"{return_url}?error=token_exchange_failed")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        
        if not access_token:
            logger.error("No access token in Power BI response")
            return RedirectResponse(f"{return_url}?error=no_access_token")
        
        # Get Power BI user profile
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        profile_response = requests.get(f"{GRAPH_API_URL}/me", headers=headers)
        
        platform_user_id = None
        platform_username = None
        
        if profile_response.status_code == 200:
            profile_data = profile_response.json()
            platform_user_id = profile_data.get("id")
            platform_username = profile_data.get("userPrincipalName") or profile_data.get("displayName")
        else:
            logger.warning(f"Could not fetch Power BI profile: {profile_response.text}")
            platform_user_id = f"powerbi_{user_id}"
            platform_username = f"powerbi_{user_id}"
        
        # Calculate token expiration
        from datetime import datetime, timedelta
        token_expires_at = None
        if expires_in:
            token_expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        
        # Store credentials in database
        # Delete existing records to avoid conflicts
        supabase.table("connected_accounts")\
            .delete()\
            .eq("platform_user_id", platform_user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        # Insert new record
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "powerbi",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": SCOPES,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
            "connected": True,
            "data": json.dumps(token_data)
        }).execute()
        
        logger.info(f"Power BI OAuth successful for user {user_id}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=powerbi"
        
        return RedirectResponse(url=final_redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Power BI OAuth callback: {e}", exc_info=True)
        error_details = f"{type(e).__name__}: {str(e)}"
        return RedirectResponse(url=f"{return_url}?error=unexpected_error&details={error_details}")


@router.get("/verify-connection")
def verify_powerbi_connection(user_id: str):
    """Verify if Power BI account is connected"""
    try:
        result = supabase.table("connected_accounts")\
            .select("*")\
            .eq("provider_id", user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        if result.data:
            return {
                "connected": True,
                "platform_user_id": result.data[0].get("platform_user_id"),
                "platform_username": result.data[0].get("platform_username")
            }
        
        return {"connected": False}
        
    except Exception as e:
        logger.error(f"Error verifying Power BI connection: {e}")
        return {"connected": False, "error": str(e)}


@router.post("/disconnect")
def disconnect_powerbi(user_id: str):
    """Disconnect Power BI account"""
    try:
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        logger.info(f"Power BI disconnected for user {user_id}")
        return {"success": True, "message": "Power BI account disconnected"}
        
    except Exception as e:
        logger.error(f"Error disconnecting Power BI: {e}")
        return {"success": False, "error": str(e)}


@router.get("/workspaces")
def get_workspaces(user_id: str):
    """Get Power BI workspaces for the user"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts")\
            .select("*")\
            .eq("provider_id", user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        if not result.data:
            return {"error": "Power BI account not connected", "workspaces": []}
        
        access_token = result.data[0].get("access_token")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Fetch workspaces from Power BI REST API
        response = requests.get(
            "https://api.powerbi.com/v1.0/myorg/groups",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return {"workspaces": data.get("value", [])}
        else:
            logger.warning(f"Failed to fetch workspaces: {response.text}")
            return {"error": "Failed to fetch workspaces", "workspaces": []}
            
    except Exception as e:
        logger.error(f"Error fetching Power BI workspaces: {e}")
        return {"error": str(e), "workspaces": []}


@router.get("/reports")
def get_reports(user_id: str, workspace_id: str = None):
    """Get Power BI reports"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts")\
            .select("*")\
            .eq("provider_id", user_id)\
            .eq("platform", "powerbi")\
            .execute()
        
        if not result.data:
            return {"error": "Power BI account not connected", "reports": []}
        
        access_token = result.data[0].get("access_token")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Fetch reports from Power BI REST API
        if workspace_id:
            url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
        else:
            url = "https://api.powerbi.com/v1.0/myorg/reports"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return {"reports": data.get("value", [])}
        else:
            logger.warning(f"Failed to fetch reports: {response.text}")
            return {"error": "Failed to fetch reports", "reports": []}
            
    except Exception as e:
        logger.error(f"Error fetching Power BI reports: {e}")
        return {"error": str(e), "reports": []}
