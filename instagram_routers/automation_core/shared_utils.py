"""
Shared Utilities for Instagram Automations
Reusable functions for keyword matching, AI decisions, token tracking, and more.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from supabase_client import supabase
from agentic.agentic_utils import AIResponser
from .constants import MatchType, TriggerType, ModelConfig

logger = logging.getLogger(__name__)
ai_responser = AIResponser()


# ==================== KEYWORD MATCHING UTILITIES ====================

def match_keywords(
    text: str,
    keywords: List[str],
    match_type: str
) -> bool:
    """
    Match text against keywords based on match type.
    
    Args:
        text: The text to match against
        keywords: List of keywords to match
        match_type: Type of matching (EXACT, CONTAINS, STARTSWITH, ENDSWITH)
        
    Returns:
        bool: True if match found, False otherwise
    """
    if not text or not keywords:
        return False
    
    # Normalize text and keywords
    text_lower = text.lower().strip()
    keywords_lower = [kw.strip().lower() for kw in keywords if kw.strip()]
    
    if not keywords_lower:
        return False
    
    match_type_upper = match_type.upper()
    
    # HARDCODED match type logic - DO NOT CHANGE
    if match_type_upper in [MatchType.EXACT]:
        return text_lower in keywords_lower
    
    elif match_type_upper in [MatchType.CONTAINS]:
        return any(kw in text_lower for kw in keywords_lower)
    
    elif match_type_upper in [MatchType.STARTSWITH, MatchType.START_WITH]:
        return any(text_lower.startswith(kw) for kw in keywords_lower)
    
    elif match_type_upper in [MatchType.ENDSWITH, MatchType.END_WITH]:
        return any(text_lower.endswith(kw) for kw in keywords_lower)
    
    return False


def parse_keywords(keywords_input: Any) -> List[str]:
    """
    Parse keywords from various input formats (string, list, comma-separated).
    
    Args:
        keywords_input: Keywords as string, list, or comma-separated values
        
    Returns:
        List[str]: Cleaned list of keywords
    """
    if isinstance(keywords_input, list):
        return [str(kw).strip() for kw in keywords_input if str(kw).strip()]
    
    elif isinstance(keywords_input, str):
        # Handle comma-separated keywords
        return [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
    
    return []


# ==================== AI DECISION UTILITIES ====================

async def check_ai_decision(
    text: str,
    ai_context_rules: str,
    model_provider: str = None,
    model_name: str = None
) -> Dict[str, Any]:
    """
    Use AI to determine if text matches context rules.
    
    Args:
        text: Text to evaluate
        ai_context_rules: Rules for AI to evaluate against
        model_provider: AI provider (defaults to OpenAI)
        model_name: AI model (defaults to gpt-4o-mini)
        
    Returns:
        Dict with 'should_reply' (bool) and 'tokens' (int)
    """
    try:
        # Force OpenAI GPT-4o-mini for all AI decisions
        model_provider = ModelConfig.DEFAULT_PROVIDER
        model_name = ModelConfig.DEFAULT_MODEL
        
        logger.info(f"AI decision check using {model_name}")
        
        ai_result = ai_responser.rule_based_ai(
            ai_rule=ai_context_rules,
            query=text,
            model_provider=model_provider,
            model_name=model_name
        )
        
        if isinstance(ai_result, dict):
            should_reply = ai_result.get("is_match", False)
            tokens = ai_result.get("tokens", 0)
        else:
            # Fallback for old format
            should_reply = bool(ai_result)
            tokens = 0
        
        logger.info(f"AI decision: should_reply={should_reply}, tokens={tokens}")
        return {"should_reply": should_reply, "tokens": tokens}
        
    except Exception as e:
        logger.error(f"Error in AI decision check: {e}")
        return {"should_reply": False, "tokens": 0}


async def generate_ai_reply(
    text: str,
    system_prompt: str,
    request_type: str = "comment_reply",
    model_provider: str = None,
    model_name: str = None,
    temperature: float = None
) -> Dict[str, Any]:
    """
    Generate AI reply for given text.
    
    Args:
        text: Original text to reply to
        system_prompt: System prompt for AI
        request_type: Type of request (comment_reply, dm_reply, etc.)
        model_provider: AI provider (defaults to OpenAI)
        model_name: AI model (defaults to gpt-4o-mini)
        temperature: Temperature for generation
        
    Returns:
        Dict with 'content' (str) and 'tokens' (int)
    """
    try:
        # Force OpenAI GPT-4o-mini for all AI generations
        model_provider = ModelConfig.DEFAULT_PROVIDER
        model_name = ModelConfig.DEFAULT_MODEL
        temperature = temperature if temperature is not None else ModelConfig.DEFAULT_TEMPERATURE
        
        logger.info(f"Generating AI reply using {model_name}")
        
        template = f"Original text: {text}\n\nGenerate an appropriate reply."
        
        ai_response = ai_responser.query(
            template=template,
            request_type=request_type,
            model_name=model_name,
            model_provider=model_provider,
            system_prompt=system_prompt,
            temperature=temperature
        )
        
        if isinstance(ai_response, dict):
            content = ai_response.get("content", "")
            tokens = ai_response.get("tokens", 0)
        else:
            content = str(ai_response) if ai_response else ""
            tokens = 0
        
        logger.info(f"AI reply generated: {len(content)} chars, {tokens} tokens")
        return {"content": content, "tokens": tokens}
        
    except Exception as e:
        logger.error(f"Error generating AI reply: {e}")
        return {"content": "", "tokens": 0}


# ==================== TOKEN TRACKING UTILITIES ====================

async def track_automation_tokens(
    automation_id: str,
    tokens_consumed: int,
    provider_id: str
) -> bool:
    """
    Track token consumption for automation.
    
    Args:
        automation_id: UUID of automation
        tokens_consumed: Number of tokens consumed
        provider_id: User's provider ID
        
    Returns:
        bool: True if successful
    """
    if tokens_consumed <= 0:
        return True
    
    try:
        from instagram_routers.automation_tracker import update_automation_metrics_direct
        
        success = await update_automation_metrics_direct(
            automation_id=automation_id,
            tokens_consumed=tokens_consumed,
            provider_id=provider_id
        )
        
        if success:
            logger.info(f"Tracked {tokens_consumed} tokens for automation {automation_id}")
        else:
            logger.warning(f"Failed to track tokens for automation {automation_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error tracking tokens: {e}")
        return False


async def get_provider_id(
    platform_user_id: str,
    platform: str = "instagram",
    config: Dict[str, Any] = None
) -> Optional[str]:
    """
    Get provider ID from config or database.
    
    Args:
        platform_user_id: Platform user ID
        platform: Platform name
        config: Optional config dict with provider_id
        
    Returns:
        Optional[str]: Provider ID if found
    """
    # Try config first
    if config and config.get('provider_id'):
        return config['provider_id']
    
    # Query database
    try:
        account_data = supabase.table("connected_accounts").select("provider_id").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", platform).limit(1).execute()
        
        if account_data.data and len(account_data.data) > 0:
            return account_data.data[0].get("provider_id")
        
        logger.warning(f"No provider_id found for {platform_user_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching provider_id: {e}")
        return None


# ==================== CREDIT CHECKING UTILITIES ====================

async def check_user_credits(provider_id: str) -> Dict[str, Any]:
    """
    Check if user has sufficient credits to process automation.
    If credits fall below 0, automatically deactivate ALL Instagram automations.
    
    Args:
        provider_id: User's provider ID
        
    Returns:
        Dict with 'has_credits' (bool) and 'current_credits' (int)
    """
    try:
        billing_data = supabase.table("billing_usage").select(
            "current_credits"
        ).eq("provider_id", provider_id).execute()
        
        if billing_data.data and len(billing_data.data) > 0:
            current_credits = billing_data.data[0].get("current_credits", 0)
            has_credits = current_credits > 0
            
            # 🚨 CRITICAL: If credits fall below 0, deactivate ALL Instagram automations
            if current_credits < 0:
                logger.critical(
                    f"🚨 CREDITS BELOW 0 for provider {provider_id}! "
                    f"Current credits: {current_credits}. "
                    f"Deactivating ALL Instagram automations and AI conversations."
                )
                deactivation_result = await deactivate_all_instagram_automations(provider_id)
                logger.critical(f"Deactivation result: {deactivation_result}")
            
            logger.info(f"Provider {provider_id} has {current_credits} credits")
            return {
                "has_credits": has_credits,
                "current_credits": current_credits
            }
        else:
            logger.warning(f"No billing data found for provider {provider_id}")
            return {
                "has_credits": False,
                "current_credits": 0
            }
    
    except Exception as e:
        logger.error(f"Error checking user credits: {e}")
        return {
            "has_credits": False,
            "current_credits": 0
        }


async def pause_automation(automation_id: str) -> bool:
    """
    Pause automation by setting activation_status to PAUSED.
    
    Args:
        automation_id: UUID of automation to pause
        
    Returns:
        bool: True if successful
    """
    try:
        result = supabase.table("automations").update({
            "activation_status": "PAUSED",
            "updated_at": "NOW()"
        }).eq("automation_id", automation_id).execute()
        
        logger.warning(f"Paused automation {automation_id} due to insufficient credits")
        return True
        
    except Exception as e:
        logger.error(f"Error pausing automation {automation_id}: {e}")
        return False


async def deactivate_all_instagram_automations(provider_id: str, platform: str = "instagram") -> Dict[str, Any]:
    """
    Deactivate ALL Instagram automations and AI conversations when credits fall below 0.
    This includes:
    - All automations from the automations table
    - AI conversation configurations from ai_conversations table
    
    Args:
        provider_id: User's provider ID
        platform: Platform name (default: "instagram")
        
    Returns:
        Dict with deactivation status and counts
    """
    try:
        # Get all platform_user_ids for this provider on Instagram
        accounts_response = supabase.table("connected_accounts").select(
            "platform_user_id"
        ).eq("provider_id", provider_id).eq("platform", platform).execute()
        
        if not accounts_response.data:
            logger.warning(f"No Instagram accounts found for provider {provider_id}")
            return {
                "success": False,
                "automations_deactivated": 0,
                "ai_conversations_deactivated": 0,
                "message": "No Instagram accounts found"
            }
        
        platform_user_ids = [account['platform_user_id'] for account in accounts_response.data]
        automations_count = 0
        ai_conversations_count = 0
        
        # Deactivate all automations for these platform users
        for platform_user_id in platform_user_ids:
            # Deactivate automations table entries
            automation_result = supabase.table("automations").update({
                "activation_status": "PAUSED",
                "updated_at": "NOW()"
            }).eq("platform_user_id", platform_user_id).eq("platform", platform).execute()
            
            if automation_result.data:
                automations_count += len(automation_result.data)
                logger.warning(
                    f"Deactivated {len(automation_result.data)} automations for "
                    f"platform_user_id {platform_user_id} due to credits below 0"
                )
            
            # Get all automation_ids for this platform_user_id to deactivate ai_conversations
            ai_automations = supabase.table("automations").select(
                "automation_id"
            ).eq("platform_user_id", platform_user_id).eq(
                "automation_type", "AI_DM_CONVERSATION"
            ).execute()
            
            if ai_automations.data:
                automation_ids = [auto['automation_id'] for auto in ai_automations.data]
                
                # Note: ai_conversations table doesn't have activation_status
                # We rely on the automations table status to control AI conversations
                # But we can log which AI conversations are affected
                for auto_id in automation_ids:
                    ai_conv_result = supabase.table("ai_conversations").select("*").eq(
                        "automation_id", auto_id
                    ).execute()
                    
                    if ai_conv_result.data:
                        ai_conversations_count += len(ai_conv_result.data)
                        logger.warning(
                            f"AI conversation (automation_id: {auto_id}) deactivated "
                            f"via automations table due to credits below 0"
                        )
        
        logger.critical(
            f"🚨 CREDITS BELOW 0 - Deactivated ALL Instagram automations for provider {provider_id}. "
            f"Automations deactivated: {automations_count}, "
            f"AI conversations affected: {ai_conversations_count}"
        )
        
        return {
            "success": True,
            "automations_deactivated": automations_count,
            "ai_conversations_deactivated": ai_conversations_count,
            "message": f"All Instagram automations deactivated due to insufficient credits"
        }
        
    except Exception as e:
        logger.error(f"Error deactivating all Instagram automations for provider {provider_id}: {e}")
        return {
            "success": False,
            "automations_deactivated": 0,
            "ai_conversations_deactivated": 0,
            "message": f"Error: {str(e)}"
        }


# ==================== POST SELECTION UTILITIES ====================

def check_post_selection(
    media_id: str,
    post_selection_type: str,
    specific_post_ids: List[str] = None
) -> bool:
    """
    Check if media ID matches post selection criteria.
    
    Args:
        media_id: Media/post ID to check
        post_selection_type: Selection type (ALL or SPECIFIC)
        specific_post_ids: List of specific post IDs
        
    Returns:
        bool: True if post matches selection criteria
    """
    from .constants import PostSelectionType
    
    if not media_id:
        return False
    
    if post_selection_type == PostSelectionType.ALL:
        return True
    
    elif post_selection_type == PostSelectionType.SPECIFIC:
        if not specific_post_ids:
            return False
        return media_id in specific_post_ids
    
    return False


# ==================== AUTOMATION VALIDATION UTILITIES ====================

def check_execution_limits(
    automation: Dict[str, Any]
) -> bool:
    """
    Check if automation has reached execution limits.
    
    Args:
        automation: Automation config dict
        
    Returns:
        bool: True if can execute, False if limits reached
    """
    max_actions = automation.get('max_actions')
    execution_count = automation.get('execution_count', 0)
    
    if max_actions and execution_count >= max_actions:
        logger.info(f"Automation {automation.get('automation_id')} reached max actions")
        return False
    
    return True


def should_process_trigger(
    trigger_type: str,
    text: str,
    config: Dict[str, Any]
) -> Tuple[bool, int]:
    """
    Synchronous check if trigger conditions are met (keyword only).
    For AI decisions, use check_ai_decision separately.
    
    Args:
        trigger_type: Type of trigger
        text: Text to check
        config: Automation config
        
    Returns:
        Tuple of (should_process, tokens_used)
    """
    # HARDCODED trigger type - DO NOT CHANGE
    if trigger_type.upper() == TriggerType.KEYWORD:
        keywords = parse_keywords(config.get('keywords', ''))
        match_type = config.get('match_type', MatchType.CONTAINS)
        
        is_match = match_keywords(text, keywords, match_type)
        return (is_match, 0)
    
    # For AI_DECISION, return False - caller should use check_ai_decision
    return (False, 0)
