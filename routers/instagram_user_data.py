# routers/instagram_user_data.py

import httpx
import asyncio
import logging
from typing import Optional, Dict, Tuple
from fastapi import APIRouter, Query
from supabase_client import supabase
from models.api_models import SendMessagePayload
from utils.api_responses import APIResponse
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/instagram",
    tags=["Instagram User Data"]
)

logger = logging.getLogger(__name__)

async def get_access_token(platform_user_id: str) -> Tuple[str, str]:
    """Helper to fetch access token from the database."""
    try:
        response = supabase.table("connected_accounts").select("access_token, platform_user_id").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", "instagram").eq("connected", True).limit(1).execute()

        if not response.data:
            raise APIResponse.error(404, "No connected Instagram account found.")
        
        account = response.data[0]
        access_token = account.get("access_token")

        if not access_token:
            raise APIResponse.error(400, "Access token is missing for this account.")
        
        # print("access_token =>>>: ",access_token)
        return access_token, account.get("platform_user_id")

    except Exception as e:
        logger.error(f"Error fetching access token for {platform_user_id}: {e}")
        if isinstance(e):
            raise e
        raise APIResponse.error(500, "Failed to fetch access token.")
    
@router.post("/send-dm-from-comment")
async def send_dm_from_comment(
    comment_id: str,
    message_type: str,
    message: str,
    platform_user_id:str
):
    if message_type != "text":
        raise HTTPException(status_code=400, detail="Only 'text' message_type is supported")
    
    access_token, puid = await get_access_token(platform_user_id=platform_user_id)
    
    # Use the Instagram Business Account ID (puid)
    url = f"https://graph.instagram.com/v23.0/{puid}/messages"
    
    payload = {
        "recipient": {
            "comment_id": comment_id
        },
        "message": {
            "text": message
        },
        "access_token": access_token  # Instagram Graph API typically uses access_token in body or query param
    }

    print("*"*10)
    print(f"URL: {url}")
    print(f"IG Account ID (puid): {puid}")
    print(f"Comment ID: {comment_id}")
    print(f"Payload: {payload}")
    print("*"*10)

    async with httpx.AsyncClient() as client:
        # Try with access_token as query parameter instead of header
        response = await client.post(url, json=payload)

    print("*****send-dm-from-comment ==> ",response.status_code)
    print("*****Response body ==> ", response.text)

    if response.status_code != 200:
        logger.error(f"Failed to send DM from comment {comment_id}: Status={response.status_code}, Response={response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()

@router.get("/me")
async def get_user_info(platform_user_id: str = Query(...)):
    """Fetches basic profile information for the connected Instagram account."""
    try:
        access_token, puid = await get_access_token(platform_user_id)
        async with httpx.AsyncClient() as client:
            url = f"https://graph.instagram.com/v23.0/me?fields=id,username,account_type&access_token={access_token}"
            res = await client.get(url)
            res.raise_for_status()
            return APIResponse.success(data=res.json(), message="User info fetched successfully")
    except httpx.HTTPStatusError as e:
        return APIResponse.error(e.response.status_code, f"Failed to fetch user info: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in get_user_info: {e}")
        return APIResponse.error(500, "An internal server error occurred.")

@router.get("/conversations")
async def get_conversation_list(platform_user_id: str = Query(...)):
    """Fetches a list of conversations for the account."""
    try:
        access_token, puid = await get_access_token(platform_user_id)
        url = f"https://graph.instagram.com/v23.0/me/conversations?platform=instagram&access_token={access_token}&fields=id,participants"
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            res.raise_for_status()
            return APIResponse.success(data=res.json(), message="Conversations fetched successfully")
    except httpx.HTTPStatusError as e:
        return APIResponse.error(e.response.status_code, f"Failed to fetch conversations: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in get_conversation_list: {e}")
        return APIResponse.error(500, "An internal server error occurred.")

@router.get("/messages")
async def get_messages_in_conversation(
    conversation_id: str = Query(...),
    platform_user_id: str = Query(...),
    after: Optional[str] = Query(None)
):
    """Fetches all messages within a specific conversation, with pagination."""
    try:
        access_token, puid = await get_access_token(platform_user_id)
        
        async def fetch_message_detail(client: httpx.AsyncClient, msg_id: str) -> Dict:
            detail_url = f"https://graph.instagram.com/v23.0/{msg_id}?fields=id,created_time,from,to,message&access_token={access_token}"
            try:
                res = await client.get(detail_url)
                res.raise_for_status()
                return res.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to fetch message {msg_id}: {e}")
                return {"id": msg_id, "error": f"Failed to fetch details: {e}"}

        async with httpx.AsyncClient() as client:
            convo_url = f"https://graph.instagram.com/v23.0/{conversation_id}/messages?access_token={access_token}"
            if after:
                convo_url += f"&after={after}"
            
            convo_res = await client.get(convo_url)
            convo_res.raise_for_status()
            convo_data = convo_res.json()
            
            message_items = convo_data.get("data", [])
            paging_info = convo_data.get("paging", {})

            tasks = [fetch_message_detail(client, msg["id"]) for msg in message_items]
            full_messages = await asyncio.gather(*tasks)

            response_data = {
                "messages": full_messages,
                "pagination": paging_info
            }
            return APIResponse.success(data=response_data, message="Messages fetched successfully")

    except httpx.HTTPStatusError as e:
        return APIResponse.error(e.response.status_code, f"Failed to fetch messages: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in get_messages_in_conversation: {e}")
        return APIResponse.error(500, "An internal server error occurred.")

@router.post("/send-message")
async def send_message(payload: SendMessagePayload):
    """Sends a text message to a recipient on Instagram."""
    try:
        access_token, puid = await get_access_token(payload.platform_user_id)
        url = f"https://graph.instagram.com/v23.0/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        json_data = {
            "recipient": {"id": payload.recipient_id},
            "message": {"text": payload.message},
            "messaging_type": "RESPONSE"
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=json_data)
            res.raise_for_status()
            return APIResponse.success(data=res.json(), message="Message sent successfully")

    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on send: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to send message: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}")
        return APIResponse.error(500, "An internal server error occurred")

