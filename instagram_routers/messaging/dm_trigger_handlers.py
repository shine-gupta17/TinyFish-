"""
DM Automation Trigger Handlers
Handles keyword matching and AI decision triggers for DM automations.
"""

import logging
from typing import Dict, Any
from instagram_routers.automation_core.shared_utils import (
    check_ai_decision,
    match_keywords,
    parse_keywords,
    generate_ai_reply
)
from instagram_routers.automation_core.constants import TriggerType, MatchType, ReplyType
from supabase_client import supabase

logger = logging.getLogger(__name__)


async def handle_dm_keyword_trigger(
    message_text: str,
    trigger_config: Dict[str, Any]
) -> bool:
    """
    Handle keyword-based DM trigger.
    
    Args:
        message_text: The DM message text
        trigger_config: DM trigger configuration
        
    Returns:
        bool: True if keyword match found
    """
    try:
        keywords = parse_keywords(trigger_config.get('keywords', ''))
        match_type = trigger_config.get('match_type', MatchType.CONTAINS)
        
        is_match = match_keywords(message_text, keywords, match_type)
        
        logger.info(f"DM keyword match: {is_match}")
        return is_match
        
    except Exception as e:
        logger.error(f"Error in DM keyword trigger: {e}")
        return False


async def handle_dm_ai_decision_trigger(
    message_text: str,
    trigger_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle AI decision-based DM trigger.
    
    Args:
        message_text: The DM message text
        trigger_config: DM trigger configuration
        
    Returns:
        Dict with 'should_reply' (bool) and 'tokens' (int)
    """
    try:
        ai_context_rules = trigger_config.get('ai_context_rules', '')
        
        logger.info(f"Processing AI decision for DM: {message_text}")
        
        result = await check_ai_decision(
            text=message_text,
            ai_context_rules=ai_context_rules
        )
        
        logger.info(f"DM AI decision result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in DM AI decision trigger: {e}")
        return {"should_reply": False, "tokens": 0}


async def generate_dm_reply_content(
    message_text: str,
    trigger_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate DM reply content based on configuration.
    
    Args:
        message_text: Original message text
        trigger_config: DM trigger configuration
        
    Returns:
        Dict with 'content' (str) and 'tokens' (int)
    """
    try:
        reply_type = trigger_config.get('reply_type', ReplyType.TEMPLATE)
        
        # HARDCODED reply type - DO NOT CHANGE
        if reply_type == ReplyType.AI_GENERATED:
            system_prompt = trigger_config.get('system_prompt', 'You are a helpful social media assistant')
            temperature = trigger_config.get('temperature', 0.7)
            
            return await generate_ai_reply(
                text=message_text,
                system_prompt=system_prompt,
                request_type="dm_reply",
                temperature=temperature
            )
        
        elif reply_type == ReplyType.TEMPLATE:
            # Return template content
            template_content = trigger_config.get('reply_template_content', '')
            return {"content": template_content, "tokens": 0}
        
        else:
            logger.warning(f"Unknown reply type: {reply_type}")
            return {"content": "", "tokens": 0}
            
    except Exception as e:
        logger.error(f"Error generating DM reply: {e}")
        return {"content": "", "tokens": 0}
