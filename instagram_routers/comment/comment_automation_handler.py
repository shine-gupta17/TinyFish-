"""
Comment Automation Handler (Refactored)
Main handler for processing comment automation events.
Uses new modular structure with shared utilities.
"""

import logging
from typing import Dict, Any
from supabase_client import supabase
from instagram_routers.automation_core.automation_processor import automation_processor
from instagram_routers.automation_core.shared_utils import (
    check_post_selection,
    generate_ai_reply,
    get_provider_id,
    check_user_credits,
    pause_automation
)
from instagram_routers.automation_core.constants import (
    AutomationType,
    TriggerType,
    ReplyType
)
from instagram_routers.comment.comment_trigger_handlers import (
    handle_comment_keyword_trigger,
    handle_comment_ai_decision_trigger
)
from routers.instagram_user_data import reply_to_comment, send_dm_from_comment
from utils.supabase_utils import increment_automation_execution_count
from instagram_routers.automation_tracker import update_automation_metrics_direct

logger = logging.getLogger(__name__)


async def handle_comment_automation(
    comment_event: Dict[str, Any],
    automation: Dict[str, Any],
    platform_user_id: str
) -> None:
    """
    Main handler for comment automation events.
    
    Args:
        comment_event: Comment event data from webhook
        automation: Automation configuration
        platform_user_id: Instagram platform user ID
    """
    try:
        # Extract comment data
        comment_value = comment_event.get("value", {})
        comment_text = comment_value.get("text", "")
        sender_id = comment_value.get("from", {}).get("id")
        sender_username = comment_value.get("from", {}).get("username", "unknown")
        comment_id = comment_value.get("id")
        media_id = comment_value.get("media", {}).get("id")
        
        # Validate sender
        if not sender_id or platform_user_id == sender_id:
            logger.info("Skipping comment from self or missing sender")
            return
        
        automation_type = automation.get('automation_type')
        
        # Route to appropriate handler based on automation type - HARDCODED
        if automation_type == AutomationType.COMMENT_REPLY:
            await process_comment_reply_automation(
                comment_event, automation, platform_user_id,
                comment_text, sender_id, comment_id, media_id
            )
        
        elif automation_type == AutomationType.PRIVATE_MESSAGE:
            await process_private_message_automation(
                comment_event, automation, platform_user_id,
                comment_text, sender_id, comment_id, media_id
            )
        
    except Exception as e:
        logger.error(f"Error in comment automation handler: {e}", exc_info=True)