@router.get("/all-media")
async def get_all_media(
    platform_user_id: str = Query(...),
    limit: int = Query(25, ge=1, le=100, description="Number of media items to fetch")
):
    """
    Fetches ALL Instagram media (posts, reels, stories) without any filtering.
    Useful for debugging and seeing exactly what Instagram API returns.
    """
    try:
        access_token, ig_user_id = await get_access_token(platform_user_id)

        url = f"https://graph.instagram.com/{ig_user_id}/media"
        params = {
            "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
            "access_token": access_token,
            "limit": limit
        }

        async with httpx.AsyncClient() as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            
            data = res.json()
            total_count = len(data.get('data', []))
            logger.info(f"Fetched {total_count} total media items (no filtering applied)")
            
            # Count media types for debugging
            if 'data' in data and data['data']:
                media_types = {}
                media_product_types = {}
                
                for item in data['data']:
                    # Count media_type (IMAGE, VIDEO, CAROUSEL_ALBUM)
                    m_type = item.get('media_type', 'UNKNOWN')
                    media_types[m_type] = media_types.get(m_type, 0) + 1
                    
                    # Count media_product_type (FEED, REELS, etc.)
                    product_type = item.get('media_product_type', 'NONE/MISSING')
                    media_product_types[product_type] = media_product_types.get(product_type, 0) + 1
                
                logger.info(f"Media TYPE breakdown: {media_types}")
                logger.info(f"Media PRODUCT TYPE breakdown: {media_product_types}")
                
                # Log first 3 items in detail
                for i, item in enumerate(data['data'][:3]):
                    logger.info(f"Item {i+1}: id={item.get('id')}, type={item.get('media_type')}, product={item.get('media_product_type', 'MISSING')}, caption={item.get('caption', '')[:50]}")
            
            return APIResponse.success(data=data, message=f"Fetched all {total_count} media items successfully")    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on fetching all media: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to fetch media: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in get_all_media: {e}")
        return APIResponse.error(500, "An internal server error occurred")
    
def _is_reel(item: dict) -> bool:
    """
    Helper function to detect if a media item is a reel.
    Uses multiple detection methods for reliability.
    """
    # Method 1: Check media_product_type field
    product_type = item.get('media_product_type', '')
    if product_type:
        if product_type.upper() in ['REELS', 'REEL']:
            return True
    
    # Method 2: Check permalink URL pattern (reels have /reel/, posts have /p/)
    permalink = item.get('permalink', '')
    if permalink and '/reel/' in permalink.lower():
        return True
    
    return False


