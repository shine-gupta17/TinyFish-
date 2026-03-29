import asyncio
import hashlib
import hmac
import logging
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from config import INSTAGRAM_CLIENT_SECRET
from supabase_client import supabase
# from redisclient.cachig import redis_cache
from instagram_routers.comment import handle_comment_automation
from instagram_routers.messaging import handle_messaging_automation
from instagram_routers.automation_core.shared_utils import (
    check_user_credits,
    pause_automation,
    get_provider_id
)
from utils.api_responses import APIResponse

router = APIRouter(
    prefix="/instagram",
    tags=["Instagram Webhooks"]
)

logger = logging.getLogger(__name__)

# In-memory cache to track processed message IDs to prevent duplicate processing
# Key: message_id, Value: timestamp
_processed_messages: dict = {}
_DEDUP_TTL_SECONDS = 300  # 5 minutes TTL for deduplication


def _cleanup_old_message_ids():
    """Remove expired message IDs from the deduplication cache."""
    import time
    current_time = time.time()
    expired_keys = [
        key for key, timestamp in _processed_messages.items()
        if current_time - timestamp > _DEDUP_TTL_SECONDS
    ]
    for key in expired_keys:
        del _processed_messages[key]


def _is_duplicate_message(message_id: str) -> bool:
    """
    Check if a message has already been processed.
    Returns True if duplicate, False if new message.
    """
    import time
    _cleanup_old_message_ids()
    
    if message_id in _processed_messages:
        logger.info(f"Duplicate message detected, skipping: {message_id[:30]}...")
        return True
    
    # Mark as processed
    _processed_messages[message_id] = time.time()
    return False


def _get_message_id(messaging_event: dict) -> str:
    """Extract unique message ID from messaging event."""
    # For messages, use 'mid'
    if "message" in messaging_event:
        return messaging_event["message"].get("mid", "")
    # For read receipts, use the mid in read object
    if "read" in messaging_event:
        return f"read_{messaging_event['read'].get('mid', '')}"
    # For reactions, use mid + action
    if "reaction" in messaging_event:
        reaction = messaging_event["reaction"]
        return f"reaction_{reaction.get('mid', '')}_{reaction.get('action', '')}"
    return ""


def _get_comment_id(change: dict) -> str:
    """Extract unique comment ID from change event."""
    value = change.get("value", {})
    return value.get("id", "")


# @redis_cache(prefix="automations", ttl=30)
def get_automation_config(platform_user_id: str):
    try:
        response = supabase.table("automations").select(
            "*"
        ).eq("platform_user_id", platform_user_id).eq("activation_status", "ACTIVE").execute()
        return response.data
    except Exception as e:
        logger.error(f"Failed to fetch automation config from DB for {platform_user_id}: {e}")
        return None

@router.get("/webhooks")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    challenge = params.get("hub.challenge")
    token = params.get("hub.verify_token")

    if mode == "subscribe" and token == "instabot":
        logger.info("Webhook verification successful.")
        return PlainTextResponse(content=challenge, status_code=200)
    else:
        logger.warning("Webhook verification failed.")
        return APIResponse.error(403, "Webhook verification failed")

@router.post("/subscribe")
async def subscribe_to_webhooks(
    platform_user_id: str,
    fields: list[str] = None
):
    """
    Enable webhook subscriptions for an Instagram account.
    This must be called after connecting an Instagram account to receive webhook events.
    
    Args:
        platform_user_id: Instagram Business Account ID
        fields: List of webhook fields to subscribe to
    
    Returns:
        Subscription status
    """
    if fields is None:
        fields = ["messages", "comments","live_comments"]
    
    try:
        # Get access token for this Instagram account
        from instagram_routers.insta_utils import get_access_token
        
        access_token = await get_access_token(platform_user_id)
        
        if not access_token:
            return APIResponse.error(404, f"No access token found for platform_user_id: {platform_user_id}")
        
        # Subscribe to webhook fields
        url = f"https://graph.instagram.com/v23.0/{platform_user_id}/subscribed_apps"
        params = {
            "subscribed_fields": ",".join(fields),
            "access_token": access_token
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params)
            response.raise_for_status()
            result = response.json()
        
        logger.info(f"Successfully subscribed to webhooks for {platform_user_id}: {fields}")
        
        return APIResponse.success(
            data={
                "platform_user_id": platform_user_id,
                "subscribed_fields": fields,
                "response": result
            },
            message="Webhook subscription enabled successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to subscribe to webhooks for {platform_user_id}: {e}")
        return APIResponse.error(500, f"Failed to enable webhook subscription: {str(e)}")


