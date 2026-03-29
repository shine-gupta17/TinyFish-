import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from supabase_client import supabase
import json
from utils.api_responses import APIResponse


logger = logging.getLogger(__name__)

async def get_access_token(platform_user_id: str) -> str:
    try:
        response = supabase.table("connected_accounts").select("access_token").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", "instagram").eq("connected", True).limit(1).maybe_single().execute()

        if not response.data or not response.data.get("access_token"):
            raise APIResponse.error(404, "Connected account or access token not found.")

        return response.data["access_token"]
    except Exception as e:
        logger.error(f"Error fetching access token for {platform_user_id}: {e}")
        raise

async def send_instagram_dm(platform_user_id: str, recipient_id: str, message_text: str) -> Dict:
    """
    Send a direct message to a user on Instagram.
    
    Args:
        platform_user_id: The platform user ID of the sender
        recipient_id: The recipient's Instagram user ID
        message_text: The message text to send
        
    Returns:
        Dict with the API response or error info
    """
    try:
        access_token = await get_access_token(platform_user_id)
        url = "https://graph.instagram.com/v23.0/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        json_data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message_text},
            "messaging_type": "RESPONSE"
        }
        
        # Use timeout to prevent hanging connections
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, headers=headers, json=json_data)
            res.raise_for_status()
            return res.json()
            
    except httpx.ConnectTimeout:
        logger.error(f"Connection timeout sending DM to {recipient_id}")
        return {"error": "Connection timeout", "success": False}
    except httpx.ReadTimeout:
        logger.error(f"Read timeout sending DM to {recipient_id}")
        return {"error": "Read timeout", "success": False}
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending DM to {recipient_id}: {e}")
        return {"error": f"Timeout: {str(e)}", "success": False}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending DM to {recipient_id}: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}", "success": False}
    except Exception as e:
        logger.error(f"Error sending DM to {recipient_id}: {e}")
        return {"error": str(e), "success": False}


async def send_message_template(platform_user_id: str, recipient_id: str, message_template: Any):
    """
    Send a message template to a user on Instagram.
    
    Args:
        platform_user_id: The platform user ID of the sender
        recipient_id: The recipient's Instagram user ID
        message_template: The message template (dict or JSON string)
        
    Returns:
        Dict with the API response or error info
    """
    try:
        # Parse string to dict if needed
        if isinstance(message_template, str):
            message_template = json.loads(message_template)

        access_token = await get_access_token(platform_user_id)
        url = "https://graph.instagram.com/v23.0/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}

        json_data = {
            "recipient": {"id": recipient_id},
            "message": message_template["message"],
            "messaging_type": "RESPONSE"
        }

        # Use timeout to prevent hanging connections
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, headers=headers, json=json_data)
            res.raise_for_status()
            return res.json()
            
    except httpx.ConnectTimeout:
        logger.error(f"Connection timeout sending template to {recipient_id}")
        return {"error": "Connection timeout", "success": False}
    except httpx.ReadTimeout:
        logger.error(f"Read timeout sending template to {recipient_id}")
        return {"error": "Read timeout", "success": False}
    except httpx.TimeoutException as e:
        logger.error(f"Timeout sending template to {recipient_id}: {e}")
        return {"error": f"Timeout: {str(e)}", "success": False}
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending template to {recipient_id}: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTP {e.response.status_code}", "success": False}
    except Exception as e:
        logger.error(f"Error sending template to {recipient_id}: {e}")
        return {"error": str(e), "success": False}
    

def upsert_instagram_account(provider_id: str, token: str, expires_in: int, user_id: str, username: str):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    # Delete existing record if any
    supabase.table("connected_accounts")\
        .delete()\
        .eq("platform_user_id", user_id)\
        .eq("platform", "instagram")\
        .execute()
    
    # Insert new record
    data = {
        "provider_id": provider_id, "platform": "instagram", "platform_user_id": user_id,
        "platform_username": username, "access_token": token, "token_expires_at": expires_at.isoformat(),
        "connected": True, "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return supabase.table("connected_accounts").insert(data).execute()