def _is_video(item: dict) -> bool:
    """
    Helper function to detect if a media item is a video (including reels).
    """
    media_type = item.get('media_type', '')
    return media_type.upper() == 'VIDEO'


def _is_image_post(item: dict) -> bool:
    """
    Helper function to check if media is an image post (IMAGE or CAROUSEL).
    Excludes videos and reels.
    """
    # First check if it's a reel - exclude reels
    if _is_reel(item):
        return False
    
    # Check media type - only IMAGE or CAROUSEL_ALBUM
    media_type = item.get('media_type', '')
    return media_type.upper() in ['IMAGE', 'CAROUSEL_ALBUM']


@router.get("/posts")
async def get_posts(
    platform_user_id: str = Query(...),
    include_reels: bool = Query(False, description="Include reels in the results"),
    include_videos: bool = Query(False, description="Include video posts (excludes reels)"),
    limit: int = Query(25, ge=1, le=100, description="Number of posts to fetch")
):
    """
    Fetches Instagram posts for the given platform_user_id.
    
    By default:
    - Excludes REELS
    - Excludes VIDEO posts  
    - Returns only IMAGE and CAROUSEL posts
    
    Use include_reels=true to include reels.
    Use include_videos=true to include regular video posts (not reels).
    
    This endpoint intelligently filters using:
    1. media_product_type field
    2. Permalink URL pattern (/reel/ vs /p/)
    3. media_type (IMAGE, VIDEO, CAROUSEL_ALBUM)
    
    If needed, it will fetch additional pages to ensure you get the requested number of posts.
    """
    try:
        access_token, ig_user_id = await get_access_token(platform_user_id)

        url = f"https://graph.instagram.com/{ig_user_id}/media"
        
        all_posts = []
        fetched_count = 0
        max_fetch = 100  # Safety limit to prevent infinite loops
        next_url = None
        
        async with httpx.AsyncClient() as client:
            # Keep fetching until we have enough posts or reach max
            while len(all_posts) < limit and fetched_count < max_fetch:
                # Fetch more items than requested to account for filtering
                fetch_limit = min(50, max_fetch - fetched_count)
                
                if next_url:
                    # Use pagination URL
                    fetch_url = next_url
                    logger.info(f"Fetching next page of media (already have {len(all_posts)} posts)")
                else:
                    # Initial fetch
                    params = {
                        "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
                        "access_token": access_token,
                        "limit": fetch_limit
                    }
                    fetch_url = url
                
                res = await client.get(fetch_url, params=params if not next_url else None)
                res.raise_for_status()
                
                data = res.json()
                items = data.get('data', [])
                fetched_count += len(items)
                
                logger.info(f"Fetched {len(items)} media items. Total fetched: {fetched_count}")
                
                # Debug: Log first item structure on initial fetch
                if len(all_posts) == 0 and len(items) > 0:
                    first_item = items[0]
                    logger.info(f"First item: id={first_item.get('id')}, type={first_item.get('media_type')}, product={first_item.get('media_product_type')}, permalink={first_item.get('permalink')}")
                
                # Filter items based on flags
                for item in items:
                    is_reel = _is_reel(item)
                    is_video = _is_video(item)
                    media_type = item.get('media_type', '')
                    
                    should_include = False
                    skip_reason = None
                    
                    if is_reel:
                        if include_reels:
                            should_include = True
                        else:
                            skip_reason = "REEL"
                    elif is_video:
                        if include_videos:
                            should_include = True
                        else:
                            skip_reason = "VIDEO"
                    else:
                        # It's an image or carousel - always include
                        should_include = True
                    
                    if should_include:
                        all_posts.append(item)
                        logger.debug(f"Keeping {media_type}: {item.get('id')}, permalink: {item.get('permalink')}")
                    else:
                        logger.debug(f"Filtering out {skip_reason}: {item.get('id')}, type={media_type}, permalink: {item.get('permalink')}")
                    
                    # Stop if we have enough posts
                    if len(all_posts) >= limit:
                        break
                
                # Check if there's a next page
                paging = data.get('paging', {})
                next_url = paging.get('next')
                
                # Break if no more pages or we have enough posts
                if not next_url or len(all_posts) >= limit:
                    break
            
            # Trim to requested limit
            all_posts = all_posts[:limit]
            
            logger.info(f"Final result: Returning {len(all_posts)} posts (images/carousels) after filtering. Total fetched: {fetched_count}")
            
            result_data = {
                'data': all_posts,
                'paging': {} if not next_url else {'next': next_url}
            }
            
            return APIResponse.success(data=result_data, message=f"Fetched {len(all_posts)} posts successfully")    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on fetching posts: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to fetch posts: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in get_posts: {e}")
        return APIResponse.error(500, "An internal server error occurred")


