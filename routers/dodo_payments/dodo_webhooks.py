"""
Dodo Payments Webhook Handler
Processes webhook events from Dodo Payments for subscriptions and payments
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import datetime
import hmac
import hashlib
import os
import logging
from supabase_client import supabase
from utils.api_responses import APIResponse
import json

router = APIRouter(
    prefix="/dodo-webhooks",
    tags=["Dodo Payments Webhooks"]
)

logger = logging.getLogger(__name__)

# Webhook secret for signature verification
DODO_WEBHOOK_SECRET = os.getenv("DODO_WEBHOOK_SECRET")


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature from Dodo Payments
    
    Args:
        payload: Raw request body
        signature: Signature from request header
        secret: Webhook secret
        
    Returns:
        bool: True if signature is valid
    """
    if not secret:
        # In development, you might skip verification
        # In production, this should always be required
        return True
    
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@router.post("/event")
async def handle_webhook_event(
    request: Request,
    x_dodo_signature: Optional[str] = Header(None, alias="X-Dodo-Signature")
):
    """
    Main webhook endpoint for Dodo Payments events
    
    Handles:
    - subscription.active: Subscription activated
    - subscription.renewed: Subscription renewed (monthly)
    - subscription.cancelled: Subscription cancelled
    - subscription.expired: Subscription expired
    - payment.succeeded: One-time payment succeeded
    - payment.failed: Payment failed
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature
        if DODO_WEBHOOK_SECRET and x_dodo_signature:
            if not verify_webhook_signature(body, x_dodo_signature, DODO_WEBHOOK_SECRET):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        # Parse event
        event = await request.json()
        event_type = event.get("event_type") or event.get("type")
        event_id = event.get("event_id") or event.get("id")
        
        logger.info(f"Received webhook event: {event_type} (ID: {event_id})")
        
        # Store webhook event for auditing
        webhook_record = {
            "event_id": event_id,
            "event_type": event_type,
            "processed": False,
            "payload": event,
            "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        insert_result = supabase.table("dodo_webhook_events").insert(webhook_record).execute()
        db_record_id = insert_result.data[0]["id"] if insert_result.data else None
        
        # Route to appropriate handler
        if event_type == "subscription.active":
            await handle_subscription_active(event)
        elif event_type == "subscription.renewed":
            await handle_subscription_renewed(event)
        elif event_type == "subscription.cancelled":
            await handle_subscription_cancelled(event)
        elif event_type == "subscription.expired":
            await handle_subscription_expired(event)
        elif event_type == "payment.succeeded":
            await handle_payment_succeeded(event)
        elif event_type == "payment.failed":
            await handle_payment_failed(event)
        else:
            logger.warning(f"Unhandled event type: {event_type}")
        
        # Mark as processed using database ID
        if db_record_id:
            supabase.table("dodo_webhook_events").update({
                "processed": True,
                "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq("id", db_record_id).execute()
        
        return APIResponse.success({"received": True, "event_type": event_type})
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Mark as failed using database ID if available
        if db_record_id:
            supabase.table("dodo_webhook_events").update({
                "processed": False,
                "processing_error": str(e)
            }).eq("id", db_record_id).execute()
        
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# ==================== Event Handlers ====================

async def handle_subscription_active(event: dict):
    """
    Handle subscription activation
    Updates subscription status and allocates tokens
    """
    try:
        data = event.get("data", {})
        subscription_id = data.get("subscription_id")
        customer_id = data.get("customer_id")
        status = data.get("status")
        
        # Get subscription metadata to retrieve tokens
        metadata = data.get("metadata", {})
        tokens_allocated = int(metadata.get("tokens_allocated", 0))
        provider_id = metadata.get("provider_id")
        
        logger.info(f"✅ [SUBSCRIPTION ACTIVE] Subscription {subscription_id} activated")
        logger.info(f"   Provider ID: {provider_id}")
        logger.info(f"   Tokens: {tokens_allocated}")
        
        # Validate provider_id
        if not provider_id:
            logger.error(f"❌ [ACTIVE ERROR] No provider_id in metadata for subscription {subscription_id}")
            raise ValueError("Missing provider_id in subscription activation")
        
        # Update subscription in database
        update_data = {
            "status": status,
            "dodo_customer_id": customer_id,
            "tokens_allocated": tokens_allocated,
            "tokens_consumed": 0,
            "current_period_start": data.get("current_period_start"),
            "current_period_end": data.get("current_period_end"),
            "next_billing_date": data.get("next_billing_date"),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        result = supabase.table("dodo_subscriptions").update(update_data).eq(
            "dodo_subscription_id", subscription_id
        ).execute()
        
        if result.data:
            logger.info(f"✅ Subscription database updated: {subscription_id}")
        else:
            logger.warning(f"⚠️ Subscription update returned no data for {subscription_id}")
        
        # ADD CREDITS TO BILLING_USAGE TABLE
        if provider_id and tokens_allocated > 0:
            logger.info(f"💰 [CREDIT UPDATE] Adding subscription credits...")
            # Get current credits
            billing_result = supabase.table("billing_usage").select("current_credits").eq(
                "provider_id", provider_id
            ).execute()
            
            if billing_result.data:
                current_credits = float(billing_result.data[0].get("current_credits", 0))
                new_balance = current_credits + tokens_allocated
                
                # Update with summed credits
                update_result = supabase.table("billing_usage").update({
                    "current_credits": new_balance
                }).eq("provider_id", provider_id).execute()
                
                if update_result.data:
                    logger.info(f"✅ [SUCCESS] Added {tokens_allocated} credits to user {provider_id}")
                    logger.info(f"   Old balance: {current_credits}, New balance: {new_balance}")
                    print(f"✅ Added {tokens_allocated} credits to user {provider_id}. New balance: {new_balance}")
                else:
                    logger.error(f"❌ Failed to update credits for user {provider_id}")
            else:
                # Initialize billing record if it doesn't exist
                insert_result = supabase.table("billing_usage").insert({
                    "provider_id": provider_id,
                    "current_credits": float(tokens_allocated),
                    "chat_token": 0,
                    "chat_cost": 0.0,
                    "platform_automation_count": 0,
                    "platform_automation_token": 0
                }).execute()
                
                if insert_result.data:
                    logger.info(f"✅ Initialized billing record with {tokens_allocated} credits for user {provider_id}")
                    print(f"✅ Initialized billing for {provider_id} with {tokens_allocated} credits")
                else:
                    logger.error(f"❌ Failed to initialize billing record for {provider_id}")
        
    except Exception as e:
        logger.error(f"❌ [SUBSCRIPTION ACTIVE ERROR] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def handle_subscription_renewed(event: dict):
    """
    Handle subscription renewal
    Resets token count for new billing period and adds new month's credits
    """
    try:
        data = event.get("data", {})
        subscription_id = data.get("subscription_id")
        
        logger.info(f"📅 [SUBSCRIPTION RENEWAL] Subscription {subscription_id} renewed")
        
        # Get original subscription to get token allocation
        sub = supabase.table("dodo_subscriptions").select("*").eq(
            "dodo_subscription_id", subscription_id
        ).single().execute()
        
        if not sub.data:
            logger.warning(f"⚠️ Subscription {subscription_id} not found for renewal")
            return
        
        # Reset tokens for new period
        tokens_allocated = sub.data.get("tokens_allocated", 0)
        provider_id = sub.data.get("provider_id")
        
        logger.info(f"   Provider ID: {provider_id}")
        logger.info(f"   Tokens to allocate: {tokens_allocated}")
        
        update_data = {
            "tokens_consumed": 0,  # Reset consumption
            "current_period_start": data.get("current_period_start"),
            "current_period_end": data.get("current_period_end"),
            "next_billing_date": data.get("next_billing_date"),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        supabase.table("dodo_subscriptions").update(update_data).eq(
            "dodo_subscription_id", subscription_id
        ).execute()
        
        logger.info(f"✅ Subscription {subscription_id} renewed. Tokens reset to {tokens_allocated}")
        
        # ADD NEW MONTH'S CREDITS TO BILLING_USAGE TABLE
        if provider_id and tokens_allocated > 0:
            logger.info(f"💰 [CREDIT UPDATE] Adding renewal credits...")
            # Get current credits
            billing_result = supabase.table("billing_usage").select("current_credits").eq(
                "provider_id", provider_id
            ).execute()
            
            if billing_result.data:
                current_credits = float(billing_result.data[0].get("current_credits", 0))
                new_balance = current_credits + tokens_allocated
                
                # Update with summed credits
                update_result = supabase.table("billing_usage").update({
                    "current_credits": new_balance
                }).eq("provider_id", provider_id).execute()
                
                if update_result.data:
                    logger.info(f"✅ [SUCCESS] Added {tokens_allocated} renewal credits to user {provider_id}")
                    logger.info(f"   Old balance: {current_credits}, New balance: {new_balance}")
                    print(f"✅ Added {tokens_allocated} renewal credits to user {provider_id}. New balance: {new_balance}")
                else:
                    logger.error(f"❌ Failed to update renewal credits for user {provider_id}")
            else:
                logger.warning(f"⚠️ No billing record found for user {provider_id} during renewal")
        
    except Exception as e:
        logger.error(f"❌ [RENEWAL ERROR] Error handling subscription.renewed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise


async def handle_subscription_cancelled(event: dict):
    """
    Handle subscription cancellation
    """
    try:
        data = event.get("data", {})
        subscription_id = data.get("subscription_id")
        
        update_data = {
            "status": "cancelled",
            "cancelled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        supabase.table("dodo_subscriptions").update(update_data).eq(
            "dodo_subscription_id", subscription_id
        ).execute()
        
        logger.info(f"Subscription {subscription_id} cancelled")
        
    except Exception as e:
        logger.error(f"Error handling subscription.cancelled: {str(e)}")
        raise


async def handle_subscription_expired(event: dict):
    """
    Handle subscription expiration
    """
    try:
        data = event.get("data", {})
        subscription_id = data.get("subscription_id")
        
        update_data = {
            "status": "expired",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        supabase.table("dodo_subscriptions").update(update_data).eq(
            "dodo_subscription_id", subscription_id
        ).execute()
        
        logger.info(f"Subscription {subscription_id} expired")
        
    except Exception as e:
        logger.error(f"Error handling subscription.expired: {str(e)}")
        raise


async def handle_payment_succeeded(event: dict):
    """
    Handle successful one-time payment
    Updates purchase status and allocates tokens
    This can be for either:
    1. One-time token purchases (pay-as-you-go)
    2. Subscription payments (initial or renewal)
    """
    try:
        data = event.get("data", {})
        payment_id = data.get("payment_id")
        metadata = data.get("metadata", {})
        provider_id = metadata.get("provider_id")
        tokens_from_metadata = metadata.get("tokens_allocated")
        
        logger.info(f"💳 [PAYMENT SUCCESS] Payment {payment_id} webhook received")
        logger.info(f"   Provider ID: {provider_id}")
        logger.info(f"   Tokens from metadata: {tokens_from_metadata}")
        
        # Validate provider_id exists
        if not provider_id:
            logger.error(f"❌ [PAYMENT ERROR] No provider_id found in metadata for payment {payment_id}")
            logger.error(f"   Metadata: {metadata}")
            raise ValueError("Missing provider_id in webhook metadata")
        
        # Try to find in one-time purchases first
        purchase_result = supabase.table("dodo_one_time_purchases").select("*").eq(
            "dodo_payment_id", payment_id
        ).execute()
        
        total_tokens = 0
        purchase_found = False
        
        if purchase_result.data:
            # This is a one-time purchase (pay-as-you-go)
            purchase = purchase_result.data[0]
            provider_id = purchase.get("provider_id")  # Override with DB value if different
            quantity = purchase.get("quantity", 0)
            tokens_per_package = purchase.get("tokens_per_package", 0)
            total_tokens = int(quantity) * int(tokens_per_package)
            purchase_found = True
            
            logger.info(f"✅ [ONE-TIME PURCHASE] Found purchase record:")
            logger.info(f"   Quantity: {quantity}")
            logger.info(f"   Tokens per package: {tokens_per_package}")
            logger.info(f"   Total tokens: {total_tokens}")
            
            # Update payment record
            update_data = {
                "status": "succeeded",
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            
            update_result = supabase.table("dodo_one_time_purchases").update(update_data).eq(
                "dodo_payment_id", payment_id
            ).execute()
            
            if not update_result.data:
                logger.warning(f"⚠️ Failed to update purchase status for {payment_id}, but continuing...")
            else:
                logger.info(f"✅ Purchase status updated to 'succeeded'")
        
        elif tokens_from_metadata:
            # This is likely a subscription payment - get tokens from metadata
            try:
                total_tokens = int(tokens_from_metadata)
                logger.info(f"✅ [SUBSCRIPTION] Using tokens from metadata: {total_tokens}")
            except (ValueError, TypeError):
                logger.error(f"❌ [PARSE ERROR] Could not parse tokens_allocated from metadata: {tokens_from_metadata}")
                total_tokens = 0
        else:
            logger.error(f"❌ [NO TOKENS FOUND] Payment {payment_id} not found in purchases and no tokens in metadata")
            logger.error(f"   Data: {data}")
            raise ValueError(f"Cannot determine tokens for payment {payment_id}")
        
        # Validate we have tokens to add
        if total_tokens <= 0:
            logger.error(f"❌ [INVALID TOKENS] Total tokens is zero or negative: {total_tokens}")
            raise ValueError(f"Invalid token count: {total_tokens}")
        
        # ADD PURCHASED CREDITS TO BILLING_USAGE TABLE
        logger.info(f"💰 [CREDIT UPDATE] Starting credit addition...")
        logger.info(f"   Provider ID: {provider_id}")
        logger.info(f"   Tokens to add: {total_tokens}")
        
        if not provider_id:
            logger.error(f"❌ [CRITICAL] Provider ID is None/empty. Cannot update billing_usage")
            raise ValueError("Provider ID is None")
        
        # Get current credits
        billing_result = supabase.table("billing_usage").select("current_credits").eq(
            "provider_id", provider_id
        ).execute()
        
        if billing_result.data:
            current_credits = float(billing_result.data[0].get("current_credits", 0))
            new_balance = current_credits + total_tokens
            
            logger.info(f"   Current balance: {current_credits}")
            logger.info(f"   New balance will be: {new_balance}")
            
            # Update with summed credits
            update_result = supabase.table("billing_usage").update({
                "current_credits": new_balance
            }).eq("provider_id", provider_id).execute()
            
            if update_result.data:
                logger.info(f"✅ [SUCCESS] Added {total_tokens} credits to user {provider_id}")
                logger.info(f"   Old balance: {current_credits}")
                logger.info(f"   New balance: {new_balance}")
                print(f"✅ [WEBHOOK] Added {total_tokens} purchase credits to user {provider_id}. New balance: {new_balance}")
            else:
                logger.error(f"❌ [UPDATE FAILED] Supabase update returned no data for provider {provider_id}")
                logger.error(f"   Update result: {update_result}")
                raise RuntimeError(f"Failed to update billing_usage for {provider_id}")
        else:
            # Initialize billing record if it doesn't exist
            logger.info(f"   No billing record found, creating new one...")
            insert_result = supabase.table("billing_usage").insert({
                "provider_id": provider_id,
                "current_credits": float(total_tokens),
                "chat_token": 0,
                "chat_cost": 0.0,
                "platform_automation_count": 0,
                "platform_automation_token": 0
            }).execute()
            
            if insert_result.data:
                logger.info(f"✅ [NEW RECORD] Initialized billing record with {total_tokens} credits for user {provider_id}")
                print(f"✅ [WEBHOOK] Initialized new billing record for {provider_id} with {total_tokens} credits")
            else:
                logger.error(f"❌ [INSERT FAILED] Failed to insert billing record for {provider_id}")
                logger.error(f"   Insert result: {insert_result}")
                raise RuntimeError(f"Failed to insert billing_usage for {provider_id}")
        
    except Exception as e:
        logger.error(f"❌ [CRITICAL ERROR] Error handling payment.succeeded: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"❌ [WEBHOOK ERROR] {str(e)}")
        raise


async def handle_payment_failed(event: dict):
    """
    Handle failed payment
    """
    try:
        data = event.get("data", {})
        payment_id = data.get("payment_id")
        
        update_data = {
            "status": "failed",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        supabase.table("dodo_one_time_purchases").update(update_data).eq(
            "dodo_payment_id", payment_id
        ).execute()
        
        logger.warning(f"Payment {payment_id} failed")
        
    except Exception as e:
        logger.error(f"Error handling payment.failed: {str(e)}")
        raise


@router.get("/health")
async def webhook_health_check():
    """
    Health check endpoint for webhook configuration
    DodoPay can ping this to verify your server is reachable
    """
    return APIResponse.success({
        "status": "healthy",
        "service": "Dodo Payments Webhooks",
        "endpoint": "/dodo-webhooks/event",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "webhook_secret_configured": bool(DODO_WEBHOOK_SECRET),
        "message": "Webhook endpoint is ready to receive events"
    })


@router.get("/events")
async def get_webhook_events(
    limit: int = 50,
    offset: int = 0,
    processed: Optional[bool] = None
):
    """
    Get webhook events for debugging/auditing
    """
    try:
        query = supabase.table("dodo_webhook_events").select("*")
        
        if processed is not None:
            query = query.eq("processed", processed)
        
        events = query.order("received_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()
        
        return APIResponse.success({
            "events": events.data or [],
            "count": len(events.data) if events.data else 0,
            "last_event_received": events.data[0]["received_at"] if events.data else None
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")


@router.post("/retry-event/{event_id}")
async def retry_failed_event(event_id: str):
    """
    Manually retry a failed webhook event
    Use the database ID (not the event_id field)
    """
    try:
        # Try to find by database ID first (numeric)
        try:
            db_id = int(event_id)
            event = supabase.table("dodo_webhook_events").select("*").eq(
                "id", db_id
            ).single().execute()
        except (ValueError, Exception):
            # If not numeric, try event_id field
            event = supabase.table("dodo_webhook_events").select("*").eq(
                "event_id", event_id
            ).single().execute()
        
        if not event.data:
            raise HTTPException(status_code=404, detail="Event not found")
        
        payload = event.data.get("payload", {})
        event_type = payload.get("event_type") or payload.get("type")
        db_record_id = event.data.get("id")
        
        logger.info(f"Retrying event ID {db_record_id}: {event_type}")
        
        # Route to handler
        if event_type == "subscription.active":
            await handle_subscription_active(payload)
        elif event_type == "subscription.renewed":
            await handle_subscription_renewed(payload)
        elif event_type == "payment.succeeded":
            await handle_payment_succeeded(payload)
        elif event_type == "subscription.cancelled":
            await handle_subscription_cancelled(payload)
        elif event_type == "subscription.expired":
            await handle_subscription_expired(payload)
        elif event_type == "payment.failed":
            await handle_payment_failed(payload)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown event type: {event_type}")
        
        # Mark as processed using database ID
        supabase.table("dodo_webhook_events").update({
            "processed": True,
            "processing_error": None,
            "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }).eq("id", db_record_id).execute()
        
        return APIResponse.success({
            "message": "Event reprocessed successfully",
            "database_id": db_record_id,
            "event_type": event_type
        })
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Failed to retry event: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to retry event: {str(e)}")


@router.post("/test-credit-addition")
async def test_credit_addition(
    user_id: str,
    credits_to_add: int
):
    """
    TEST ENDPOINT: Manually add credits to test the credit addition logic
    This simulates what webhooks do when payment succeeds
    """
    try:
        logger.info(f"TEST: Adding {credits_to_add} credits to user {user_id}")
        
        # Get current credits from billing_usage
        billing_result = supabase.table("billing_usage").select("current_credits").eq(
            "provider_id", user_id
        ).execute()
        
        if billing_result.data:
            current_credits = float(billing_result.data[0].get("current_credits", 0))
            new_balance = current_credits + credits_to_add
            
            # Update with summed credits
            supabase.table("billing_usage").update({
                "current_credits": new_balance
            }).eq("provider_id", user_id).execute()
            
            logger.info(f"TEST: Updated credits for {user_id}. Old: {current_credits}, Added: {credits_to_add}, New: {new_balance}")
            
            return APIResponse.success({
                "message": "Credits added successfully",
                "user_id": user_id,
                "previous_balance": current_credits,
                "credits_added": credits_to_add,
                "new_balance": new_balance
            })
        else:
            # Initialize billing record if it doesn't exist
            supabase.table("billing_usage").insert({
                "provider_id": user_id,
                "current_credits": float(credits_to_add),
                "chat_token": 0,
                "chat_cost": 0.0,
                "platform_automation_count": 0,
                "platform_automation_token": 0
            }).execute()
            
            logger.info(f"TEST: Initialized billing record with {credits_to_add} credits for user {user_id}")
            
            return APIResponse.success({
                "message": "Billing record initialized with credits",
                "user_id": user_id,
                "previous_balance": 0,
                "credits_added": credits_to_add,
                "new_balance": credits_to_add
            })
        
    except Exception as e:
        import traceback
        logger.error(f"TEST ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to add test credits: {str(e)}")


@router.post("/simulate-payment-webhook/{user_id}")
async def simulate_payment_webhook(user_id: str, tokens: int = 5000000):
    """
    ADMIN ENDPOINT: Simulate a payment.succeeded webhook for testing
    This manually triggers the credit addition as if a real payment succeeded
    """
    try:
        # Create a fake webhook payload that matches DodoPay structure
        fake_webhook = {
            "type": "payment.succeeded",
            "data": {
                "payment_id": f"test_pay_{user_id}_{datetime.datetime.now().timestamp()}",
                "customer_id": user_id,
                "status": "succeeded",
                "metadata": {
                    "provider_id": user_id,
                    "tokens_allocated": str(tokens)
                }
            }
        }
        
        # Manually call the payment succeeded handler
        await handle_payment_succeeded(fake_webhook)
        
        # Get updated balance
        balance_result = supabase.table("billing_usage").select("current_credits").eq(
            "provider_id", user_id
        ).execute()
        
        new_balance = balance_result.data[0].get("current_credits", 0) if balance_result.data else 0
        
        return APIResponse.success({
            "message": f"Simulated payment webhook - {tokens} credits added",
            "user_id": user_id,
            "tokens_added": tokens,
            "new_balance": new_balance
        })
        
    except Exception as e:
        import traceback
        logger.error(f"SIMULATION ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to simulate webhook: {str(e)}")