@router.get("/subscription-status/{platform_user_id}")
async def get_subscription_status(platform_user_id: str):
    """
    Check current webhook subscription status for an Instagram account.
    
    Args:
        platform_user_id: Instagram Business Account ID
    
    Returns:
        Current subscription fields
    """
    try:
        from instagram_routers.insta_utils import get_access_token
        
        access_token = await get_access_token(platform_user_id)
        
        if not access_token:
            return APIResponse.error(404, f"No access token found for platform_user_id: {platform_user_id}")
        
        url = f"https://graph.instagram.com/v23.0/{platform_user_id}/subscribed_apps"
        params = {"access_token": access_token}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
        
        return APIResponse.success(
            data=result,
            message="Subscription status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get subscription status for {platform_user_id}: {e}")
        return APIResponse.error(500, f"Failed to get subscription status: {str(e)}")


@router.get("/health-check/{platform_user_id}")
async def webhook_health_check(platform_user_id: str):
    """
    Comprehensive health check for webhook setup.
    Verifies:
    - Access token exists
    - Webhook subscriptions are active
    - Automation config exists
    
    Args:
        platform_user_id: Instagram Business Account ID
    
    Returns:
        Health status with details
    """
    try:
        from instagram_routers.insta_utils import get_access_token
        
        # Check access token
        try:
            access_token = await get_access_token(platform_user_id)
            token_status = "valid" if access_token else "invalid"
        except Exception:
            token_status = "invalid"
            access_token = None
        
        # Check webhook subscription
        subscription_status = "unknown"
        subscribed_fields = []
        
        if token_status == "valid":
            try:
                url = f"https://graph.instagram.com/v23.0/{platform_user_id}/subscribed_apps"
                params = {"access_token": access_token}
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get("data"):
                        subscribed_fields = result["data"][0].get("subscribed_fields", [])
                        subscription_status = "active" if subscribed_fields else "inactive"
                    else:
                        subscription_status = "inactive"
            except Exception as e:
                logger.error(f"Error checking webhook subscription: {e}")
                subscription_status = "error"
        
        # Check automation config
        automations = get_automation_config(platform_user_id)
        automation_count = len(automations) if automations else 0
        
        return APIResponse.success(
            data={
                "platform_user_id": platform_user_id,
                "access_token_status": token_status,
                "webhook_subscription_status": subscription_status,
                "subscribed_fields": subscribed_fields,
                "active_automations": automation_count,
                "healthy": token_status == "valid" and subscription_status == "active" and automation_count > 0
            },
            message="Health check completed"
        )
        
    except Exception as e:
        logger.error(f"Health check failed for {platform_user_id}: {e}")
        return APIResponse.error(500, f"Health check failed: {str(e)}")

