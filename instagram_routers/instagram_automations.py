from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from supabase_client import supabase
from models.api_models import DmKeywordReplyAutomationPayload, AIChatBotConfigPayload
from models.comment_reply_model import CommentReplyPayload #
from models.private_message import PrivateReply
from utils.api_responses import APIResponse
import logging
import asyncio
from services.email_triggers import email_trigger_by_provider

router = APIRouter(
    prefix="/instagram/automations",
    tags=["Instagram Automations"]
)

logger = logging.getLogger(__name__)


@router.post("/comment-reply", status_code=201)
async def create_or_update_comment_reply_automation(payload: CommentReplyPayload) -> JSONResponse:
    # try:
    logger.info(f"Creating/updating comment reply automation - Payload: {payload}")
    automation_param = {
        "platform": payload.platform,
        "platform_user_id": payload.platform_user_id,
        "name": payload.name,
        "description": payload.description if payload.description is not None else "No Desc",
        "automation_type": "COMMENT_REPLY",
        "activation_status": "ACTIVE",
        "model_usage": "PLATFORM_DEFAULT",
        "schedule_type":"CONTINUOUS",
        "execution_count": 0,
        "max_actions": payload.max_actions,
        "time_period_seconds": payload.time_period_seconds,
        "user_cooldown_seconds": payload.user_cooldown_seconds
    }

    if payload.automation_id:
        automation_param["automation_id"] = str(payload.automation_id)

    automation_response = supabase.table("automations").upsert(automation_param).execute()
    automation_id = automation_response.data[0]['automation_id']

    comment_reply_data = {
        "automation_id": automation_id,  # already string
        "platform_user_id": payload.platform_user_id,
        "provider_id": str(payload.provider_id),
        "post_selection_type": payload.post_selection_type,
        "specific_post_ids": payload.specific_post_ids,
        "date_range": payload.dateRange, 
        "trigger_type": payload.trigger_type,
        "keywords": payload.keywords,
        "match_type": payload.match_type,
        "ai_context_rules": payload.ai_context_rules,
        "system_prompt": payload.system_prompt,
        "custom_reply":payload.custom_message,
        "reply_type":payload.reply_type,
        "comment_reply_template_type": payload.comment_reply_template_type,
        "max_replies_per_post": payload.max_replies_per_post,
        "reply_count_condition": payload.reply_count_condition,
        "reply_count_value": payload.reply_count_value,
        "model_provider": payload.model_provider,
        "model_name": payload.model_name,
        "temperature": payload.temperature,
        "is_rag_enabled": payload.is_rag_enabled,
        "confidence_threshold": payload.confidence_threshold
    }

    if getattr(payload, "rule_id", None):
        comment_reply_data["rule_id"] = str(payload.rule_id)
    resp = supabase.table("comment_keyword_reply").upsert(comment_reply_data, on_conflict=["automation_id"]).execute()
    logger.info(f"Comment reply automation saved - Response: {resp}")

    # ✅ Send automation creation email to user (logged-in user's email from database)
    asyncio.create_task(
        email_trigger_by_provider.send_automation_created_notification(
            provider_id=str(payload.provider_id),
            automation_name=payload.name,
            automation_type="COMMENT_REPLY",
            credits_per_execution=100
        )
    )

    return APIResponse.success(
        data=resp.data,
        message="Comment reply automation saved successfully"
    )
    # except Exception as e:
    #     return APIResponse.error(422, f"Failed to save comment reply automation: {e.errors() if hasattr(e, 'errors') else str(e)}")

@router.post("/private-message")
async def post_private_message(payload:PrivateReply)->JSONResponse:
    logger.info(f"Creating private message automation - Payload: {payload}")
    automation_param = {
        "platform": "instagram",
        "platform_user_id": payload.platform_user_id,
        "name": payload.name,
        "description": payload.description if payload.description is not None else "No Desc",
        "automation_type": "PRIVATE_MESSAGE",
        "activation_status": "ACTIVE",
        "model_usage": "PLATFORM_DEFAULT",
        "schedule_type":"CONTINUOUS",
        "execution_count": 0,
        "max_actions": payload.max_actions,
        "time_period_seconds": payload.time_period_seconds,
        "user_cooldown_seconds": payload.user_cooldown_seconds
    }

    # if payload.automation_id:
    #     automation_param["automation_id"] = str(payload.automation_id)

    automation_response = supabase.table("automations").upsert(automation_param).execute()
    automation_id = automation_response.data[0]['automation_id']

   # New dictionary for the private_message table
    private_message_param = {
        "automation_id": automation_id,
        "platform_user_id": payload.platform_user_id,
        "provider_id": payload.provider_id,
        "post_selection_type": payload.post_selection_type,
        "specific_post_ids": payload.specific_post_ids,
        "date_range": payload.date_range,
        "trigger_type": payload.trigger_type,
        "keywords": payload.keywords,
        "match_type": payload.match_type,
        "ai_context_rules": payload.ai_context_rules,
        "system_prompt": payload.system_prompt,
        "reply_template_type": payload.reply_template_type,
        "reply_template_content": payload.reply_template_content,
        "model_provider": payload.model_provider,
        "model_name": payload.model_name,
        "temperature": payload.temperature,
        "is_rag_enabled": payload.is_rag_enabled,
        "confidence_threshold": payload.confidence_threshold,
        "model_usage": payload.model_usage,
        "schedule_type": payload.schedule_type,
        "max_actions": payload.max_actions,
        "time_period_seconds": payload.time_period_seconds,
        "user_cooldown_seconds": payload.user_cooldown_seconds,
    }
    private_message_response = supabase.table("private_message").upsert(private_message_param).execute()
    
    # ✅ Send automation creation email to user
    asyncio.create_task(
        email_trigger_by_provider.send_automation_created_notification(
            provider_id=str(payload.provider_id),
            automation_name=payload.name,
            automation_type="PRIVATE_MESSAGE",
            credits_per_execution=150
        )
    )
    
    return APIResponse.success(
        data=private_message_param,
        message="Automation and private message rule created successfully"
    )


