from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from supabase_client import supabase
from utils.api_responses import APIResponse
import httpx
import logging
import json
from datetime import datetime

router = APIRouter(
    prefix="/instagram/insight",
    tags=["Instagram insight"]
)

logger = logging.getLogger(__name__)


INSTAGRAM_INSIGHT_URL = "https://graph.instagram.com/{ig_id}/insights"

async def get_access_token(platform_user_id: str) -> str:
    try:
        logger.info(f"Fetching access token for platform_user_id: {platform_user_id}")
        response = supabase.table("connected_accounts").select("access_token").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", "instagram").eq("connected", True).limit(1).maybe_single().execute()

        logger.info(f"Supabase response: {response}")
        
        if not response.data or not response.data.get("access_token"):
            logger.error(f"No access token found for platform_user_id: {platform_user_id}")
            raise Exception("Connected account or access token not found.")

        access_token = response.data["access_token"]
        logger.info(f"Successfully retrieved access token for platform_user_id: {platform_user_id}")
        return access_token
    except Exception as e:
        logger.error(f"Error in get_access_token: {str(e)}")
        raise

@router.get("/instagram-insight", status_code=200)
async def getInstagramInsight(platform_user_id: str):
    """
    Fetch Instagram insights for a given Instagram account (async).
    Returns comprehensive metrics for Business/Creator accounts.
    """
    logger.info(f"Fetching Instagram data for platform user ID: {platform_user_id}")
    
    if not platform_user_id:
        logger.error("platform_user_id is missing or empty")
        return JSONResponse(
            status_code=400,
            content={"error": "❌ Missing platform_user_id parameter"}
        )
    
    try:
        access_token = await get_access_token(platform_user_id)

        if not access_token:
            logger.error("No access token retrieved")
            return JSONResponse(
                status_code=400,
                content={"error": "❌ Missing or invalid access token"}
            )

        all_data = {}

        # Fetch profile information
        try:
            url_profile = f"https://graph.instagram.com/v24.0/{platform_user_id}"
            params_profile = {
                "fields": "id,username,name,biography,website,profile_picture_url,followers_count,follows_count,media_count",
                "access_token": access_token,
            }
            
            logger.info(f"Fetching profile information for user {platform_user_id}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response_profile = await client.get(url_profile, params=params_profile)
            
            if response_profile.status_code == 200:
                profile_data = response_profile.json()
                logger.info(f"✓ Profile data fetched successfully")
                
                # Store profile information
                all_data['profile'] = {
                    'username': profile_data.get('username', ''),
                    'name': profile_data.get('name', ''),
                    'biography': profile_data.get('biography', ''),
                    'website': profile_data.get('website', ''),
                    'profile_picture_url': profile_data.get('profile_picture_url', ''),
                    'followers_count': profile_data.get('followers_count', 0),
                    'follows_count': profile_data.get('follows_count', 0),
                    'media_count': profile_data.get('media_count', 0),
                }
            else:
                error_msg = response_profile.text if response_profile.text else "Unknown error"
                logger.warning(f"Failed to fetch profile data: HTTP {response_profile.status_code}")
                logger.warning(f"Error details: {error_msg}")
                
                # Try to parse Instagram error response
                try:
                    error_data = response_profile.json()
                    if 'error' in error_data:
                        logger.warning(f"Instagram error: {error_data['error'].get('message', 'Unknown')}")
                except:
                    pass
        except Exception as e:
            logger.warning(f"Error fetching profile: {str(e)}")

        # Fetch insights metrics (optimized - fetch all at once)
        try:
            url_insights = f"https://graph.instagram.com/v24.0/{platform_user_id}/insights"
            
            # All metrics we want to fetch
            metrics_list = [
                "reach",
                "website_clicks",
                "profile_views",
                "accounts_engaged",
                "total_interactions",
                "likes",
                "comments",
                "saves"
            ]
            
            metrics_str = ",".join(metrics_list)
            
            params_insights = {
                "metric": metrics_str,
                "metric_type": "total_value",
                "period": "days_28",
                "access_token": access_token,
            }
            
            logger.info(f"Fetching all metrics at once: {metrics_str}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response_insights = await client.get(url_insights, params=params_insights)
            
            if response_insights.status_code == 200:
                data = response_insights.json().get("data", [])
                logger.info(f"✓ Metrics fetch successful! Got {len(data)} metrics")
                
                # Process metrics
                for metric_data in data:
                    metric_name = metric_data.get("name")
                    if "total_value" in metric_data:
                        value = metric_data["total_value"].get("value", 0)
                        all_data[metric_name] = value
                        logger.info(f"✓ Metric '{metric_name}': {value}")
                    elif "values" in metric_data and len(metric_data["values"]) > 0:
                        value = metric_data["values"][-1].get("value", 0)
                        all_data[metric_name] = value
                        logger.info(f"✓ Metric '{metric_name}': {value}")
            else:
                logger.warning(f"Metrics fetch returned HTTP {response_insights.status_code}")
                # Try individual metrics as fallback
                for metric in metrics_list:
                    try:
                        params_single = {
                            "metric": metric,
                            "metric_type": "total_value",
                            "period": "days_28",
                            "access_token": access_token,
                        }
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response_single = await client.get(url_insights, params=params_single)
                        
                        if response_single.status_code == 200:
                            data = response_single.json().get("data", [])
                            if data and len(data) > 0:
                                metric_data = data[0]
                                if "total_value" in metric_data:
                                    all_data[metric] = metric_data["total_value"].get("value", 0)
                                elif "values" in metric_data and len(metric_data["values"]) > 0:
                                    all_data[metric] = metric_data["values"][-1].get("value", 0)
                                logger.info(f"✓ Fallback metric '{metric}': {all_data.get(metric)}")
                    except Exception as e:
                        logger.debug(f"Metric '{metric}' fallback failed: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error fetching insights: {str(e)}")
        
        if not all_data:
            logger.error("No data available - account may not be connected properly")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "❌ No data available",
                    "details": "Unable to fetch Instagram data",
                    "message": "Please ensure your Instagram account is properly connected and try again."
                }
            )
        
        logger.info(f"Successfully fetched {len(all_data)} data points")
        return JSONResponse(status_code=200, content=all_data)

    except Exception as e:
        logger.error(f"Exception in getInstagramInsight: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "⚠️ Internal Server Error", 
                "details": str(e),
                "message": "An unexpected error occurred while fetching Instagram data. Please try again later."
            }
        )