def identify_messaging_event_type(messaging_event: dict) -> str:
    """
    Identify the type of messaging event from the webhook payload.
    
    Returns one of:
    - "user_text_message": User sent a text message
    - "user_image_message": User sent an image
    - "user_audio_message": User sent a voice message
    - "user_attachment_message": User sent other attachment type
    - "ai_echo_text": AI agent sent a text message (echo)
    - "ai_echo_image": AI agent sent an image (echo)
    - "ai_echo_attachment": AI agent sent other attachment (echo)
    - "message_read": User read a message
    - "message_reaction": User reacted to a message
    - "unknown": Unknown event type
    """
    # Check for read receipt
    if "read" in messaging_event:
        return "message_read"
    
    # Check for reaction
    if "reaction" in messaging_event:
        return "message_reaction"
    
    # Check for message
    if "message" in messaging_event:
        message = messaging_event["message"]
        is_echo = message.get("is_echo", False)
        has_attachments = "attachments" in message
        
        if is_echo:
            # AI agent sent this message
            if has_attachments:
                attachment_type = message["attachments"][0].get("type", "unknown")
                if attachment_type == "image":
                    return "ai_echo_image"
                elif attachment_type == "audio":
                    return "ai_echo_audio"
                else:
                    return "ai_echo_attachment"
            else:
                return "ai_echo_text"
        else:
            # User sent this message
            if has_attachments:
                attachment_type = message["attachments"][0].get("type", "unknown")
                if attachment_type == "image":
                    return "user_image_message"
                elif attachment_type == "audio":
                    return "user_audio_message"
                else:
                    return "user_attachment_message"
            else:
                return "user_text_message"
    
    return "unknown"


def should_process_messaging_event(event_type: str) -> bool:
    """
    Determine if the messaging event should be processed by the automation.
    
    We should process:
    - User text messages
    - User image messages
    - User audio messages
    - User other attachments
    
    We should NOT process (just log):
    - AI echo messages (already sent by us)
    - Message read receipts
    - Message reactions
    """
    processable_events = [
        "user_text_message",
        "user_image_message", 
        "user_audio_message",
        "user_attachment_message"
    ]
    return event_type in processable_events


@router.post("/webhooks")
async def handle_webhook(request: Request):
    """
    Handle Instagram webhook events.
    
    IMPORTANT: This endpoint returns immediately after signature validation
    to prevent Instagram from retrying. All processing is done asynchronously
    using asyncio.create_task() to support concurrent conversations with
    multiple users/providers.
    """
    try:
        raw_body = await request.body()
        signature = request.headers.get("x-hub-signature-256")

        if not signature:
            logger.warning("Missing X-Hub-Signature-256 header")
            return APIResponse.error(400, "Missing X-Hub-Signature-256 header")

        expected_signature = "sha256=" + hmac.new(
            INSTAGRAM_CLIENT_SECRET.encode(),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            logger.warning("Invalid request signature")
            return APIResponse.error(403, "Invalid request signature")

        # Parse payload
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook payload: {e}")
            # Still return success to prevent retries
            return APIResponse.success(message="Webhook received")

        logger.info(f"Received webhook payload: {payload}")

        # Create async task for background processing - true parallel execution
        # This allows handling multiple conversations concurrently
        asyncio.create_task(_process_webhook_payload_async(payload))

        # Return success immediately to prevent Instagram retries
        return APIResponse.success(message="Webhook received successfully")
    
    except Exception as e:
        # Even on error, return success to prevent infinite retries
        logger.error(f"Error in webhook handler: {e}", exc_info=True)
        return APIResponse.success(message="Webhook received")


async def _process_webhook_payload_async(payload: dict):
    """
    Process webhook payload asynchronously with true parallel execution.
    
    Each entry (different platform_user_id/provider) is processed concurrently
    using asyncio.gather() for maximum parallelism.
    """
    try:
        entries = payload.get("entry", [])
        
        if not entries:
            return
        
        # Process all entries concurrently - each entry may be from different provider
        tasks = [_process_webhook_entry_async(entry) for entry in entries]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}", exc_info=True)


