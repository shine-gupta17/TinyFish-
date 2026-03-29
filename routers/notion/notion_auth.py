from fastapi import Request, HTTPException
from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse
from supabase_client import supabase
from config import FRONTEND_PLATFORM_URL, BACKEND_URL
from config.oauth_config import get_platform_scopes, get_credential_file
from .notion_utils import NotionAPIClient, create_text_block, create_heading_block
import os
import logging
import json
import requests
import base64
import urllib.parse

router = APIRouter(
    prefix="/auth/notion",
    tags=["notion"]
)

logger = logging.getLogger(__name__)

# Get credential file and scopes from centralized config
CLIENT_SECRETS_FILE = get_credential_file("notion")
SCOPES = get_platform_scopes("notion")
REDIRECT_URI = f"{BACKEND_URL}/auth/notion/oauth2callback"

# Notion OAuth URLs
NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"


@router.get("/debug")
def debug_notion_config():
    """Debug endpoint to check Notion configuration"""
    return {
        "redirect_uri": REDIRECT_URI,
        "backend_url": BACKEND_URL,
        "scopes": SCOPES,
        "credentials_file": CLIENT_SECRETS_FILE,
        "credentials_exists": os.path.exists(CLIENT_SECRETS_FILE)
    }


@router.get("/verify-credentials")
def verify_notion_credentials():
    """Verify Notion credentials without OAuth"""
    try:
        client_id, client_secret = load_notion_credentials()
        
        # Make a simple request to verify credentials
        headers = {
            "Authorization": f"Bearer invalid_token_for_test",
            "Notion-Version": "2022-06-28"
        }
        
        # This should return 401 with proper error if credentials are valid format
        response = requests.get("https://api.notion.com/v1/users/me", headers=headers)
        
        return {
            "client_id": client_id,
            "client_id_length": len(client_id),
            "client_secret_length": len(client_secret),
            "client_secret_format": client_secret.startswith("ntn_"),
            "test_response_status": response.status_code,
            "redirect_uri_configured": REDIRECT_URI
        }
        
    except Exception as e:
        return {"error": str(e)}


def load_notion_credentials():
    """Load Notion OAuth credentials from file"""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"Notion OAuth credentials not found at {CLIENT_SECRETS_FILE}"
        )
    
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        creds = json.load(f)
    
    return creds.get("client_id"), creds.get("client_secret")


@router.get("/login")
def notion_login(user_id: str, return_url: str = None) -> RedirectResponse:
    """Redirect user to Notion OAuth2 consent screen"""
    try:
        client_id, _ = load_notion_credentials()
    except HTTPException as e:
        raise e
    
    state_value = user_id
    if return_url:
        state_value = f"{user_id}__RETURN_URL__{return_url}"

    # Build Notion OAuth URL with proper URL encoding
    params = {
        "client_id": client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": REDIRECT_URI,
        "state": state_value
    }
    
    # URL encode the parameters
    query_string = urllib.parse.urlencode(params)
    auth_url = f"{NOTION_AUTH_URL}?{query_string}"
    
    logger.info(f"Redirecting to Notion auth URL for user_id: {user_id}")
    logger.info(f"Redirect URI being used: {REDIRECT_URI}")
    logger.info(f"Full auth URL: {auth_url}")
    return RedirectResponse(auth_url)


@router.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str, error: str = None) -> RedirectResponse:
    """Handle Notion OAuth2 callback and save creds to Supabase"""
    return_url = f"{FRONTEND_PLATFORM_URL}/platforms"
    user_id = None

    if "__RETURN_URL__" in state:
        parts = state.split("__RETURN_URL__", 1)
        user_id = parts[0]
        return_url = parts[1]
    else:
        user_id = state

    if error:
        logger.error(f"Notion OAuth error: {error}")
        return RedirectResponse(f"{return_url}?error={error}")

    if not code or not user_id:
        return RedirectResponse(f"{return_url}?error=authorization_failed")

    try:
        client_id, client_secret = load_notion_credentials()
        
        # Notion requires Basic Authentication for token exchange
        # Encode client_id:client_secret in base64
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        # Exchange code for access token using Basic Auth
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        logger.info(f"Sending token exchange request to Notion for user: {user_id}")
        logger.info(f"Using client_id: {client_id}")
        logger.info(f"Using redirect_uri: {REDIRECT_URI}")
        
        response = requests.post(NOTION_TOKEN_URL, json=token_data, headers=headers)
        
        logger.info(f"Notion token response status: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Notion token exchange failed: {response.text}")
            logger.error(f"Request data sent: {token_data}")
            return RedirectResponse(f"{return_url}?error=token_exchange_failed")
        
        token_response = response.json()
        access_token = token_response.get("access_token")
        
        if not access_token:
            logger.error("No access token in Notion response")
            return RedirectResponse(f"{return_url}?error=no_access_token")

        # Get user info from Notion
        user_headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28"
        }
        
        user_response = requests.get("https://api.notion.com/v1/users/me", headers=user_headers)
        
        if user_response.status_code != 200:
            logger.error(f"Failed to get Notion user info: {user_response.text}")
            return RedirectResponse(f"{return_url}?error=user_info_failed")
        
        user_data = user_response.json()
        platform_user_id = user_data.get("id")
        platform_username = user_data.get("name", user_data.get("id"))

        # Store token info
        token_info = {
            "access_token": access_token,
            "token_type": token_response.get("token_type", "bearer"),
            "bot_id": token_response.get("bot_id"),
            "workspace_name": token_response.get("workspace_name"),
            "workspace_icon": token_response.get("workspace_icon"),
            "workspace_id": token_response.get("workspace_id"),
            "owner": token_response.get("owner"),
            "duplicated_template_id": token_response.get("duplicated_template_id")
        }

        # Delete existing record if any (to avoid conflicts)
        supabase.table("connected_accounts")\
            .delete()\
            .eq("provider_id", user_id)\
            .eq("platform", "notion")\
            .execute()
        
        # Insert new record
        supabase.table("connected_accounts").insert({
            "provider_id": user_id,
            "platform": "notion",
            "platform_user_id": platform_user_id,
            "platform_username": platform_username,
            "scopes": SCOPES,
            "access_token": access_token,
            "refresh_token": None,  # Notion doesn't use refresh tokens
            "token_expires_at": None,  # Notion tokens don't expire
            "connected": True,
            "data": json.dumps(token_info)
        }).execute()

        logger.info(f"Notion OAuth successful for user {user_id}")
        
        separator = '&' if '?' in return_url else '?'
        final_redirect_url = f"{return_url}{separator}auth_success=notion"

        return RedirectResponse(url=final_redirect_url)

    except Exception as e:
        logger.error(f"Error during Notion OAuth callback: {e}", exc_info=True)
        return RedirectResponse(url=f"{return_url}?error=unexpected_error")


