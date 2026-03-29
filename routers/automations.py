from fastapi import APIRouter
from fastapi.responses import JSONResponse
from supabase_client_async import async_supabase
from utils.api_responses import APIResponse
import logging

router = APIRouter(
    prefix="/automations",
    tags=["Manage all automations"]
)

logger = logging.getLogger(__name__)

@router.get("/get-all-automations")
async def get_all_automations(provider_id: str) -> JSONResponse:
    try:
        logger.info(f"Fetching automations for provider_id: {provider_id}")
        response = await async_supabase.select(
            "automations",
            select="*",
            filters={"platform_user_id": provider_id}
        )
        
        return APIResponse.success(
            data=response["data"] or [], 
            message="Fetched automations successfully"
        )
    except Exception as e:
        logger.error(f"Error fetching automations: {str(e)}")
        return APIResponse.error(500, str(e))

@router.get('/delete')
async def delete(platform_user_id: str, automation_id: str) -> JSONResponse:
    try:
        logger.info(f"Deleting automation: {automation_id} for user: {platform_user_id}")
        
        # For multiple filters, we'll need to do a custom query
        # First, get the automation to verify it exists
        check = await async_supabase.select(
            "automations",
            select="*",
            filters={"platform_user_id": platform_user_id}
        )
        
        # Filter in Python for automation_id
        if check["data"]:
            to_delete = [item for item in check["data"] if item.get("automation_id") == automation_id]
            if not to_delete:
                return APIResponse.error(404, "Automation not found")
        
        # Delete using the primary key if available, or both conditions
        response = await async_supabase.delete(
            "automations",
            {"automation_id": automation_id, "platform_user_id": platform_user_id}
        )
        
        return APIResponse.success(
            data=response["data"], 
            message="Deleted automation successfully"
        )
    except Exception as e:
        logger.error(f"Error deleting automation: {str(e)}")
        return APIResponse.error(500, str(e))

@router.get("/update-active")
async def update_active(platform_user_id: str, automation_id: str, activation_status: str) -> JSONResponse:
    try:
        logger.info(f"Updating automation: {automation_id} to status: {activation_status}")
        
        # For complex filters, we'll fetch and update
        check = await async_supabase.select(
            "automations",
            select="id",
            filters={"platform_user_id": platform_user_id}
        )
        
        if check["data"]:
            filtered = [item for item in check["data"] if item.get("automation_id") == automation_id]
            if not filtered:
                return APIResponse.error(404, "Automation not found")
        
        response = await async_supabase.update(
            "automations",
            {"activation_status": activation_status},
            {"automation_id": automation_id, "platform_user_id": platform_user_id}
        )
        
        return APIResponse.success(
            data=response["data"], 
            message="Updated automation successfully"
        )
    except Exception as e:
        logger.error(f"Error updating automation: {str(e)}")
        return APIResponse.error(500, str(e))

@router.get("/details/{automation_id}")
async def get_automation_details(automation_id: str, automation_type: str) -> JSONResponse:
    """
    Fetches automation-specific details from respective tables based on automation type.
    
    Automation Type -> Table Mapping:
    - AI_DM_CONVERSATION -> ai_conversations table
    - DM_REPLY -> dm_reply table
    - COMMENT_REPLY -> comment_keyword_reply table
    - PRIVATE_MESSAGE -> private_message table
    """
    try:
        table_mapping = {
            'AI_DM_CONVERSATION': 'ai_conversations',
            'DM_REPLY': 'dm_reply',
            'COMMENT_REPLY': 'comment_keyword_reply',
            'PRIVATE_MESSAGE': 'private_message'
        }
        
        table_name = table_mapping.get(automation_type)
        
        if not table_name:
            return APIResponse.error(
                message=f"Invalid automation type: {automation_type}"
            )
        
        # Fetch details from the appropriate table
        response = await async_supabase.select(
            table_name,
            select="*",
            filters={"automation_id": automation_id}
        )
        
        if response["data"] and len(response["data"]) > 0:
            return APIResponse.success(
                data=response["data"][0],
                message=f"Fetched {automation_type} details successfully"
            )
        else:
            return APIResponse.error(
                message=f"No details found for automation_id: {automation_id}"
            )
            
    except Exception as e:
        logger.error(f"Error fetching automation details: {str(e)}")
        return APIResponse.error(
            message=f"Error fetching automation details: {str(e)}"
        )