@router.get("/instagram-token-debug/{platform_user_id}", status_code=200)
async def debug_instagram_token(platform_user_id: str):
    """
    Debug endpoint to check if Instagram access token is valid.
    Helps diagnose "400 Bad Request" errors from Instagram API.
    """
    logger.info(f"🔍 Debugging access token for platform user ID: {platform_user_id}")
    
    try:
        # Get the access token
        response = supabase.table("connected_accounts").select("access_token, platform_user_id, platform, connected").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", "instagram").limit(1).maybe_single().execute()

        if not response.data:
            logger.warning(f"❌ No connected account found for {platform_user_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": "No connected Instagram account found",
                    "platform_user_id": platform_user_id
                }
            )

        account_data = response.data
        access_token = account_data.get("access_token")
        
        if not access_token:
            logger.error(f"❌ No access token stored for {platform_user_id}")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "No access token found in database",
                    "platform_user_id": platform_user_id,
                    "account_data": {
                        "connected": account_data.get("connected"),
                        "platform": account_data.get("platform")
                    }
                }
            )

        logger.info(f"✓ Found access token")
        
        # Test token by making a simple API call
        logger.info(f"Testing token validity by fetching account info...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to fetch just the ID (lightweight test)
                test_url = f"https://graph.instagram.com/v24.0/{platform_user_id}"
                test_params = {
                    "fields": "id,username",
                    "access_token": access_token
                }
                
                test_response = await client.get(test_url, params=test_params)
                
                logger.info(f"Instagram API response: HTTP {test_response.status_code}")
                
                if test_response.status_code == 200:
                    logger.info(f"✅ Token is valid!")
                    test_data = test_response.json()
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "valid",
                            "message": "Access token is valid",
                            "platform_user_id": platform_user_id,
                            "instagram_account": {
                                "id": test_data.get("id"),
                                "username": test_data.get("username")
                            },
                            "token_info": {
                                "token_length": len(access_token),
                                "stored_in_db": True,
                                "connected": account_data.get("connected")
                            }
                        }
                    )
                else:
                    # Token is invalid
                    logger.error(f"❌ Token validation failed: HTTP {test_response.status_code}")
                    error_body = test_response.text
                    
                    try:
                        error_json = test_response.json()
                        if "error" in error_json:
                            error_type = error_json["error"].get("type", "unknown")
                            error_message = error_json["error"].get("message", "Unknown error")
                            logger.error(f"Instagram error: [{error_type}] {error_message}")
                    except:
                        pass
                    
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "invalid",
                            "message": "Access token is invalid or expired",
                            "platform_user_id": platform_user_id,
                            "http_status": test_response.status_code,
                            "error_response": error_body[:500],
                            "next_steps": [
                                "1. Token may have expired - ask user to reconnect Instagram",
                                "2. Token may have been revoked - check Instagram app settings",
                                "3. Account may not have required permissions",
                                "4. Try re-authenticating the Instagram connection"
                            ],
                            "token_info": {
                                "token_length": len(access_token),
                                "stored_in_db": True,
                                "connected": account_data.get("connected")
                            }
                        }
                    )
                    
        except Exception as api_error:
            logger.error(f"❌ Error testing token: {str(api_error)}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to test token: {str(api_error)}",
                    "platform_user_id": platform_user_id,
                    "token_info": {
                        "token_length": len(access_token),
                        "stored_in_db": True,
                        "connected": account_data.get("connected")
                    }
                }
            )
    
    except Exception as e:
        logger.error(f"❌ Error in token debug: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "platform_user_id": platform_user_id
            }
        )