@router.get("/pages")
def get_notion_pages(user_id: str):
    """Fetch user's Notion pages"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq("provider_id", user_id).eq("platform", "notion").execute()

        if not result.data:
            return {"error": "❌ Notion not connected. Please authenticate first."}

        account = result.data[0]
        access_token = account.get("access_token")

        if not access_token:
            return {"error": "❌ No stored access token found for this account."}

        # Make request to Notion API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # Search for pages (this requires appropriate permissions)
        search_data = {
            "filter": {
                "value": "page",
                "property": "object"
            },
            "page_size": 10
        }
        
        response = requests.post(
            "https://api.notion.com/v1/search",
            headers=headers,
            json=search_data
        )
        
        if response.status_code != 200:
            logger.error(f"Notion API error: {response.text}")
            return {"error": "Failed to fetch pages from Notion"}
        
        data = response.json()
        pages = []
        
        for result in data.get("results", []):
            if result.get("object") == "page":
                page_info = {
                    "id": result.get("id"),
                    "title": "Untitled",
                    "url": result.get("url"),
                    "created_time": result.get("created_time"),
                    "last_edited_time": result.get("last_edited_time")
                }
                
                # Extract title from properties
                properties = result.get("properties", {})
                for prop_name, prop_data in properties.items():
                    if prop_data.get("type") == "title":
                        title_array = prop_data.get("title", [])
                        if title_array:
                            page_info["title"] = title_array[0].get("plain_text", "Untitled")
                        break
                
                pages.append(page_info)
        
        return {"pages": pages}

    except Exception as e:
        logger.error(f"Error fetching Notion pages: {e}")
        return {"error": "Failed to fetch pages"}


@router.get("/databases")
def get_notion_databases(user_id: str):
    """Fetch user's Notion databases"""
    try:
        # Get credentials from database
        result = supabase.table("connected_accounts").select("*").eq("provider_id", user_id).eq("platform", "notion").execute()

        if not result.data:
            return {"error": "❌ Notion not connected. Please authenticate first."}

        account = result.data[0]
        access_token = account.get("access_token")

        if not access_token:
            return {"error": "❌ No stored access token found for this account."}

        # Make request to Notion API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # Search for databases
        search_data = {
            "filter": {
                "value": "database",
                "property": "object"
            },
            "page_size": 10
        }
        
        response = requests.post(
            "https://api.notion.com/v1/search",
            headers=headers,
            json=search_data
        )
        
        if response.status_code != 200:
            logger.error(f"Notion API error: {response.text}")
            return {"error": "Failed to fetch databases from Notion"}
        
        data = response.json()
        databases = []
        
        for result in data.get("results", []):
            if result.get("object") == "database":
                db_info = {
                    "id": result.get("id"),
                    "title": "Untitled Database",
                    "url": result.get("url"),
                    "created_time": result.get("created_time"),
                    "last_edited_time": result.get("last_edited_time")
                }
                
                # Extract title
                title_array = result.get("title", [])
                if title_array:
                    db_info["title"] = title_array[0].get("plain_text", "Untitled Database")
                
                databases.append(db_info)
        
        return {"databases": databases}

    except Exception as e:
        logger.error(f"Error fetching Notion databases: {e}")
        return {"error": "Failed to fetch databases"}


