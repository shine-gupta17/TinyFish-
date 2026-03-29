from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from supabase_client import supabase
from models.api_models import AIChatBotConfigPayload, RagStatusPayload
from utils.api_responses import APIResponse
import logging

router = APIRouter(
    prefix="/ai-chat/config",
    tags=["AI Chat Configuration"]
)

logger = logging.getLogger(__name__)

@router.get("/{platform_user_id}")
def get_ai_chat_config(platform_user_id: str) -> JSONResponse:
    """
    Fetches the combined AI chat configuration by joining ai_conversations
    with its corresponding automation record.
    """
    try:
        response = supabase.table("ai_conversations").select(
            "*, automations(*)"
        ).eq("platform_user_id", platform_user_id).maybe_single().execute()

        if not response or not response.data:
            logger.info(f"AI chat configuration not found for platform_user_id: {platform_user_id}")
            APIResponse.error(404, "AI chat configuration not found")

        return APIResponse.success(
            data=response.data,
            message="AI chat configuration fetched successfully"
        )
    except HTTPException:
        # Re-raise HTTPException so FastAPI can handle it properly
        raise
    except Exception as e:
        logger.error(f"Error getting AI config for {platform_user_id}: {e}", exc_info=True)
        APIResponse.error(500, str(e))


@router.post("")
def create_or_update_ai_chat_config(payload: AIChatBotConfigPayload) -> JSONResponse:
    """
    Creates or updates an AI DM conversation automation and its corresponding
    AI conversation settings.
    """
    # try:
    # Define the data for the automation record
    automation_data = {
        "platform": payload.platform,
        "platform_user_id": payload.platform_user_id,
        "name": payload.bot_name,
        "description": "No Desc",
        "automation_type": "AI_DM_CONVERSATION",
        "activation_status": "ACTIVE",
        "schedule_type":"CONTINUOUS",
        "model_usage": "PLATFORM_DEFAULT",
        "max_actions": None,
        "time_period_seconds": None,
        "user_cooldown_seconds": None
    }

    # Check if an AI_DM_CONVERSATION automation already exists for this user
    existing_automation = supabase.table("automations").select("automation_id").eq(
        "platform_user_id", payload.platform_user_id
    ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()

    if existing_automation and existing_automation.data:
        # If it exists, update it using the automation_id
        automation_id = existing_automation.data['automation_id']
        automation_data['automation_id'] = automation_id
        auto_response = supabase.table("automations").update(automation_data).eq(
            "automation_id", automation_id
        ).execute()
    else:
        # If it does not exist, insert it
        auto_response = supabase.table("automations").insert(automation_data).execute()

    if not auto_response.data:
        raise Exception("Failed to create or update automation record.")
        
    automation_id = auto_response.data[0]['automation_id']

    # Prepare and upsert the 'ai_conversations' record
    ai_conversation_data = {
        "automation_id": automation_id,
        "platform_user_id": payload.platform_user_id,
        "model_provider": "OPENAI",
        "model_name": payload.model_name,
        "system_prompt": payload.system_prompt,
        "temperature": payload.temperature,
        "is_rag_enabled": payload.is_rag_enabled,
        "confidence_threshold": 0.75,
    }

    convo_response = supabase.table("ai_conversations").upsert(
        ai_conversation_data,
        on_conflict="platform_user_id"
    ).execute()

    if not convo_response.data:
        raise Exception("Failed to create or update AI conversation record.")

    return APIResponse.success(
        data=convo_response.data[0],
        message="AI chat configuration saved successfully"
    )
    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.error(f"Failed to save AI chat configuration: {e}", exc_info=True)
    #     APIResponse.error(500, f"Failed to save AI chat configuration: {str(e)}")


@router.post("/{platform_user_id}/rag")
def update_rag_status(platform_user_id: str, payload: RagStatusPayload) -> JSONResponse:
    """
    Updates the RAG status for a specific AI conversation configuration.
    """
    try:
        response = supabase.table("ai_conversations").update({
            "is_rag_enabled": payload.is_rag_enabled
        }).eq("platform_user_id", platform_user_id).execute()

        if not response.data:
            return APIResponse.error(404, "Failed to update RAG status: Configuration not found.")
            
        return APIResponse.success(
            data=response.data[0],
            message="RAG status updated successfully"
        )
    except Exception as e:
        logger.error(f"Failed to update RAG status for {platform_user_id}: {e}")
        return APIResponse.error(500, f"Failed to update RAG status: {str(e)}")