async def process_comment_reply_automation(
    comment_event: Dict[str, Any],
    automation: Dict[str, Any],
    platform_user_id: str,
    comment_text: str,
    sender_id: str,
    comment_id: str,
    media_id: str
) -> None:
    """Process COMMENT_REPLY automation type."""
    try:
        # Check execution limits
        if automation.get('max_actions'):
            if automation.get('execution_count', 0) >= automation.get('max_actions'):
                logger.info(f"Automation {automation.get('automation_id')} reached max actions")
                return
        
        # Get comment automation config
        comment_config = await automation_processor.get_automation_config(
            automation_id=automation.get('automation_id'),
            config_table="comment_keyword_reply"
        )
        
        if not comment_config:
            logger.error(f"No config found for comment automation {automation.get('automation_id')}")
            return
        
        # Get provider_id for credit check
        provider_id = await get_provider_id(platform_user_id, config=comment_config)
        
        if not provider_id:
            logger.warning(f"No provider_id found for comment automation")
            return
        
        # Check if user has sufficient credits before processing
        credit_check = await check_user_credits(provider_id)
        
        if not credit_check.get("has_credits", False):
            logger.warning(
                f"Insufficient credits for provider {provider_id}. "
                f"Current credits: {credit_check.get('current_credits', 0)}. "
                f"Pausing automation {automation.get('automation_id')}"
            )
            await pause_automation(automation.get('automation_id'))
            return
        
        # Check post selection
        post_selection_type = comment_config.get('post_selection_type')
        specific_post_ids = comment_config.get('specific_post_ids', [])
        
        if not check_post_selection(media_id, post_selection_type, specific_post_ids):
            logger.info(f"Post {media_id} does not match selection criteria")
            return
        
        # Determine if should reply
        should_reply = False
        ai_decision_tokens = 0
        trigger_type = comment_config.get('trigger_type')
        
        # HARDCODED trigger types - DO NOT CHANGE
        if trigger_type == TriggerType.KEYWORD:
            should_reply = await handle_comment_keyword_trigger(
                comment_config, comment_text, platform_user_id, comment_id, media_id
            )
            logger.info(f"Keyword trigger result: {should_reply}")
        
        elif trigger_type == TriggerType.AI_DECISION:
            ai_result = await handle_comment_ai_decision_trigger(
                comment_event, comment_config, platform_user_id
            )
            should_reply = ai_result.get("should_reply", False)
            ai_decision_tokens = ai_result.get("tokens", 0)
            logger.info(f"AI decision trigger result: {should_reply}, tokens: {ai_decision_tokens}")
        
        # Generate and send reply
        reply_generation_tokens = 0
        
        if should_reply:
            reply_text = await generate_comment_reply_text(
                comment_text, comment_config
            )
            
            if isinstance(reply_text, dict):
                reply_content = reply_text.get("content", "")
                reply_generation_tokens = reply_text.get("tokens", 0)
            else:
                reply_content = reply_text
            
            if reply_content and reply_content.strip():
                resp = await reply_to_comment(
                    comment_id=comment_id,
                    message=reply_content,
                    platform_user_id=platform_user_id
                )
                
                if resp.status_code == 200:
                    logger.info(f"Successfully replied to comment {comment_id}")
                    
                    # Track execution and tokens
                    total_tokens = ai_decision_tokens + reply_generation_tokens
                    await track_comment_automation_metrics(
                        automation, comment_config, platform_user_id, total_tokens
                    )
                else:
                    logger.error(f"Failed to reply to comment: {resp.status_code}")
        else:
            # Track AI decision tokens even when not replying
            if ai_decision_tokens > 0:
                await track_comment_automation_metrics(
                    automation, comment_config, platform_user_id, ai_decision_tokens
                )
    
    except Exception as e:
        logger.error(f"Error processing comment reply automation: {e}", exc_info=True)


