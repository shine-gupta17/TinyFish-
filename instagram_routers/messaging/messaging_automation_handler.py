"""
DM/Messaging Automation Handler (Refactored)
Main handler for processing DM automation events.
Uses new modular structure with shared utilities.
"""

import logging
from typing import Dict, Any, Optional
from supabase_client import supabase
from instagram_routers.automation_core.automation_processor import automation_processor
from instagram_routers.automation_core.shared_utils import (
    get_provider_id,
    check_user_credits,
    pause_automation
)
from instagram_routers.automation_core.constants import AutomationType, TriggerType
from instagram_routers.messaging.dm_trigger_handlers import (
    handle_dm_keyword_trigger,
    handle_dm_ai_decision_trigger,
    generate_dm_reply_content
)
from instagram_routers.messaging.dm_ai_conversation_handler import handle_ai_conversation
from instagram_routers.insta_utils import send_instagram_dm, send_message_template
from instagram_routers.automation_tracker import update_automation_metrics_direct
from utils.supabase_utils import increment_automation_execution_count
import json

logger = logging.getLogger(__name__)


async def handle_messaging_automation(
    messaging_event: Dict[str, Any],
    automation: Dict[str, Any],
    platform_user_id: str,
    event_type: Optional[str] = None
) -> None:
    """
    Main handler for DM/messaging automation events.
    
    Args:
        messaging_event: Messaging event data from webhook
        automation: Automation configuration
        platform_user_id: Instagram platform user ID
        event_type: Type of event (user_text_message, user_image_message, user_audio_message, etc.)
    """
    try:
        # Extract sender info
        sender_id = messaging_event.get("sender", {}).get("id")
        
        # Validate sender
        if not sender_id or platform_user_id == sender_id:
            logger.info("Skipping DM from self or missing sender")
            return
        
        # Log the event type for debugging
        logger.info(f"Processing messaging event type: {event_type} from sender: {sender_id}")
        
        automation_type = automation.get('automation_type')
        
        # Route to appropriate handler based on automation type - HARDCODED
        if automation_type == AutomationType.DM_REPLY:
            await process_dm_reply_automation(
                messaging_event, automation, platform_user_id, sender_id, event_type
            )
        
        elif automation_type == AutomationType.AI_DM_CONVERSATION:
            await handle_ai_conversation(
                messaging_event, platform_user_id, automation, event_type
            )
        
    except Exception as e:
        logger.error(f"Error in messaging automation handler: {e}", exc_info=True)


