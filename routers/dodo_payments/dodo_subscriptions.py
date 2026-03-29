"""
Dodo Payments Subscription Router
Handles subscription creation, token package purchases, and usage tracking
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional, List
import datetime
import logging
from supabase_client import supabase
from config.dodo_config import (
    get_async_dodo_client,
    get_subscription_plan,
    get_payg_config,
    calculate_payg_price,
    DODO_BRAND_ID,
    SUBSCRIPTION_PLANS,
    PAY_AS_YOU_GO
)
from models.dodo_subscription_model import (
    CreateSubscriptionRequest,
    PurchaseTokenPackageRequest,
    UpdateSubscriptionRequest,
    SubscriptionResponse,
    TokenPackageResponse,
    TokenUsageResponse
)
from utils.api_responses import APIResponse
import os

router = APIRouter(
    prefix="/dodo-subscriptions",
    tags=["Dodo Payments Subscriptions"]
)

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# ==================== Subscription Management ====================

@router.post("/create-subscription", response_model=SubscriptionResponse)
async def create_subscription(request: CreateSubscriptionRequest):
    """
    Create a new usage-based subscription with Dodo Payments
    
    - **Monthly 5M Plan**: Get 5 million tokens per month for $10/850 INR
    - Tokens refresh monthly
    - Auto-renewal enabled by default
    """
    try:
        # Get plan configuration
        plan = get_subscription_plan(request.plan_key)
        if not plan:
            raise HTTPException(status_code=400, detail=f"Invalid plan key: {request.plan_key}")
        
        # Validate product ID is configured
        if not plan.get("product_id"):
            raise HTTPException(
                status_code=500, 
                detail=f"Product ID not configured for plan: {request.plan_key}"
            )
        
        # Get Dodo client
        dodo_client = get_async_dodo_client()
        
        # Determine price based on currency
        amount = plan["price_usd"] if request.currency.value == "USD" else plan["price_inr"]
        
        # Create subscription with Dodo Payments
        subscription = await dodo_client.subscriptions.create(
            product_id=plan["product_id"],
            quantity=1,
            billing_currency=request.currency.value,
            payment_link=True,  # Generate payment link
            customer={
                "email": request.email,
                "name": request.name
            },
            billing={
                "country": request.country,
                "city": request.city,
                "street": request.street,
                "zipcode": request.zipcode,
                "state": request.state
            },
            return_url=request.return_url or f"{BACKEND_URL}/dodo-subscriptions/success",
            metadata={
                "provider_id": request.user_id,
                "plan_key": request.plan_key,
                "tokens_allocated": str(plan["tokens"]),
                **request.metadata
            }
        )
        
        # Store subscription in database
        subscription_record = {
            "dodo_subscription_id": subscription.subscription_id,
            "dodo_customer_id": getattr(subscription, 'customer_id', request.email),  # Fallback to email
            "provider_id": request.user_id,
            "plan_type": request.plan_key,
            "product_id": plan["product_id"],
            "status": getattr(subscription, 'status', 'pending'),
            "tokens_allocated": plan["tokens"],
            "tokens_consumed": 0,
            "billing_interval": plan["billing_interval"],
            "currency": request.currency.value,
            "amount": amount,
            "metadata": {
                "plan_name": plan["name"],
                "dodo_subscription_data": subscription.model_dump(mode='json')
            },
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        db_response = supabase.table("dodo_subscriptions").insert(subscription_record).execute()
        
        if not db_response.data:
            # Subscription created in Dodo but failed to save locally
            # Log this for manual intervention
            logger.error(f"Failed to save subscription {subscription.subscription_id} to database")
        
        # Get payment URL - Dodo returns payment_link when payment_link=True
        payment_url = getattr(subscription, 'payment_link', None)
        
        return SubscriptionResponse(
            success=True,
            message="Subscription created successfully. Please complete payment.",
            subscription_id=subscription.subscription_id,
            payment_url=payment_url,
            status=getattr(subscription, 'status', 'pending'),
            tokens_allocated=plan["tokens"],
            data={
                "subscription": subscription.model_dump(mode='json'),
                "plan_details": plan
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")


@router.get("/plans")
async def get_available_plans():
    """
    Get all available pricing options
    
    Returns:
        - Monthly subscription: Fixed price for 5M tokens/month
        - Pay-as-you-go: Flexible tokens in multiples of 500K
    """
    payg_config = get_payg_config()
    
    # Calculate example prices for pay-as-you-go
    examples_inr = [
        calculate_payg_price(1, "INR"),   # 500K = ₹100
        calculate_payg_price(2, "INR"),   # 1M = ₹200
        calculate_payg_price(5, "INR"),   # 2.5M = ₹500
        calculate_payg_price(10, "INR"),  # 5M = ₹1000
        calculate_payg_price(20, "INR"),  # 10M = ₹2000
    ]
    
    return APIResponse.success({
        "pricing_models": {
            "subscription": {
                "type": "monthly_subscription",
                "plan": SUBSCRIPTION_PLANS["monthly_5m"],
                "features": [
                    "5 million tokens every month",
                    "Tokens reset on monthly renewal",
                    "Usage-based billing",
                    "Auto-renewal (can cancel anytime)"
                ]
            },
            "pay_as_you_go": {
                "type": "flexible_tokens",
                "config": payg_config,
                "pricing": {
                    "base_unit": "500K tokens = ₹100",
                    "min_purchase": f"{payg_config['min_units']} unit ({payg_config['min_units'] * 500}K tokens)",
                    "max_purchase": f"{payg_config['max_units']} units ({payg_config['max_units'] * 500}K tokens)"
                },
                "examples_inr": examples_inr,
                "features": [
                    "Buy exactly what you need",
                    "No subscription required",
                    "Tokens never expire",
                    "Adjust quantity in multiples of 500K"
                ]
            }
        },
        "currency_support": ["USD", "INR"],
        "recommendation": {
            "regular_users": "Monthly subscription (best value for 5M+ tokens/month)",
            "occasional_users": "Pay-as-you-go (flexibility without commitment)"
        }
    })


@router.get("/subscription/{subscription_id}")
async def get_subscription(subscription_id: str):
    """
    Get subscription details by ID
    """
    try:
        # Check local database first
        local_sub = supabase.table("dodo_subscriptions").select("*").eq(
            "dodo_subscription_id", subscription_id
        ).single().execute()
        
        if not local_sub.data:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Optionally fetch latest from Dodo
        dodo_client = get_async_dodo_client()
        dodo_sub = await dodo_client.subscriptions.retrieve(subscription_id)
        
        return APIResponse.success({
            "local_data": local_sub.data,
            "dodo_data": dodo_sub.model_dump()
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve subscription: {str(e)}")


@router.get("/my-subscriptions/{user_id}")
async def get_user_subscriptions(user_id: str):
    """
    Get all subscriptions for a user
    """
    try:
        subscriptions = supabase.table("dodo_subscriptions").select("*").eq(
            "provider_id", user_id
        ).order("created_at", desc=True).execute()
        
        return APIResponse.success({
            "subscriptions": subscriptions.data or [],
            "count": len(subscriptions.data) if subscriptions.data else 0
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve subscriptions: {str(e)}")


@router.patch("/subscription/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(subscription_id: str, request: UpdateSubscriptionRequest):
    """
    Update subscription settings (cancel, change status, etc.)
    """
    try:
        dodo_client = get_async_dodo_client()
        
        # Update in Dodo Payments
        updated_sub = await dodo_client.subscriptions.update(
            subscription_id=subscription_id,
            cancel_at_next_billing_date=request.cancel_at_next_billing_date,
            status=request.status.value if request.status else None,
            metadata=request.metadata
        )
        
        # Update local database
        update_data = {
            "status": updated_sub.status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        if request.cancel_at_next_billing_date:
            update_data["cancelled_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        supabase.table("dodo_subscriptions").update(update_data).eq(
            "dodo_subscription_id", subscription_id
        ).execute()
        
        return SubscriptionResponse(
            success=True,
            message="Subscription updated successfully",
            subscription_id=subscription_id,
            status=updated_sub.status,
            data=updated_sub.model_dump()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update subscription: {str(e)}")


# ==================== Pay-As-You-Go Token Purchase ====================

@router.post("/purchase-tokens", response_model=TokenPackageResponse)
async def purchase_payg_tokens(request: PurchaseTokenPackageRequest):
    """
    Purchase tokens with Pay-As-You-Go model
    
    **Flexible Token Purchase:**
    - Base unit: 500K tokens = ₹100 (or $1)
    - Buy in multiples: 1x, 2x, 3x, 4x, 5x, 10x, 20x, etc.
    
    **Examples:**
    - quantity=1 → 500K tokens for ₹100
    - quantity=2 → 1M tokens for ₹200
    - quantity=5 → 2.5M tokens for ₹500
    - quantity=10 → 5M tokens for ₹1000
    - quantity=20 → 10M tokens for ₹2000
    
    **Features:**
    - No subscription needed
    - Tokens never expire
    - Usage-based: pay only for what you use
    - Adjust quantity to your exact needs
    """
    try:
        logger.info(f"[PAYG] Starting token purchase request for user: {request.user_id}, quantity: {request.quantity}")
        
        # Get pay-as-you-go configuration
        payg_config = get_payg_config()
        logger.debug(f"[PAYG] Config loaded: {payg_config}")
        
        if not payg_config.get("product_id"):
            error_msg = "Pay-as-you-go product not configured. Please set DODO_PRODUCT_PAYG in .env or create the product in Dodo dashboard."
            logger.error(f"[PAYG ERROR] {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
        
        # Validate quantity
        if request.quantity < payg_config["min_units"] or request.quantity > payg_config["max_units"]:
            error_msg = f"Quantity must be between {payg_config['min_units']} and {payg_config['max_units']} units"
            logger.error(f"[PAYG ERROR] {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # Calculate pricing
        pricing = calculate_payg_price(request.quantity, request.currency.value)
        logger.debug(f"[PAYG] Calculated pricing: {pricing}")
        
        # Get Dodo client
        dodo_client = get_async_dodo_client()
        logger.debug("[PAYG] Dodo client initialized")
        
        # Create one-time payment
        logger.info(f"[PAYG] Creating payment with product_id: {payg_config['product_id']}")
        payment = await dodo_client.payments.create(
            product_cart=[{
                "product_id": payg_config["product_id"],
                "quantity": request.quantity
            }],
            billing_currency=request.currency.value,
            payment_link=True,  # Generate payment link
            customer={
                "email": request.email,
                "name": request.name
            },
            billing={
                "country": request.country,
                "city": request.city,
                "street": request.street,
                "zipcode": request.zipcode,
                "state": request.state
            },
            return_url=request.return_url or f"{BACKEND_URL}/dodo-subscriptions/payment-success",
            metadata={
                "provider_id": request.user_id,
                "pricing_model": "pay_as_you_go",
                "units": str(request.quantity),
                "tokens_per_unit": str(payg_config["tokens_per_unit"]),
                "total_tokens": str(pricing["tokens"])
            }
        )
        logger.info(f"[PAYG] Payment created successfully: {payment.payment_id}")
        
        # Store purchase in database
        purchase_record = {
            "dodo_payment_id": payment.payment_id,
            "dodo_customer_id": payment.customer.customer_id,  # customer_id is inside customer object
            "provider_id": request.user_id,
            "package_key": "payg",
            "product_id": payg_config["product_id"],
            "quantity": request.quantity,
            "tokens_per_package": payg_config["tokens_per_unit"],
            "tokens_consumed": 0,
            "amount": pricing["total_price"],
            "currency": request.currency.value,
            "status": "pending",
            "metadata": {
                "pricing_model": "pay_as_you_go",
                "units": request.quantity,
                "price_per_unit": pricing["price_per_unit"],
                "payment_data": payment.model_dump(mode='json')  # Use mode='json' to serialize datetime objects
            }
            # Don't include created_at - Supabase will auto-generate it with default=now()
        }
        
        # ⚠️ IMPORTANT: Must pass provider_id to Dodo in metadata so webhook can add credits
        # The webhook handler will extract this when payment succeeds
        if not payment.metadata or "provider_id" not in payment.metadata:
            logger.error(f"[PAYG CRITICAL] provider_id NOT in Dodo payment metadata!")
            logger.error(f"   Payment metadata: {payment.metadata}")
        else:
            logger.info(f"[PAYG] ✅ provider_id correctly passed to Dodo: {payment.metadata.get('provider_id')}")
        
        supabase.table("dodo_one_time_purchases").insert(purchase_record).execute()
        logger.info("[PAYG] Purchase record saved to database")
        
        # Get payment URL - Dodo returns payment_link when payment_link=True
        payment_url = getattr(payment, 'payment_link', "")
        logger.info(f"[PAYG] Payment URL: {payment_url}")
        
        return TokenPackageResponse(
            success=True,
            message=f"Pay-as-you-go purchase created: {pricing['description']}",
            payment_url=payment_url,
            payment_id=payment.payment_id,
            tokens=pricing["tokens"],
            total_cost=pricing["total_price"],
            currency=request.currency.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error("[PAYG ERROR] Exception occurred:")
        logger.error(error_details)
        logger.error(f"[PAYG ERROR] Error type: {type(e).__name__}")
        logger.error(f"[PAYG ERROR] Error message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create token purchase: {str(e)}")


# ==================== Token Usage Tracking ====================

@router.get("/tokens/{user_id}", response_model=TokenUsageResponse)
async def get_token_balance(user_id: str):
    """
    Get user's total token balance from billing_usage table
    This reflects the actual current_credits that are used across the platform
    """
    try:
        # Get credits from billing_usage table (the single source of truth)
        billing_result = supabase.table("billing_usage").select(
            "current_credits, chat_token, chat_cost"
        ).eq("provider_id", user_id).execute()
        
        if not billing_result.data:
            # User doesn't have billing record yet
            return TokenUsageResponse(
                user_id=user_id,
                total_tokens_purchased=0,
                total_tokens_consumed=0,
                tokens_remaining=0,
                active_subscriptions=[]
            )
        
        billing_data = billing_result.data[0]
        current_credits = float(billing_data.get("current_credits", 0))
        chat_token = int(billing_data.get("chat_token", 0))
        
        # Get active subscriptions for display
        active_subs = supabase.table("dodo_subscriptions").select("*").eq(
            "provider_id", user_id
        ).eq("status", "active").execute()
        
        # Calculate total purchased from subscription and purchase history
        # (This is informational - the actual balance is current_credits)
        subs = supabase.table("dodo_subscriptions").select("tokens_allocated").eq(
            "provider_id", user_id
        ).execute()
        
        purchases = supabase.table("dodo_one_time_purchases").select(
            "quantity, tokens_per_package"
        ).eq("provider_id", user_id).eq("status", "succeeded").execute()
        
        total_from_subs = sum(s.get("tokens_allocated", 0) for s in (subs.data or []))
        total_from_purchases = sum(
            p.get("quantity", 0) * p.get("tokens_per_package", 0) 
            for p in (purchases.data or [])
        )
        total_purchased = total_from_subs + total_from_purchases
        
        return TokenUsageResponse(
            user_id=user_id,
            total_tokens_purchased=total_purchased,
            total_tokens_consumed=chat_token,
            tokens_remaining=int(current_credits),  # This is the actual usable balance
            active_subscriptions=active_subs.data or []
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve token balance: {str(e)}")


@router.get("/usage-history/{user_id}")
async def get_usage_history(
    user_id: str,
    limit: int = 100,
    offset: int = 0
):
    """
    Get token usage history for a user
    """
    try:
        usage_records = supabase.table("dodo_token_usage").select("*").eq(
            "provider_id", user_id
        ).order("consumed_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return APIResponse.success({
            "usage_history": usage_records.data or [],
            "count": len(usage_records.data) if usage_records.data else 0,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve usage history: {str(e)}")


@router.post("/consume-tokens")
async def consume_tokens(
    user_id: str,
    tokens_used: int,
    cost: float = 0.0,
    operation_type: str = "ai_chat",
    metadata: dict = None
):
    """
    Record token consumption from AI operations
    
    This endpoint is called by the AI Development service to track token usage.
    It deducts tokens from the user's balance and records the usage.
    
    Args:
        user_id: The user's provider_id
        tokens_used: Number of tokens consumed
        cost: Cost of the operation (optional)
        operation_type: Type of operation (default: "ai_chat")
        metadata: Additional metadata about the usage
    """
    try:
        if tokens_used <= 0:
            raise HTTPException(status_code=400, detail="tokens_used must be greater than 0")
        
        # Get user's current balance
        balance_response = supabase.table("dodo_token_balance").select(
            "provider_id, total_tokens_purchased, tokens_consumed, tokens_remaining"
        ).eq("provider_id", user_id).execute()
        
        if not balance_response.data:
            raise HTTPException(status_code=404, detail="User token balance not found")
        
        balance = balance_response.data[0]
        tokens_remaining = balance.get("tokens_remaining", 0)
        
        # Check if user has enough tokens
        if tokens_remaining < tokens_used:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient tokens. Available: {tokens_remaining}, Required: {tokens_used}"
            )
        
        # Record token usage
        usage_data = {
            "provider_id": user_id,
            "tokens_consumed": tokens_used,
            "cost": cost,
            "operation_type": operation_type,
            "metadata": metadata or {},
            "consumed_at": datetime.datetime.utcnow().isoformat()
        }
        
        supabase.table("dodo_token_usage").insert(usage_data).execute()
        
        # Update token balance using the database function
        update_result = supabase.rpc(
            "update_token_balance",
            {
                "p_provider_id": user_id,
                "p_tokens_consumed": tokens_used
            }
        ).execute()
        
        # Get updated balance
        updated_balance = supabase.table("dodo_token_balance").select(
            "provider_id, total_tokens_purchased, tokens_consumed, tokens_remaining"
        ).eq("provider_id", user_id).execute()
        
        return APIResponse.success({
            "message": "Tokens consumed successfully",
            "tokens_consumed": tokens_used,
            "tokens_remaining": updated_balance.data[0]["tokens_remaining"] if updated_balance.data else 0,
            "operation_type": operation_type
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to consume tokens: {str(e)}")


# ==================== Success/Callback Endpoints ====================

@router.get("/success")
async def subscription_success():
    """Redirect endpoint after successful subscription payment"""
    return JSONResponse({
        "success": True,
        "message": "Subscription activated! Your tokens will be available shortly."
    })


@router.get("/payment-success")
async def payment_success():
    """Redirect endpoint after successful token package payment"""
    return JSONResponse({
        "success": True,
        "message": "Payment successful! Your tokens have been added to your account."
    })


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return APIResponse.success({"status": "healthy", "service": "Dodo Payments Subscriptions"})


@router.post("/sync-balance/{user_id}")
async def sync_user_balance(user_id: str):
    """
    Manually sync/refresh a user's token balance
    Useful for debugging or fixing balance discrepancies
    """
    try:
        # Refresh the balance
        supabase.rpc('refresh_token_balance', {'p_provider_id': user_id}).execute()
        
        # Get the updated balance
        balance = supabase.table("dodo_token_balance").select("*").eq(
            "provider_id", user_id
        ).execute()
        
        return APIResponse.success({
            "message": "Balance synced successfully",
            "user_id": user_id,
            "balance": balance.data[0] if balance.data else None
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync balance: {str(e)}")


@router.post("/sync-all-balances")
async def sync_all_balances():
    """
    Sync token balances for all users with subscriptions or purchases
    Admin endpoint for bulk balance refresh
    """
    try:
        # Get all unique user IDs from subscriptions and purchases
        subs_users = supabase.table("dodo_subscriptions").select("provider_id").execute()
        purchase_users = supabase.table("dodo_one_time_purchases").select("provider_id").execute()
        
        # Combine and deduplicate user IDs
        user_ids = set()
        if subs_users.data:
            user_ids.update([u["provider_id"] for u in subs_users.data])
        if purchase_users.data:
            user_ids.update([u["provider_id"] for u in purchase_users.data])
        
        synced_count = 0
        errors = []
        
        # Sync each user
        for user_id in user_ids:
            try:
                supabase.rpc('refresh_token_balance', {'p_provider_id': user_id}).execute()
                synced_count += 1
            except Exception as e:
                errors.append({"user_id": user_id, "error": str(e)})
        
        return APIResponse.success({
            "message": f"Synced {synced_count} user balances",
            "total_users": len(user_ids),
            "synced": synced_count,
            "errors": errors if errors else None
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync all balances: {str(e)}")