@router.get("/comment-reply", status_code=200)
def get_comment_reply_automations(platform_user_id: str = Query(...)) -> JSONResponse:
    try:
        # Fetch automations of type 'COMMENT_REPLY'
        automations_response = supabase.table("automations").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("automation_type", "COMMENT_REPLY").execute()

        formatted_data = []
        if automations_response.data:
            automation_ids = [auto['automation_id'] for auto in automations_response.data]
            
            # Fetch corresponding comment_keyword_reply data for all automation_ids
            comment_replies_response = supabase.table("comment_keyword_reply").select("*").in_(
                "automation_id", automation_ids
            ).execute()
            
            comment_reply_map = {item['automation_id']: item for item in comment_replies_response.data}

            for auto in automations_response.data:
                comment_reply_data = comment_reply_map.get(auto['automation_id'])
                if comment_reply_data:
                    merged_data = {**auto, **comment_reply_data}
                    formatted_data.append(merged_data)

        return APIResponse.success(
            data=formatted_data,
            message="Successfully fetched comment reply automations"
        )
    except Exception as e:
        logger.error(f"Error during get_comment_reply_automations: {e}")
        return APIResponse.error(500, f"Failed to fetch automations: {str(e)}")



@router.post("/dm-keyword-reply", status_code=201)
async def create_or_update_dm_keyword_automation(payload: DmKeywordReplyAutomationPayload) -> JSONResponse:
    # try:
    automation_param = {
        "platform": payload.platform,
        "platform_user_id": payload.platform_user_id,
        "name": payload.name,
        "description": payload.description,
        "automation_type": "DM_REPLY",
        "activation_status": "ACTIVE",
        "model_usage": payload.model_usage,
        "schedule_type":"CONTINUOUS",
        "execution_count": 0, # Hardcoded to None
        "max_actions": None, # Hardcoded to None
        "time_period_seconds": None, # Hardcoded to None
        "user_cooldown_seconds": payload.user_cooldown_seconds
    }

    logger.info(f"Processing automation with ID: {payload.automation_id}")

    if payload.automation_id:
        automation_param["automation_id"] = str(payload.automation_id)

    automation_response = supabase.table("automations").upsert(automation_param).execute()
    automation_id = automation_response.data[0]['automation_id']


    logger.debug(f"Keywords for automation: {','.join(payload.keywords)}")


    supabase.table('dm_reply').upsert({
        "automation_id": automation_id,
        "platform_user_id": payload.platform_user_id,
        "provider_id": payload.provider_id,
        "trigger_type": payload.trigger_type,
        "keywords": ','.join(payload.keywords),
        "match_type": payload.match_type.upper(),
        "ai_context_rules": payload.ai_context_rules,
        "reply_template_type": payload.reply_template_type,
        "reply_template_content": payload.reply_template_content
    }).execute()

    # ✅ Send automation creation email to user (logged-in user's email from database)
    asyncio.create_task(
        email_trigger_by_provider.send_automation_created_notification(
            provider_id=str(payload.provider_id),
            automation_name=payload.name,
            automation_type="DM_KEYWORD_REPLY",
            credits_per_execution=120
        )
    )

    return APIResponse.success(
        data={"automation_id": automation_id},
        message="DM keyword reply automation saved successfully"
    )
    # except Exception as e:
    #     return APIResponse.error(500, f"Failed to save DM keyword reply automation: {str(e)}")