# ==================== WEBHOOK ENDPOINTS FOR REAL-TIME UPDATES ====================

@router.post("/webhook/comments")
async def instagram_comments_webhook(request: Request):
    """
    Instagram webhook endpoint to receive real-time comment notifications.
    Handles: comments, instagram_comment, instagram_mentioned_comment
    """
    try:
        body = await request.json()
        logger.info(f"🔔 WEBHOOK RECEIVED: {json.dumps(body, indent=2)}")
        
        # Extract webhook data
        entry = body.get("entry", [{}])[0] if body.get("entry") else {}
        changes = entry.get("changes", [])
        
        logger.info(f"Processing {len(changes)} changes")
        
        for change in changes:
            field = change.get("field")
            value = change.get("value", {})
            
            logger.info(f"Field: {field}, Value: {value}")
            
            # Handle different field types from Instagram
            if field in ["comments", "instagram_comment", "instagram_mentioned_comment", "instagram_live_comments"]:
                logger.info(f"✓ Comment event detected (field: {field})")
                
                # Extract comment data - Instagram sends nested structure
                comment_id = value.get("id") or value.get("comment_id")
                post_id = value.get("post_id")
                from_data = value.get("from", {})
                from_username = from_data.get("username") if isinstance(from_data, dict) else value.get("username")
                from_id = from_data.get("id") if isinstance(from_data, dict) else value.get("user_id")
                text = value.get("text") or value.get("message") or value.get("comment")
                timestamp = value.get("timestamp", datetime.now().isoformat())
                
                logger.info(f"📝 Comment: {from_username} - {text[:50] if text else 'No text'}")
                
                # Skip if missing critical data
                if not comment_id or not text:
                    logger.warning(f"Skipping comment - missing comment_id or text")
                    continue
                
                # Store comment in Supabase for real-time updates
                try:
                    comment_data = {
                        "comment_id": str(comment_id),
                        "post_id": str(post_id) if post_id else None,
                        "from_username": from_username or "unknown",
                        "from_id": str(from_id) if from_id else None,
                        "text": text,
                        "timestamp": timestamp,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    logger.info(f"💾 Storing comment: {comment_data}")
                    supabase.table("instagram_comments").insert(comment_data).execute()
                    logger.info(f"✅ Comment stored successfully: {comment_id}")
                    
                except Exception as db_error:
                    logger.error(f"❌ Failed to store comment in DB: {str(db_error)}")
        
        # Return 200 to acknowledge webhook reception
        logger.info("✓ Webhook acknowledged")
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        # Still return 200 so Instagram doesn't retry
        return JSONResponse(status_code=200, content={"status": "received"})


@router.get("/webhook/comments")
async def verify_instagram_webhook(request: Request):
    """
    Instagram webhook verification endpoint.
    Used by Instagram to verify the webhook URL.
    """
    try:
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        
        logger.info(f"🔐 Webhook verification attempt")
        logger.info(f"   Received token: {verify_token}")
        logger.info(f"   Challenge: {challenge}")
        
        # Use your verify token from Instagram webhook setup
        WEBHOOK_VERIFY_TOKEN = "chatverse_instagram_webhook_token_2024"
        
        if verify_token == WEBHOOK_VERIFY_TOKEN:
            logger.info("✅ Webhook verified successfully!")
            return int(challenge)
        else:
            logger.warning(f"❌ Webhook verification failed: token mismatch")
            logger.warning(f"   Expected: {WEBHOOK_VERIFY_TOKEN}")
            logger.warning(f"   Got: {verify_token}")
            return JSONResponse(status_code=403, content={"error": "Verification failed"})
            
    except Exception as e:
        logger.error(f"❌ Error verifying webhook: {str(e)}", exc_info=True)
        return JSONResponse(status_code=403, content={"error": "Verification failed"})


@router.get("/instagram-comments/{platform_user_id}")
async def get_instagram_comments(platform_user_id: str):
    """
    Fetch real-time comments for an Instagram account.
    Returns comments from the last 24 hours, ordered by newest first.
    """
    try:
        logger.info(f"Fetching comments for platform_user_id: {platform_user_id}")
        
        # Get user's Instagram account ID from connected_accounts
        response = supabase.table("connected_accounts").select("platform_user_id").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", "instagram").limit(1).execute()
        
        if not response.data:
            logger.warning(f"No Instagram account found for: {platform_user_id}")
            return JSONResponse(
                status_code=404,
                content={"error": "Instagram account not found"}
            )
        
        # Fetch comments from last 24 hours
        from datetime import timedelta
        time_threshold = (datetime.now() - timedelta(hours=24)).isoformat()
        
        try:
            comments_response = supabase.table("instagram_comments").select("*").eq(
                "from_id", platform_user_id
            ).gte("created_at", time_threshold).order("timestamp", desc=True).limit(50).execute()
            
            comments = comments_response.data or []
            
            logger.info(f"Retrieved {len(comments)} comments for {platform_user_id}")
            
            return JSONResponse(
                status_code=200,
                content={"comments": comments}
            )
        except Exception as db_error:
            error_msg = str(db_error)
            logger.error(f"Database error fetching comments: {error_msg}")
            
            # Check if it's a table not found error
            if "instagram_comments" in error_msg and ("not found" in error_msg.lower() or "PGRST205" in error_msg):
                logger.error("❌ instagram_comments table not found in database")
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Database table not configured",
                        "message": "The instagram_comments table needs to be created in Supabase",
                        "solution": "Run the SQL migration: SQL_database/instagram_comments.sql in Supabase SQL Editor",
                        "steps": [
                            "1. Go to Supabase Dashboard",
                            "2. Select your project",
                            "3. Go to SQL Editor",
                            "4. Click 'New Query'",
                            "5. Copy the contents of SQL_database/instagram_comments.sql",
                            "6. Run the query",
                            "7. Try again"
                        ]
                    }
                )
            else:
                # Other database errors
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Database error",
                        "message": error_msg[:200]
                    }
                )
    
    except Exception as e:
        logger.error(f"Error fetching comments: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to fetch comments", "details": str(e)}
        )