async def _process_webhook_entry_async(entry: dict):
    """
    Process a single webhook entry asynchronously.
    
    Each entry represents events from one platform_user_id.
    All messaging and comment events within the entry are processed concurrently.
    """
    try:
        platform_user_id = entry.get("id")
        if not platform_user_id:
            return

        automations = get_automation_config(platform_user_id)
        logger.info(f"Processing entry for platform_user_id: {platform_user_id}")
        
        if automations is None or len(automations) == 0:
            logger.info(f"No active automations found for platform_user_id: {platform_user_id}")
            return
            
        # Get provider_id for credit check (do this once per entry)
        provider_id = await get_provider_id(platform_user_id)
        
        if not provider_id:
            logger.warning(f"No provider_id found for platform_user_id {platform_user_id}, skipping automation")
            return
        
        # Check if user has sufficient credits
        credit_check = await check_user_credits(provider_id)
        
        if not credit_check.get("has_credits", False):
            logger.warning(
                f"Insufficient credits for provider {provider_id}. "
                f"Current credits: {credit_check.get('current_credits', 0)}. "
                f"Pausing all automations for this user."
            )
            
            # Pause all automations for this user concurrently
            pause_tasks = [pause_automation(automation.get('automation_id')) for automation in automations]
            await asyncio.gather(*pause_tasks, return_exceptions=True)
            return
        
        # Collect all tasks for concurrent processing
        tasks = []
        
        # Handle messaging events (DMs) - create task for each
        for messaging_event in entry.get("messaging", []):
            tasks.append(_process_messaging_event_async(messaging_event, automations, platform_user_id))

        # Handle comment events - create task for each
        for change in entry.get("changes", []):
            tasks.append(_process_comment_event_async(change, automations, platform_user_id))
        
        # Execute all event processing concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    except Exception as e:
        logger.error(f"Error processing webhook entry: {e}", exc_info=True)


async def _process_messaging_event_async(messaging_event: dict, automations: list, platform_user_id: str):
    """Process a single messaging event with deduplication and concurrent automation handling."""
    try:
        # Check for duplicate message
        message_id = _get_message_id(messaging_event)
        if message_id and _is_duplicate_message(message_id):
            return
        
        event_type = identify_messaging_event_type(messaging_event)
        logger.info(f"Messaging event type identified: {event_type}")
        
        # Skip events that shouldn't be processed
        if not should_process_messaging_event(event_type):
            if event_type == "message_read":
                logger.debug(f"Message read receipt received, skipping processing")
            elif event_type == "message_reaction":
                reaction_data = messaging_event.get("reaction", {})
                logger.debug(f"Message reaction received: {reaction_data.get('emoji', 'unknown')}, skipping processing")
            elif event_type.startswith("ai_echo"):
                logger.debug(f"AI echo message received ({event_type}), skipping processing")
            else:
                logger.debug(f"Unknown or non-processable event type: {event_type}, skipping")
            return
        
        # Process user messages through all automations concurrently
        async def process_single_automation(automation):
            try:
                await handle_messaging_automation.handle_messaging_automation(
                    messaging_event, 
                    automation, 
                    platform_user_id,
                    event_type=event_type
                )
            except Exception as e:
                logger.error(f"Error processing messaging automation {automation.get('automation_id')}: {e}", exc_info=True)
        
        # Run all automations concurrently
        tasks = [process_single_automation(automation) for automation in automations]
        await asyncio.gather(*tasks, return_exceptions=True)
                
    except Exception as e:
        logger.error(f"Error processing messaging event: {e}", exc_info=True)


async def _process_comment_event_async(change: dict, automations: list, platform_user_id: str):
    """Process a single comment event with deduplication and concurrent automation handling."""
    try:
        if change.get("field") != "comments":
            return
        
        # Check for duplicate comment
        comment_id = _get_comment_id(change)
        if comment_id and _is_duplicate_message(f"comment_{comment_id}"):
            return
        
        logger.info(f"Comment event received")
        
        # Process comment through all automations concurrently
        async def process_single_automation(automation):
            try:
                await handle_comment_automation.handle_comment_automation(
                    change, 
                    automation, 
                    platform_user_id
                )
            except Exception as e:
                logger.error(f"Error processing comment automation {automation.get('automation_id')}: {e}", exc_info=True)
        
        # Run all automations concurrently
        tasks = [process_single_automation(automation) for automation in automations]
        await asyncio.gather(*tasks, return_exceptions=True)
                
    except Exception as e:
        logger.error(f"Error processing comment event: {e}", exc_info=True)