@router.get("/images")
async def get_image_posts(
    platform_user_id: str = Query(...),
    limit: int = Query(25, ge=1, le=100, description="Number of image posts to fetch")
):
    """
    Fetches ONLY image posts (IMAGE and CAROUSEL_ALBUM types).
    
    This endpoint:
    - Excludes ALL videos (reels and regular video posts)
    - Returns only IMAGE and CAROUSEL_ALBUM posts
    - Perfect for "fetch latest post" queries where you want images only
    
    If needed, it will fetch additional pages to ensure you get the requested number of image posts.
    """
    try:
        access_token, ig_user_id = await get_access_token(platform_user_id)

        url = f"https://graph.instagram.com/{ig_user_id}/media"
        
        all_images = []
        fetched_count = 0
        max_fetch = 100  # Safety limit
        next_url = None
        
        async with httpx.AsyncClient() as client:
            while len(all_images) < limit and fetched_count < max_fetch:
                fetch_limit = min(50, max_fetch - fetched_count)
                
                if next_url:
                    fetch_url = next_url
                    logger.info(f"Fetching next page (already have {len(all_images)} image posts)")
                else:
                    params = {
                        "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
                        "access_token": access_token,
                        "limit": fetch_limit
                    }
                    fetch_url = url
                
                res = await client.get(fetch_url, params=params if not next_url else None)
                res.raise_for_status()
                
                data = res.json()
                items = data.get('data', [])
                fetched_count += len(items)
                
                logger.info(f"Fetched {len(items)} media items for image filtering. Total fetched: {fetched_count}")
                
                # Filter: Only keep IMAGE and CAROUSEL_ALBUM posts
                for item in items:
                    if _is_image_post(item):
                        all_images.append(item)
                        logger.debug(f"Keeping IMAGE POST: {item.get('id')}, type={item.get('media_type')}")
                    else:
                        logger.debug(f"Filtering out: {item.get('id')}, type={item.get('media_type')}, is_reel={_is_reel(item)}")
                    
                    if len(all_images) >= limit:
                        break
                
                paging = data.get('paging', {})
                next_url = paging.get('next')
                
                if not next_url or len(all_images) >= limit:
                    break
            
            all_images = all_images[:limit]
            
            logger.info(f"Final: Returning {len(all_images)} image posts. Total fetched: {fetched_count}")
            
            result_data = {
                'data': all_images,
                'paging': {} if not next_url else {'next': next_url}
            }
            
            return APIResponse.success(data=result_data, message=f"Fetched {len(all_images)} image posts successfully")    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on fetching images: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to fetch images: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in get_image_posts: {e}")
        return APIResponse.error(500, "An internal server error occurred")


@router.get("/post/{post_id}")
async def get_post_by_id(post_id: str, platform_user_id: str = Query(...)):
    """Fetches details of a specific Instagram post by ID."""
    try:
        access_token, ig_user_id = await get_access_token(platform_user_id)

        url = f"https://graph.instagram.com/{post_id}"
        params = {
            "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
            "access_token": access_token
        }

        async with httpx.AsyncClient() as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            
            data = res.json()
            # Add helpful info about media type
            media_product_type = data.get('media_product_type', 'UNKNOWN')
            if media_product_type == 'REELS':
                logger.info(f"Fetched media {post_id} is a REEL")
            elif media_product_type == 'FEED':
                logger.info(f"Fetched media {post_id} is a FEED post")
            else:
                logger.info(f"Fetched media {post_id} with product_type: {media_product_type}")
            
            return APIResponse.success(data=data, message="Fetched post successfully")    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error fetching post {post_id}: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to fetch post: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in get_post_by_id: {e}")
        return APIResponse.error(500, "An internal server error occurred")