@router.post("/setup-webhook/{platform_user_id}")
async def setup_instagram_webhook(platform_user_id: str):
    """
    Setup Instagram webhook subscription for real-time comments.
    Requires the Instagram app to be configured with webhook capabilities.
    """
    try:
        logger.info(f"Setting up webhook for platform_user_id: {platform_user_id}")
        
        access_token = await get_access_token(platform_user_id)
        
        if not access_token:
            return JSONResponse(
                status_code=400,
                content={"error": "Access token not found"}
            )
        
        # Subscribe to comments field
        webhook_url = "https://your-domain.com/instagram/insight/webhook/comments"  # Update with your domain
        
        subscribe_params = {
            "fields": "comments,mentions",
            "object": "instagram",
            "callback_url": webhook_url,
            "verify_token": "chatverse_instagram_webhook_token_2024",
            "access_token": access_token
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.instagram.com/v24.0/{platform_user_id}/subscribed_apps",
                json=subscribe_params
            )
        
        if response.status_code in [200, 201]:
            logger.info(f"Webhook setup successful for {platform_user_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Webhook subscription activated",
                    "webhook_url": webhook_url
                }
            )
        else:
            logger.error(f"Webhook setup failed: {response.text}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Failed to setup webhook",
                    "details": response.text
                }
            )
        
    except Exception as e:
        logger.error(f"Error setting up webhook: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to setup webhook",
                "details": str(e)
            }
        )


