"""
AI-Powered DM Conversation Handler
Handles AI-based direct message conversations with users.
"""

import logging
from typing import Dict, Any, Optional
from supabase_client import supabase
from instagram_routers.insta_utils import send_instagram_dm
from instagram_routers.automation_tracker import update_automation_metrics_direct
from instagram_routers.automation_core.shared_utils import (
    get_provider_id,
    check_user_credits,
    pause_automation
)
from utils.supabase_utils import increment_automation_execution_count
from services.ai_assistant import AIAssistant, AIPersonality

logger = logging.getLogger(__name__)
ai_assistant = AIAssistant(personality=AIPersonality.FRIENDLY)


async def handle_ai_conversation(
    messaging_event: Dict[str, Any],
    platform_user_id: str,
    automation_config: Dict[str, Any],
    event_type: Optional[str] = None
) -> None:
    """
    Handle AI-powered conversation for DMs.
    
    Args:
        messaging_event: Messaging event data
        platform_user_id: Platform user ID
        automation_config: Automation configuration
        event_type: Type of event (user_text_message, user_image_message, user_audio_message, etc.)
    """
    try:
        sender_id = messaging_event.get("sender", {}).get("id")
        message = messaging_event.get("message", {})
        message_text = message.get("text")
        attachments = message.get("attachments", [])
        
        if not sender_id:
            logger.warning("Missing sender_id for AI conversation")
            return
        
        # Handle different event types
        if event_type in ["user_image_message", "user_audio_message", "user_attachment_message"]:
            attachment_type = attachments[0].get("type", "unknown") if attachments else "unknown"
            attachment_url = attachments[0].get("payload", {}).get("url", "") if attachments else ""
            logger.info(f"Received {attachment_type} attachment from {sender_id} for AI conversation")
            
            # For attachments without text, create a description for the AI
            if not message_text:
                if event_type == "user_image_message":
                    message_text = f"[User sent an image: {attachment_url}]"
                elif event_type == "user_audio_message":
                    message_text = f"[User sent a voice message: {attachment_url}]"
                else:
                    message_text = f"[User sent a {attachment_type} attachment: {attachment_url}]"
                logger.info(f"Created placeholder text for {event_type}: {message_text[:50]}...")
        
        if not message_text:
            logger.warning("Missing message_text for AI conversation")
            return
        
        automation_id = automation_config.get("automation_id")
        
        # Get AI conversation configuration
        ai_conv_config = await get_ai_conversation_config(automation_id)
        
        if not ai_conv_config:
            logger.error(f"No AI conversation config found for automation {automation_id}")
            return
        
        # Get provider_id for credit check
        provider_id = await get_provider_id(platform_user_id)
        
        if not provider_id:
            logger.warning(f"No provider_id found for AI conversation automation")
            return
        
        # Check if user has sufficient credits before processing
        credit_check = await check_user_credits(provider_id)
        
        if not credit_check.get("has_credits", False):
            logger.warning(
                f"Insufficient credits for provider {provider_id}. "
                f"Current credits: {credit_check.get('current_credits', 0)}. "
                f"Pausing automation {automation_id}"
            )
            await pause_automation(automation_id)
            return
        
        # Force OpenAI GPT-4o-mini for all AI conversations
        logger.info(f"Processing AI conversation using gpt-4o-mini")
        
        ai_response = await ai_assistant.process_query(
            query=message_text,
            platform="instagram",
            platform_id=platform_user_id,
            system_prompt=ai_conv_config.get("system_prompt"),
            use_rag_override=ai_conv_config.get("is_rag_enabled", False),
            model_name='gpt-4o-mini',
            model_provider='OPENAI'
        )
        
        logger.info(f"AI response generated for message: {message_text}")
        
        if ai_response and ai_response.get("answer"):
            await send_ai_dm_response(
                platform_user_id=platform_user_id,
                sender_id=sender_id,
                ai_response=ai_response,
                automation_id=automation_id
            )
        else:
            logger.warning("AI response is empty or invalid")
            
    except Exception as e:
        logger.error(f"Error in AI conversation handler: {e}", exc_info=True)


async def get_ai_conversation_config(automation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get AI conversation configuration from database.
    
    Args:
        automation_id: Automation ID
        
    Returns:
        Optional[Dict]: Configuration dict or None
    """
    try:
        ai_conv_resp = supabase.table("ai_conversations").select("*").eq(
            "automation_id", automation_id
        ).execute()
        
        if ai_conv_resp.data and len(ai_conv_resp.data) > 0:
            return ai_conv_resp.data[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching AI conversation config: {e}")
        return None


async def send_ai_dm_response(
    platform_user_id: str,
    sender_id: str,
    ai_response: Dict[str, Any],
    automation_id: str
) -> None:
    """
    Send AI-generated DM response and track metrics.
    
    Args:
        platform_user_id: Platform user ID
        sender_id: Recipient/sender ID
        ai_response: AI response dict with 'answer' and 'tokens_used'
        automation_id: Automation ID
    """
    try:
        full_answer = ai_response["answer"]
        tokens_used = ai_response.get("tokens_used", 0)
        
        # Truncate message if too long (Instagram limit)
        message_to_send = (full_answer[:997] + '...') if len(full_answer) > 1000 else full_answer
        
        # Send the DM
        result = await send_instagram_dm(
            platform_user_id=platform_user_id,
            recipient_id=sender_id,
            message_text=message_to_send
        )
        
        # Check if send was successful
        if result.get("error"):
            logger.error(f"Failed to send AI DM response to {sender_id}: {result.get('error')}")
            # Still track tokens since AI processing was done
        else:
            logger.info(f"Sent AI DM response to {sender_id}")
        
        # Increment execution count (always, even if send failed - AI processing was done)
        execution_update = increment_automation_execution_count(automation_id=automation_id)
        if execution_update:
            logger.info(f"Updated execution count for automation {automation_id}")
        
        # Track tokens if any were consumed
        if tokens_used > 0:
            provider_id = await get_provider_id(platform_user_id)
            if provider_id:
                await update_automation_metrics_direct(
                    automation_id=automation_id,
                    tokens_consumed=tokens_used,
                    provider_id=provider_id
                )
                logger.info(f"Tracked {tokens_used} tokens for AI conversation {automation_id}")
            else:
                logger.warning(f"Could not find provider_id for {platform_user_id}. Tokens not tracked.")
        
    except Exception as e:
        logger.error(f"Failed to send AI DM response: {e}", exc_info=True)
