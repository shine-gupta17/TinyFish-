"""
Comment Automation Trigger Handlers
Handles keyword matching and AI decision triggers for comment automations.
"""

import logging
from typing import Dict, Any
from instagram_routers.automation_core.shared_utils import (
    check_ai_decision,
    match_keywords,
    parse_keywords
)
from instagram_routers.automation_core.constants import TriggerType, MatchType

logger = logging.getLogger(__name__)


async def handle_comment_keyword_trigger(
    comment_config: Dict[str, Any],
    comment_text: str,
    platform_user_id: str,
    comment_id: str,
    media_id: str
) -> bool:
    """
    Handle keyword-based comment trigger.
    
    Args:
        comment_config: Comment automation configuration
        comment_text: The comment text
        platform_user_id: Platform user ID
        comment_id: Comment ID
        media_id: Media/post ID
        
    Returns:
        bool: True if keyword match found
    """
    try:
        keywords = parse_keywords(comment_config.get('keywords', ''))
        match_type = comment_config.get('match_type', MatchType.CONTAINS)
        
        is_match = match_keywords(comment_text, keywords, match_type)
        
        logger.info(f"Keyword match for comment {comment_id}: {is_match}")
        return is_match
        
    except Exception as e:
        logger.error(f"Error in keyword trigger: {e}")
        return False


async def handle_comment_ai_decision_trigger(
    comment_event: Dict[str, Any],
    comment_config: Dict[str, Any],
    platform_user_id: str
) -> Dict[str, Any]:
    """
    Handle AI decision-based comment trigger.
    
    Args:
        comment_event: Full comment event data
        comment_config: Comment automation configuration
        platform_user_id: Platform user ID
        
    Returns:
        Dict with 'should_reply' (bool) and 'tokens' (int)
    """
    try:
        comment_value = comment_event.get("value", {})
        comment_text = comment_value.get("text", "")
        sender_id = comment_value.get("from", {}).get("id")
        sender_username = comment_value.get("from", {}).get("username", "unknown")
        comment_id = comment_value.get("id")
        
        if not comment_text or not sender_id or not comment_id:
            logger.warning("Missing required comment data for AI decision")
            return {"should_reply": False, "tokens": 0}
        
        ai_context_rules = comment_config.get('ai_context_rules', '')
        
        logger.info(f"Processing AI decision for comment from {sender_username}: {comment_text}")
        
        result = await check_ai_decision(
            text=comment_text,
            ai_context_rules=ai_context_rules
        )
        
        logger.info(f"AI decision result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in AI decision trigger: {e}")
        return {"should_reply": False, "tokens": 0}