@router.post("/webhook/test")
async def test_webhook(request: Request):
    """
    Test endpoint to simulate Instagram webhook for debugging.
    Send a test comment webhook notification.
    """
    try:
        # Simulate Instagram webhook payload
        test_payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "field": "comments",
                            "value": {
                                "id": "test_comment_123",
                                "post_id": "test_post_456",
                                "from": {
                                    "username": "test_user",
                                    "id": "test_user_id"
                                },
                                "text": "This is a test comment!",
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                    ]
                }
            ]
        }
        
        logger.info("🧪 TEST WEBHOOK RECEIVED")
        logger.info(f"Payload: {json.dumps(test_payload, indent=2)}")
        
        # Process it like a real webhook
        entry = test_payload.get("entry", [{}])[0]
        changes = entry.get("changes", [])
        
        for change in changes:
            field = change.get("field")
            value = change.get("value", {})
            
            if field == "comments":
                comment_id = value.get("id")
                text = value.get("text")
                from_username = value.get("from", {}).get("username")
                
                logger.info(f"✓ Test comment stored: {from_username} - {text}")
                
                try:
                    comment_data = {
                        "comment_id": str(comment_id),
                        "post_id": value.get("post_id"),
                        "from_username": from_username,
                        "from_id": value.get("from", {}).get("id"),
                        "text": text,
                        "timestamp": value.get("timestamp"),
                        "created_at": datetime.now().isoformat()
                    }
                    
                    supabase.table("instagram_comments").insert(comment_data).execute()
                    logger.info(f"✅ Test comment stored in database!")
                    
                except Exception as db_error:
                    logger.error(f"❌ Failed to store test comment: {str(db_error)}")
                    return JSONResponse(
                        status_code=500,
                        content={"error": f"Database error: {str(db_error)}"}
                    )
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Test comment processed successfully",
                "comment_stored": True
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in test webhook: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/webhook/debug/logs")
async def get_webhook_debug_logs():
    """
    Retrieve recent webhook event logs for debugging.
    Shows last 20 webhook events received.
    """
    try:
        logger.info("📋 Fetching webhook debug logs...")
        
        # Fetch last 20 comments from database
        response = supabase.table("instagram_comments").select(
            "id, comment_id, from_username, text, timestamp, created_at"
        ).order("created_at", desc=True).limit(20).execute()
        
        comments = response.data if response.data else []
        
        return JSONResponse(
            status_code=200,
            content={
                "total_comments_stored": len(comments),
                "recent_events": comments,
                "debug_info": {
                    "webhook_endpoint": "/instagram/insight/webhook/comments",
                    "verify_token": "chatverse_instagram_webhook_token_2024",
                    "table_name": "instagram_comments"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching logs: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/webhook/debug/clear")
async def clear_webhook_logs():
    """
    Clear all comments from the database (for testing/debugging).
    WARNING: This deletes all stored comments!
    """
    try:
        logger.warning("🗑️ CLEARING ALL WEBHOOK LOGS - DEBUG PURPOSE ONLY")
        
        # Delete all comments
        supabase.table("instagram_comments").delete().neq("id", 0).execute()
        
        logger.info("✅ All comments cleared")
        return JSONResponse(
            status_code=200,
            content={"status": "cleared", "message": "All webhook logs deleted"}
        )
        
    except Exception as e:
        logger.error(f"❌ Error clearing logs: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/webhook/debug/verify")
async def debug_verify_webhook():
    """
    Test webhook verification with correct token.
    Use this to verify your webhook setup works.
    """
    try:
        logger.info("🔧 Testing webhook verification...")
        
        # Test verification
        WEBHOOK_VERIFY_TOKEN = "chatverse_instagram_webhook_token_2024"
        test_challenge = "test_challenge_123"
        
        # Simulate what Instagram does
        verify_params = {
            "hub.verify_token": WEBHOOK_VERIFY_TOKEN,
            "hub.challenge": test_challenge
        }
        
        logger.info(f"Testing with verify_token: {WEBHOOK_VERIFY_TOKEN}")
        logger.info(f"Testing with challenge: {test_challenge}")
        
        # Check if token matches
        if verify_params["hub.verify_token"] == WEBHOOK_VERIFY_TOKEN:
            logger.info("✅ Verification would succeed!")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Webhook verification would pass",
                    "verify_token": WEBHOOK_VERIFY_TOKEN,
                    "challenge_response": int(test_challenge.replace("test_challenge_", "")),
                    "next_step": "Configure this verify token in Instagram Developer Console"
                }
            )
        else:
            logger.warning("❌ Verification would fail!")
            return JSONResponse(
                status_code=400,
                content={"error": "Token mismatch"}
            )
            
    except Exception as e:
        logger.error(f"❌ Error testing verification: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/webhook/debug/config")
async def debug_webhook_config():
    """
    Display current webhook configuration for debugging.
    Shows what settings the webhook is expecting.
    """
    try:
        logger.info("⚙️ Displaying webhook configuration...")
        
        WEBHOOK_VERIFY_TOKEN = "chatverse_instagram_webhook_token_2024"
        
        return JSONResponse(
            status_code=200,
            content={
                "webhook_configuration": {
                    "endpoint_url": "https://yourdomain.com/api/instagram/insight/webhook/comments",
                    "verify_token": WEBHOOK_VERIFY_TOKEN,
                    "http_method": "POST (for comments), GET (for verification)",
                    "event_types_subscribed": [
                        "comments",
                        "instagram_comment",
                        "instagram_mentioned_comment",
                        "instagram_live_comments"
                    ]
                },
                "database_table": "instagram_comments",
                "stored_fields": [
                    "id",
                    "comment_id",
                    "post_id",
                    "from_username",
                    "from_id",
                    "text",
                    "timestamp",
                    "created_at"
                ],
                "instagram_console_setup": {
                    "step_1": "Go to Instagram app settings",
                    "step_2": "Find Webhooks section",
                    "step_3": f"Set callback URL to: https://yourdomain.com/api/instagram/insight/webhook/comments",
                    "step_4": f"Set Verify Token to: {WEBHOOK_VERIFY_TOKEN}",
                    "step_5": "Subscribe to 'comments' field",
                    "step_6": "Click Verify and Save"
                },
                "local_testing": {
                    "verify_endpoint": "http://localhost:8000/api/instagram/insight/webhook/comments?hub.verify_token=chatverse_instagram_webhook_token_2024&hub.challenge=test123",
                    "test_webhook": "POST http://localhost:8000/api/instagram/insight/webhook/test",
                    "check_status": "GET http://localhost:8000/api/instagram/insight/webhook/status",
                    "view_logs": "GET http://localhost:8000/api/instagram/insight/webhook/debug/logs"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error getting config: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/webhook/status")
async def webhook_status():
    """
    Check webhook setup status and configuration.
    """
    try:
        logger.info("📊 Checking webhook status...")
        
        # Check if Supabase table exists
        try:
            count_response = supabase.table("instagram_comments").select("count", count="exact").limit(1).execute()
            table_count = count_response.count
            logger.info(f"✅ instagram_comments table exists with {table_count} records")
        except Exception as e:
            logger.warning(f"❌ instagram_comments table check failed: {str(e)}")
            table_count = None
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "operational",
                "webhook_url": "/instagram/insight/webhook/comments",
                "verify_token": "chatverse_instagram_webhook_token_2024",
                "test_endpoint": "/instagram/insight/webhook/test",
                "comments_table_exists": table_count is not None,
                "comments_count": table_count,
                "endpoints": {
                    "POST /webhook/comments": "Receive real-time comments",
                    "GET /webhook/comments": "Verification endpoint",
                    "GET /instagram-comments/{id}": "Fetch stored comments",
                    "POST /setup-webhook/{id}": "Setup webhook subscription",
                    "POST /webhook/test": "Test webhook (simulated)",
                    "GET /webhook/status": "Check webhook status",
                    "GET /webhook/debug/logs": "View recent webhook events",
                    "GET /webhook/debug/config": "View webhook configuration",
                    "GET /webhook/debug/verify": "Test verification endpoint",
                    "POST /webhook/debug/clear": "Clear all stored comments"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error checking status: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