@router.get("/reels")
async def get_reels(
    platform_user_id: str = Query(...),
    limit: int = Query(25, ge=1, le=100, description="Number of reels to fetch")
):
    """
    Fetches only Instagram REELS for the given platform_user_id.
    This endpoint filters and returns only content that is identified as reels using:
    1. media_product_type field
    2. Permalink URL pattern (/reel/)
    
    If needed, it will fetch additional pages to ensure you get the requested number of reels.
    """
    try:
        access_token, ig_user_id = await get_access_token(platform_user_id)

        url = f"https://graph.instagram.com/{ig_user_id}/media"
        
        all_reels = []
        fetched_count = 0
        max_fetch = 100  # Safety limit to prevent infinite loops
        next_url = None
        
        async with httpx.AsyncClient() as client:
            # Keep fetching until we have enough reels or reach max
            while len(all_reels) < limit and fetched_count < max_fetch:
                # Fetch more items than requested to account for filtering
                fetch_limit = min(50, max_fetch - fetched_count)
                
                if next_url:
                    # Use pagination URL
                    fetch_url = next_url
                    logger.info(f"Fetching next page of media (already have {len(all_reels)} reels)")
                else:
                    # Initial fetch
                    params = {
                        "fields": "id,caption,media_type,media_product_type,media_url,thumbnail_url,timestamp,permalink,like_count,comments_count",
                        "access_token": access_token,
                        "limit": fetch_limit
                    }
                    fetch_url = url
                
                res = await client.get(fetch_url, params=params if not next_url else None)
                res.raise_for_status()
                
                data = res.json()
                items = data.get('data', [])
                fetched_count += len(items)
                
                logger.info(f"Fetched {len(items)} media items for reels. Total fetched: {fetched_count}")
                
                # Filter to keep only reels
                for item in items:
                    is_reel = _is_reel(item)
                    
                    if is_reel:
                        all_reels.append(item)
                        logger.debug(f"Keeping REEL: {item.get('id')}, permalink: {item.get('permalink')}")
                    else:
                        logger.debug(f"Filtering out POST: {item.get('id')}")
                    
                    # Stop if we have enough reels
                    if len(all_reels) >= limit:
                        break
                
                # Check if there's a next page
                paging = data.get('paging', {})
                next_url = paging.get('next')
                
                # Break if no more pages or we have enough reels
                if not next_url or len(all_reels) >= limit:
                    break
            
            # Trim to requested limit
            all_reels = all_reels[:limit]
            
            logger.info(f"Final result: Returning {len(all_reels)} reels after filtering. Total fetched: {fetched_count}")
            
            result_data = {
                'data': all_reels,
                'paging': {} if not next_url else {'next': next_url}
            }
            
            return APIResponse.success(data=result_data, message=f"Fetched {len(all_reels)} reels successfully")    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on fetching reels: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to fetch reels: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in get_reels: {e}")
        return APIResponse.error(500, "An internal server error occurred")


# curl -X POST "https://<HOST_URL>/v23.0/<IG_COMMENT_ID>/replies"
#    -H "Content-Type: application/json" 
#    -d '{
#          "message":"Thanks for sharing!"
#        }'
@router.post("/reply-to-comment")
async def reply_to_comment(comment_id: str = Query(...), message: str = Query(...), platform_user_id: str = Query(...)):
    """
    Replies to an Instagram comment using the Instagram Graph API.
    """
    try:
        # Get access token based on the comment_id (you may need to adjust this logic)
        access_token, puid = await get_access_token(platform_user_id)
        url = f"https://graph.instagram.com/v23.0/{comment_id}/replies"
        payload = {
            "message": message,
            "access_token": access_token
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            return APIResponse.success(data=res.json(), message="Reply sent successfully")
    
    except httpx.HTTPStatusError as e:
        logger.error(f"Instagram API error on reply: {e.response.text}")
        return APIResponse.error(e.response.status_code, f"Failed to send reply: {e.response.text}")
    
    except Exception as e:
        logger.error(f"Unexpected error in reply_to_comment: {e}")
        return APIResponse.error(500, "An internal server error occurred")