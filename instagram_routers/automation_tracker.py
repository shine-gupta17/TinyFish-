"""
Automation tracking utilities for Instagram automations.
Handles token consumption tracking, execution count increment, and billing deduction.
"""
import logging
from supabase_client import supabase

logger = logging.getLogger(__name__)


async def update_automation_metrics(
    automation_id: str,
    tokens_consumed: int,
    provider_id: str
) -> bool:
    """
    Update automation metrics after each execution:
    1. Increment execution_count
    2. Add tokens to cumulative_tokens
    3. Update last_triggered_at
    4. Deduct tokens from user's billing_usage
    
    Args:
        automation_id: The automation's UUID
        tokens_consumed: Number of tokens used in this execution
        provider_id: User's provider ID for billing
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Step 1 & 2 & 3: Update automation record
        automation_update = supabase.rpc(
            'increment_automation_metrics',
            {
                'p_automation_id': automation_id,
                'p_tokens_consumed': tokens_consumed
            }
        ).execute()
        
        logger.info(f"Updated automation {automation_id}: +{tokens_consumed} tokens")
        
        # Step 4: Deduct tokens from billing_usage
        billing_update = supabase.rpc(
            'deduct_user_credits',
            {
                'p_provider_id': provider_id,
                'p_tokens': tokens_consumed
            }
        ).execute()
        
        logger.info(f"Deducted {tokens_consumed} tokens from user {provider_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to update automation metrics: {e}")
        return False


async def update_automation_metrics_direct(
    automation_id: str,
    tokens_consumed: int,
    provider_id: str
) -> bool:
    """
    Direct SQL update method to track cumulative tokens and update billing.
    Note: execution_count should be updated separately using increment_automation_execution_count
    
    Args:
        automation_id: The automation's UUID
        tokens_consumed: Number of tokens used in this execution
        provider_id: User's provider ID for billing
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First, get current cumulative_tokens
        automation_data = supabase.table("automations").select(
            "cumulative_tokens"
        ).eq("automation_id", automation_id).execute()
        
        if not automation_data.data or len(automation_data.data) == 0:
            logger.error(f"Automation {automation_id} not found")
            return False
        
        current_cumulative_tokens = automation_data.data[0].get("cumulative_tokens", 0) or 0
        new_cumulative_tokens = current_cumulative_tokens + tokens_consumed
        
        # Update automation record with new cumulative tokens
        automation_update = supabase.table("automations").update({
            "cumulative_tokens": new_cumulative_tokens
        }).eq("automation_id", automation_id).execute()
        
        logger.info(f"Updated automation {automation_id}: cumulative_tokens {current_cumulative_tokens} -> {new_cumulative_tokens} (+{tokens_consumed})")
        
        # Deduct tokens from billing_usage
        current_billing = supabase.table("billing_usage").select(
            "chat_token, current_credits"
        ).eq("provider_id", provider_id).execute()
        
        if current_billing.data:
            current_tokens = current_billing.data[0].get("chat_token", 0) or 0
            current_credits = current_billing.data[0].get("current_credits", 0) or 0
            
            supabase.table("billing_usage").update({
                "chat_token": current_tokens + tokens_consumed,
                "current_credits": current_credits - tokens_consumed
            }).eq("provider_id", provider_id).execute()
            
            logger.info(f"Deducted {tokens_consumed} tokens from user {provider_id}: credits {current_credits} -> {current_credits - tokens_consumed}")
        else:
            # Create new billing record if doesn't exist
            supabase.table("billing_usage").insert({
                "provider_id": provider_id,
                "chat_token": tokens_consumed,
                "current_credits": -tokens_consumed,
                "chat_cost": 0.0
            }).execute()
            
            logger.warning(f"Created new billing record for {provider_id} with {tokens_consumed} tokens")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to update automation metrics directly: {e}", exc_info=True)
        return False