@router.get("/dm-keyword-reply")
def get_dm_keyword_automations(platform_user_id: str = Query(...)) -> JSONResponse:
    # try:
        automations_response = supabase.table("automations").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("automation_type", "DM_REPLY").execute()

        formatted_data = []
        if automations_response.data:
            for auto in automations_response.data:
                dm_reply_response = supabase.table("dm_reply").select("*").eq(
                    "automation_id", auto['automation_id']
                ).single().execute()

                if dm_reply_response.data:
                    # Merge automation data with dm_reply data
                    merged_data = {**auto, **dm_reply_response.data}
                    # Remove the fields that are no longer in DM_REPLY from the merged data if they exist in `auto`
                    merged_data.pop('post_selection_type', None)
                    merged_data.pop('specific_post_ids', None)
                    merged_data.pop('reply_after_date', None)
                    merged_data.pop('reply_before_date', None)
                    # No need to remove max_actions or time_period_seconds from merged_data if they are already hardcoded to None in upsert
                    formatted_data.append(merged_data)

        return APIResponse.success(
            data=formatted_data,
            message="Successfully fetched DM keyword reply automations"
        )
    # except Exception as e:
    #     return APIResponse.error(500, f"Failed to fetch automations: {str(e)}")


@router.post("/ai-chatbot", status_code=201)
def create_or_update_ai_chatbot(payload: AIChatBotConfigPayload) -> JSONResponse:
    """
    Creates or updates an AI chatbot automation for Instagram DM conversations.
    This endpoint follows the same pattern as other Instagram automations.
    """
    try:
        # Define the data for the automation record
        automation_param = {
            "platform": payload.platform,
            "platform_user_id": payload.platform_user_id,
            "name": payload.bot_name,
            "description": "AI Chatbot for Instagram DMs",
            "automation_type": "AI_DM_CONVERSATION",
            "activation_status": "ACTIVE" if payload.is_active else "INACTIVE",
            "schedule_type": "CONTINUOUS",
            "model_usage": "PLATFORM_DEFAULT",
            "execution_count": 0,
            "max_actions": None,
            "time_period_seconds": None,
            "user_cooldown_seconds": None
        }

        # Check if an AI_DM_CONVERSATION automation already exists for this user
        existing_automation = supabase.table("automations").select("automation_id").eq(
            "platform_user_id", payload.platform_user_id
        ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()

        if existing_automation and existing_automation.data:
            # If it exists, update it
            automation_id = existing_automation.data['automation_id']
            automation_param['automation_id'] = automation_id
            automation_response = supabase.table("automations").update(automation_param).eq(
                "automation_id", automation_id
            ).execute()
        else:
            # If it does not exist, insert it
            automation_response = supabase.table("automations").insert(automation_param).execute()

        if not automation_response.data:
            raise Exception("Failed to create or update automation record.")
            
        automation_id = automation_response.data[0]['automation_id']

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
            raise Exception("Failed to create or update AI conversation settings.")

        return APIResponse.success(
            data={
                "automation_id": automation_id,
                "ai_conversation": convo_response.data[0]
            },
            message="AI chatbot automation saved successfully"
        )

    except Exception as e:
        return APIResponse.error(500, f"Failed to save AI chatbot automation: {str(e)}")


@router.get("/ai-chatbot")
def get_ai_chatbot(platform_user_id: str = Query(...)) -> JSONResponse:
    """
    Fetches the AI chatbot configuration by joining ai_conversations with its corresponding automation record.
    """
    try:
        # Fetch automation of type 'AI_DM_CONVERSATION'
        automation_response = supabase.table("automations").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()

        if not automation_response.data:
            return APIResponse.success(
                data=None,
                message="AI chatbot not configured for this user"
            )

        automation_id = automation_response.data['automation_id']

        # Fetch corresponding ai_conversations data
        ai_convo_response = supabase.table("ai_conversations").select("*").eq(
            "automation_id", automation_id
        ).maybe_single().execute()

        if ai_convo_response.data:
            # Merge automation data with ai_conversations data
            merged_data = {**automation_response.data, **ai_convo_response.data}
        else:
            merged_data = automation_response.data

        return APIResponse.success(
            data=merged_data,
            message="AI chatbot configuration fetched successfully"
        )

    except Exception as e:
        return APIResponse.error(500, f"Failed to fetch AI chatbot: {str(e)}")


@router.post("/admin/check-and-deactivate-on-low-credits")
async def admin_check_and_deactivate(provider_id: str = Query(...)) -> JSONResponse:
    """
    Admin endpoint to check credits and deactivate all Instagram automations if needed.
    This endpoint is useful for testing and manual intervention.
    
    Args:
        provider_id: Provider ID to check
        
    Returns:
        JSONResponse with credit status and deactivation details
    """
    try:
        from automation_core.shared_utils import check_user_credits, deactivate_all_instagram_automations
        
        # Check current credits
        credit_status = await check_user_credits(provider_id)
        
        # Manual deactivation if credits are below 0
        deactivation_result = None
        if credit_status.get('current_credits', 0) < 0:
            deactivation_result = await deactivate_all_instagram_automations(provider_id)
        
        return APIResponse.success(
            data={
                "provider_id": provider_id,
                "credit_status": credit_status,
                "deactivation_performed": deactivation_result is not None,
                "deactivation_result": deactivation_result
            },
            message="Credit check and deactivation completed"
        )
        
    except Exception as e:
        logger.error(f"Error in admin check and deactivate: {e}")
        return APIResponse.error(500, f"Failed to check and deactivate: {str(e)}")