async def process_dm_reply_automation(
    messaging_event: Dict[str, Any],
    automation: Dict[str, Any],
    platform_user_id: str,
    sender_id: str,
    event_type: Optional[str] = None
) -> None:
    """Process DM_REPLY automation type (keyword or AI-based reply).
    
    Args:
        messaging_event: Messaging event data from webhook
        automation: Automation configuration
        platform_user_id: Instagram platform user ID
        sender_id: ID of the message sender
        event_type: Type of event (user_text_message, user_image_message, user_audio_message, etc.)
    """
    try:
        message = messaging_event.get("message", {})
        message_text = message.get("text", "").strip()
        attachments = message.get("attachments", [])
        
        # Handle different event types
        if event_type in ["user_image_message", "user_audio_message", "user_attachment_message"]:
            # For attachments, we might want to handle differently or skip
            attachment_type = attachments[0].get("type", "unknown") if attachments else "unknown"
            attachment_url = attachments[0].get("payload", {}).get("url", "") if attachments else ""
            logger.info(f"Received {attachment_type} attachment from {sender_id}: {attachment_url[:50]}...")
            
            # For now, only process text messages for DM_REPLY automation
            # You can extend this to handle images/audio in the future
            if not message_text:
                logger.info(f"Skipping {event_type} - DM_REPLY only handles text messages")
                return
        
        if not message_text:
            logger.info("No message text in DM event")
            return
        
        automation_id = automation.get('automation_id')
        
        # Get DM reply config
        dm_config = await automation_processor.get_automation_config(
            automation_id=automation_id,
            config_table="dm_reply"
        )
        
        if not dm_config:
            logger.error(f"No config found for DM automation {automation_id}")
            return
        
        # Get provider_id for credit check
        provider_id = await get_provider_id(platform_user_id, config=dm_config)
        
        if not provider_id:
            logger.warning(f"No provider_id found for DM automation")
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
        
        # Determine if should reply
        should_reply = False
        ai_decision_tokens = 0
        trigger_type = dm_config.get('trigger_type', TriggerType.KEYWORD).upper()
        
        logger.info(f"DM trigger type: {trigger_type}")
        
        # HARDCODED trigger types - DO NOT CHANGE
        if trigger_type == TriggerType.KEYWORD:
            should_reply = await handle_dm_keyword_trigger(
                message_text, dm_config
            )
            logger.info(f"Keyword trigger result: {should_reply}")
        
        elif trigger_type == TriggerType.AI_DECISION:
            ai_result = await handle_dm_ai_decision_trigger(
                message_text, dm_config
            )
            should_reply = ai_result.get("should_reply", False)
            ai_decision_tokens = ai_result.get("tokens", 0)
            logger.info(f"AI decision trigger result: {should_reply}, tokens: {ai_decision_tokens}")
        
        # Generate and send reply
        reply_tokens = 0
        
        if should_reply:
            # Generate reply content
            reply_result = await generate_dm_reply_content(message_text, dm_config)
            reply_content = reply_result.get("content", "")
            reply_tokens = reply_result.get("tokens", 0)
            
            if reply_content and reply_content.strip():
                # Check if it's a template or text
                reply_type = dm_config.get('reply_type', 'TEMPLATE')
                
                if reply_type == 'AI_GENERATED':
                    # Send as text message
                    await send_instagram_dm(
                        platform_user_id=platform_user_id,
                        recipient_id=sender_id,
                        message_text=reply_content
                    )
                    logger.info(f"Sent AI-generated DM reply to {sender_id}")
                
                else:
                    # Send as template
                    template_content = dm_config.get("reply_template_content", {})
                    
                    # Parse if string
                    if isinstance(template_content, str):
                        try:
                            template_content = json.loads(template_content)
                        except:
                            logger.error("Failed to parse template content")
                            template_content = {"message": {"text": reply_content}}
                    
                    await send_message_template(
                        platform_user_id, sender_id, template_content
                    )
                    logger.info(f"Sent template DM reply to {sender_id}")
                
                # Track execution and tokens
                total_tokens = ai_decision_tokens + reply_tokens
                await track_dm_automation_metrics(
                    automation, dm_config, platform_user_id, total_tokens
                )
            else:
                logger.warning("Generated reply content is empty")
        else:
            # Track AI decision tokens even when not replying
            if ai_decision_tokens > 0:
                await track_dm_automation_metrics(
                    automation, dm_config, platform_user_id, ai_decision_tokens
                )
    
    except Exception as e:
        logger.error(f"Error processing DM reply automation: {e}", exc_info=True)


async def track_dm_automation_metrics(
    automation: Dict[str, Any],
    config: Dict[str, Any],
    platform_user_id: str,
    tokens_consumed: int
) -> None:
    """Track execution count and token consumption for DM automations."""
    try:
        automation_id = automation.get('automation_id')
        
        # Increment execution count
        increment_automation_execution_count(automation_id=automation_id)
        logger.info(f"Incremented execution count for automation {automation_id}")
        
        # Track tokens if consumed
        if tokens_consumed > 0:
            provider_id = await get_provider_id(platform_user_id, config=config)
            
            if provider_id:
                await update_automation_metrics_direct(
                    automation_id=automation_id,
                    tokens_consumed=tokens_consumed,
                    provider_id=provider_id
                )
                logger.info(f"Tracked {tokens_consumed} tokens for automation {automation_id}")
            else:
                logger.warning("No provider_id found for token tracking")
    
    except Exception as e:
        logger.error(f"Error tracking DM metrics: {e}", exc_info=True)
