"""
Token Usage Tracking Service
Tracks token consumption and reports to Dodo Payments meters for usage-based billing
"""

import datetime
import logging
from typing import Optional, Dict, Any
from supabase_client import supabase
from config.dodo_config import get_async_dodo_client, METER_CONFIG

logger = logging.getLogger(__name__)


class TokenUsageService:
    """
    Service for tracking and reporting token usage
    """
    
    @staticmethod
    async def consume_tokens(
        user_id: str,
        tokens: int,
        operation_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record token consumption and deduct from user's balance
        
        Args:
            user_id: User's provider ID
            tokens: Number of tokens consumed
            operation_type: Type of operation (chat, automation, etc.)
            metadata: Additional metadata about the operation
            
        Returns:
            Dict with consumption details and remaining balance
        """
        try:
            # Get user's active token sources (subscriptions + purchases)
            # Priority: Use subscription tokens first, then one-time purchases
            
            tokens_to_consume = tokens
            consumption_log = []
            
            # 1. Try to consume from active subscriptions first
            active_subs = supabase.table("dodo_subscriptions").select("*").eq(
                "provider_id", user_id
            ).eq("status", "active").order("created_at", asc=True).execute()
            
            for sub in (active_subs.data or []):
                if tokens_to_consume <= 0:
                    break
                
                available = sub["tokens_remaining"]
                if available > 0:
                    consumed_from_this = min(tokens_to_consume, available)
                    
                    # Update subscription
                    new_consumed = sub["tokens_consumed"] + consumed_from_this
                    supabase.table("dodo_subscriptions").update({
                        "tokens_consumed": new_consumed,
                        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }).eq("id", sub["id"]).execute()
                    
                    consumption_log.append({
                        "source": "subscription",
                        "subscription_id": sub["dodo_subscription_id"],
                        "tokens": consumed_from_this
                    })
                    
                    tokens_to_consume -= consumed_from_this
            
            # 2. If still tokens to consume, use one-time purchases
            if tokens_to_consume > 0:
                purchases = supabase.table("dodo_one_time_purchases").select("*").eq(
                    "provider_id", user_id
                ).eq("status", "succeeded").order("created_at", asc=True).execute()
                
                for purchase in (purchases.data or []):
                    if tokens_to_consume <= 0:
                        break
                    
                    available = purchase["tokens_remaining"]
                    if available > 0:
                        consumed_from_this = min(tokens_to_consume, available)
                        
                        # Update purchase
                        new_consumed = purchase["tokens_consumed"] + consumed_from_this
                        supabase.table("dodo_one_time_purchases").update({
                            "tokens_consumed": new_consumed,
                            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                        }).eq("id", purchase["id"]).execute()
                        
                        consumption_log.append({
                            "source": "package",
                            "payment_id": purchase["dodo_payment_id"],
                            "tokens": consumed_from_this
                        })
                        
                        tokens_to_consume -= consumed_from_this
            
            # Check if we consumed all requested tokens
            if tokens_to_consume > 0:
                return {
                    "success": False,
                    "error": "Insufficient tokens",
                    "requested": tokens,
                    "consumed": tokens - tokens_to_consume,
                    "shortage": tokens_to_consume
                }
            
            # Log the consumption
            usage_record = {
                "provider_id": user_id,
                "tokens_consumed": tokens,
                "operation_type": operation_type,
                "metadata": {
                    **(metadata or {}),
                    "consumption_breakdown": consumption_log
                },
                "consumed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            
            supabase.table("dodo_token_usage").insert(usage_record).execute()
            
            # Get updated balance
            balance = await TokenUsageService.get_token_balance(user_id)
            
            return {
                "success": True,
                "tokens_consumed": tokens,
                "consumption_log": consumption_log,
                "remaining_balance": balance["tokens_remaining"]
            }
            
        except Exception as e:
            logger.error(f"Error consuming tokens: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    @staticmethod
    async def get_token_balance(user_id: str) -> Dict[str, Any]:
        """
        Get user's current token balance
        
        Args:
            user_id: User's provider ID
            
        Returns:
            Dict with token balance information
        """
        try:
            result = supabase.rpc('get_user_total_tokens', {
                'user_provider_id': user_id
            }).execute()
            
            if not result.data or len(result.data) == 0:
                return {
                    "total_purchased": 0,
                    "total_consumed": 0,
                    "tokens_remaining": 0,
                    "subscription_tokens": 0,
                    "package_tokens": 0
                }
            
            return result.data[0]
            
        except Exception as e:
            logger.error(f"Error getting token balance: {str(e)}")
            return {
                "error": str(e),
                "total_purchased": 0,
                "total_consumed": 0,
                "tokens_remaining": 0
            }
    
    
    @staticmethod
    async def report_usage_to_dodo(
        subscription_id: str,
        tokens_consumed: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Report usage to Dodo Payments meters for metered billing
        
        This is used when you have metered subscriptions that charge based on usage.
        For the current implementation with fixed token allocations, this may not be needed.
        
        Args:
            subscription_id: Dodo subscription ID
            tokens_consumed: Number of tokens consumed
            metadata: Additional metadata
            
        Returns:
            bool: Success status
        """
        try:
            # Get subscription to find customer ID
            sub = supabase.table("dodo_subscriptions").select("*").eq(
                "dodo_subscription_id", subscription_id
            ).single().execute()
            
            if not sub.data:
                return False
            
            customer_id = sub.data["dodo_customer_id"]
            provider_id = sub.data["provider_id"]
            
            # Get meter ID from config
            meter_id = METER_CONFIG.get("token_usage", {}).get("meter_id")
            if not meter_id:
                logger.warning("Meter ID not configured")
                return False
            
            # Report to Dodo Payments
            dodo_client = get_async_dodo_client()
            
            event = await dodo_client.usage_events.ingest(
                events=[{
                    "event_id": f"{provider_id}_{datetime.datetime.now().timestamp()}",
                    "event_name": METER_CONFIG["token_usage"]["event_name"],
                    "customer_id": customer_id,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "properties": {
                        "tokens": tokens_consumed,
                        "subscription_id": subscription_id,
                        "provider_id": provider_id,
                        **(metadata or {})
                    }
                }]
            )
            
            logger.info(f"Reported {tokens_consumed} tokens to Dodo meter for subscription {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error reporting to Dodo meters: {str(e)}")
            return False
    
    
    @staticmethod
    async def check_and_warn_low_balance(user_id: str, threshold: int = 100000) -> Dict[str, Any]:
        """
        Check if user has low token balance and return warning
        
        Args:
            user_id: User's provider ID
            threshold: Token threshold for warning (default 100k)
            
        Returns:
            Dict with warning information
        """
        balance = await TokenUsageService.get_token_balance(user_id)
        remaining = balance.get("tokens_remaining", 0)
        
        if remaining <= 0:
            return {
                "warning": "critical",
                "message": "You have run out of tokens. Please purchase more to continue.",
                "remaining": 0
            }
        elif remaining < threshold:
            return {
                "warning": "low",
                "message": f"You have only {remaining:,} tokens remaining. Consider purchasing more.",
                "remaining": remaining
            }
        else:
            return {
                "warning": None,
                "remaining": remaining
            }


# Convenience functions for easy imports
async def consume_tokens(
    user_id: str,
    tokens: int,
    operation_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Consume tokens from user's balance"""
    return await TokenUsageService.consume_tokens(user_id, tokens, operation_type, metadata)


async def get_token_balance(user_id: str) -> Dict[str, Any]:
    """Get user's token balance"""
    return await TokenUsageService.get_token_balance(user_id)


async def check_sufficient_tokens(user_id: str, required_tokens: int) -> bool:
    """Check if user has sufficient tokens"""
    balance = await TokenUsageService.get_token_balance(user_id)
    return balance.get("tokens_remaining", 0) >= required_tokens