async def process_private_message_automation(
    comment_event: Dict[str, Any],
    automation: Dict[str, Any],
    platform_user_id: str,
    comment_text: str,
    sender_id: str,
    comment_id: str,
    media_id: str
) -> None:
    """Process PRIVATE_MESSAGE automation type (sends DM based on comment)."""
    try:
        # Check execution limits
        if automation.get('max_actions'):
            if automation.get('execution_count', 0) >= automation.get('max_actions'):
                logger.info(f"Automation {automation.get('automation_id')} reached max actions")
                return
        
        # Get private message config
        pm_config = await automation_processor.get_automation_config(
            automation_id=automation.get('automation_id'),
            config_table="private_message"
        )
        
        if not pm_config:
            logger.error(f"No config found for private message automation {automation.get('automation_id')}")
            return
        
        # Get provider_id for credit check
        provider_id = await get_provider_id(platform_user_id, config=pm_config)
        
        if not provider_id:
            logger.warning(f"No provider_id found for private message automation")
            return
        
        # Check if user has sufficient credits before processing
        credit_check = await check_user_credits(provider_id)
        
        if not credit_check.get("has_credits", False):
            logger.warning(
                f"Insufficient credits for provider {provider_id}. "
                f"Current credits: {credit_check.get('current_credits', 0)}. "
                f"Pausing automation {automation.get('automation_id')}"
            )
            await pause_automation(automation.get('automation_id'))
            return
        
        # Check post selection
        post_selection_type = pm_config.get('post_selection_type')
        specific_post_ids = pm_config.get('specific_post_ids', [])
        
        if not check_post_selection(media_id, post_selection_type, specific_post_ids):
            logger.info(f"Post {media_id} does not match selection criteria")
            return
        
        # Determine if should send DM
        should_reply = False
        ai_decision_tokens = 0
        trigger_type = pm_config.get('trigger_type')
        
        # HARDCODED trigger types - DO NOT CHANGE
        if trigger_type == TriggerType.KEYWORD:
            should_reply = await handle_comment_keyword_trigger(
                pm_config, comment_text, platform_user_id, comment_id, media_id
            )
            logger.info(f"Keyword trigger for PM: {should_reply}")
        
        elif trigger_type == TriggerType.AI_DECISION:
            ai_result = await handle_comment_ai_decision_trigger(
                comment_event, pm_config, platform_user_id
            )
            should_reply = ai_result.get("should_reply", False)
            ai_decision_tokens = ai_result.get("tokens", 0)
            logger.info(f"AI decision trigger for PM: {should_reply}, tokens: {ai_decision_tokens}")
        
        # Generate and send DM
        dm_tokens = 0
        
        if should_reply:
            # Generate AI-based DM message
            system_prompt = pm_config.get('system_prompt', 'You are a helpful and engaging social media assistant')
            temperature = pm_config.get('temperature', 0.7)
            
            dm_result = await generate_ai_reply(
                text=comment_text,
                system_prompt=system_prompt,
                request_type="dm_reply",
                temperature=temperature
            )
            
            dm_message = dm_result.get("content", "")
            dm_tokens = dm_result.get("tokens", 0)
            
            if not dm_message or dm_message.strip() == "":
                logger.warning("AI failed to generate DM, using fallback")
                dm_message = "Thanks for your comment! 😊"
            
            # Send DM
            resp = await send_dm_from_comment(
                platform_user_id=platform_user_id,
                comment_id=comment_id,
                message_type="text",
                message=dm_message
            )
            
            if resp:
                logger.info(f"Successfully sent DM for comment {comment_id}")
                
                # Track execution and tokens
                total_tokens = ai_decision_tokens + dm_tokens
                await track_comment_automation_metrics(
                    automation, pm_config, platform_user_id, total_tokens
                )
            else:
                logger.error("Failed to send DM")
        else:
            # Track AI decision tokens even when not sending DM
            if ai_decision_tokens > 0:
                await track_comment_automation_metrics(
                    automation, pm_config, platform_user_id, ai_decision_tokens
                )
    
    except Exception as e:
        logger.error(f"Error processing private message automation: {e}", exc_info=True)


async def generate_comment_reply_text(
    comment_text: str,
    comment_config: Dict[str, Any]
) -> Any:
    """Generate reply text based on reply type."""
    try:
        reply_type = comment_config.get('reply_type', ReplyType.CUSTOM).lower()
        
        # HARDCODED reply types - DO NOT CHANGE
        if reply_type == "custom":
            custom_reply = comment_config.get('custom_reply')
            return {"content": custom_reply if custom_reply else ":)", "tokens": 0}
        
        elif reply_type == "ai_decision":
            system_prompt = comment_config.get('system_prompt', 'Reply to this comment in a friendly manner')
            temperature = comment_config.get('temperature', 0.7)
            
            return await generate_ai_reply(
                text=comment_text,
                system_prompt=system_prompt,
                request_type="comment_reply",
                temperature=temperature
            )
        
        return {"content": "", "tokens": 0}
        
    except Exception as e:
        logger.error(f"Error generating comment reply text: {e}")
        return {"content": "", "tokens": 0}


async def track_comment_automation_metrics(
    automation: Dict[str, Any],
    config: Dict[str, Any],
    platform_user_id: str,
    tokens_consumed: int
) -> None:
    """Track execution count and token consumption."""
    try:
        automation_id = automation.get('automation_id')
        
        # Increment execution count
        increment_automation_execution_count(automation_id=automation_id)
        
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
        logger.error(f"Error tracking metrics: {e}", exc_info=True)