@router.post("/create-page")
def create_notion_page(user_id: str, parent_id: str, title: str, content: str = ""):
    """Create a new page in Notion"""
    try:
        client = NotionAPIClient(user_id)
        
        # Create content blocks
        blocks = []
        if content:
            # Split content by lines and create paragraph blocks
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    blocks.append(create_text_block(line.strip()))
        
        # Create the page
        page = client.create_page(
            parent_id=parent_id,
            title=title,
            content=blocks,
            parent_type="page"
        )
        
        return {
            "success": True,
            "page_id": page.get("id"),
            "url": page.get("url"),
            "message": "Page created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating Notion page: {e}")
        return {"error": f"Failed to create page: {str(e)}"}


@router.post("/create-database")
def create_notion_database(user_id: str, parent_id: str, title: str):
    """Create a new database in Notion"""
    try:
        client = NotionAPIClient(user_id)
        
        # Define basic database properties
        properties = {
            "Name": {
                "type": "title",
                "title": {}
            },
            "Status": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": "Not started", "color": "gray"},
                        {"name": "In progress", "color": "yellow"},
                        {"name": "Completed", "color": "green"}
                    ]
                }
            },
            "Created": {
                "type": "created_time",
                "created_time": {}
            }
        }
        
        database = client.create_database(
            parent_id=parent_id,
            title=title,
            properties=properties
        )
        
        return {
            "success": True,
            "database_id": database.get("id"),
            "url": database.get("url"),
            "message": "Database created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating Notion database: {e}")
        return {"error": f"Failed to create database: {str(e)}"}


@router.get("/search")
def search_notion(user_id: str, query: str = "", filter_type: str = None):
    """Search Notion workspace"""
    try:
        client = NotionAPIClient(user_id)
        results = client.search(query=query, filter_type=filter_type)
        
        formatted_results = []
        for result in results.get("results", []):
            item = {
                "id": result.get("id"),
                "object": result.get("object"),
                "url": result.get("url"),
                "created_time": result.get("created_time"),
                "last_edited_time": result.get("last_edited_time")
            }
            
            if result.get("object") == "page":
                # Get page title
                properties = result.get("properties", {})
                for prop_name, prop_data in properties.items():
                    if prop_data.get("type") == "title":
                        title_array = prop_data.get("title", [])
                        if title_array:
                            item["title"] = title_array[0].get("plain_text", "Untitled")
                        break
                else:
                    item["title"] = "Untitled"
            
            elif result.get("object") == "database":
                # Get database title
                title_array = result.get("title", [])
                if title_array:
                    item["title"] = title_array[0].get("plain_text", "Untitled Database")
                else:
                    item["title"] = "Untitled Database"
            
            formatted_results.append(item)
        
        return {
            "results": formatted_results,
            "has_more": results.get("has_more", False),
            "next_cursor": results.get("next_cursor")
        }
        
    except Exception as e:
        logger.error(f"Error searching Notion: {e}")
        return {"error": f"Search failed: {str(e)}"}


@router.get("/page/{page_id}")
def get_page_details(user_id: str, page_id: str):
    """Get detailed information about a specific page"""
    try:
        client = NotionAPIClient(user_id)
        
        # Get page metadata
        page = client.get_page(page_id)
        
        # Get page content
        content = client.get_page_content(page_id)
        
        return {
            "page": page,
            "content": content
        }
        
    except Exception as e:
        logger.error(f"Error getting page details: {e}")
        return {"error": f"Failed to get page details: {str(e)}"}


@router.get("/database/{database_id}")
def get_database_details(user_id: str, database_id: str):
    """Get detailed information about a specific database"""
    try:
        client = NotionAPIClient(user_id)
        
        # Get database schema
        database = client.get_database(database_id)
        
        # Get database entries
        entries = client.query_database(database_id, page_size=10)
        
        return {
            "database": database,
            "entries": entries
        }
        
    except Exception as e:
        logger.error(f"Error getting database details: {e}")
        return {"error": f"Failed to get database details: {str(e)}"}


@router.post("/page/{page_id}/content")
def add_content_to_page(user_id: str, page_id: str, content: str, content_type: str = "paragraph"):
    """Add content to an existing page"""
    try:
        client = NotionAPIClient(user_id)
        
        # Create content blocks based on type
        blocks = []
        if content_type == "heading":
            blocks.append(create_heading_block(content))
        else:
            # Split content by lines for paragraphs
            lines = content.split('\n')
            for line in lines:
                if line.strip():
                    blocks.append(create_text_block(line.strip()))
        
        # Append blocks to page
        result = client.append_block_children(page_id, blocks)
        
        return {
            "success": True,
            "message": "Content added successfully",
            "blocks_added": len(blocks)
        }
        
    except Exception as e:
        logger.error(f"Error adding content to page: {e}")
        return {"error": f"Failed to add content: {str(e)}"}


@router.get("/users")
def get_workspace_users(user_id: str):
    """Get all users in the workspace"""
    try:
        client = NotionAPIClient(user_id)
        users = client.get_users()
        
        return users
        
    except Exception as e:
        logger.error(f"Error getting workspace users: {e}")
        return {"error": f"Failed to get users: {str(e)}"}