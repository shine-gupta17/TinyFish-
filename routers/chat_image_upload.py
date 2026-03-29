"""
Simple Chat Image Upload Router
Uploads image files to Supabase storage and returns the URL.
Images can be used for social media posts (LinkedIn, Instagram, etc.)
"""

import uuid
import logging
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import JSONResponse
from config import (
    CHAT_BUCKET_NAME, 
    SUPABASE_URL,
    S3_ACCESS_KEY_ID,
    S3_SECRET_ACCESS_KEY,
    S3_ENDPOINT_URL,
    S3_REGION
)
from utils.api_responses import APIResponse
from supabase_client import supabase

router = APIRouter(
    prefix="/chat/image",
    tags=["Chat Image Upload"]
)

logger = logging.getLogger(__name__)

# Supported image formats
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp"
}


@router.post("/upload")
async def upload_chat_image(
    file: UploadFile = File(...),
    provider_id: str = Form(...),
    thread_id: str = Form(...)  # Required thread_id
) -> JSONResponse:
    """
    Upload an image file to Supabase storage for chat usage.
    Returns the file URL which can be used in LinkedIn posts, Instagram, etc.
    
    Supported formats: JPEG, PNG, GIF, WebP
    Max size: 10MB
    
    Also logs the upload metadata to media_storage table for tracking.
    """
    logger.info(f"Image upload request - provider_id: {provider_id}, thread_id: {thread_id}, filename: {file.filename}")
    
    # Validate file type
    if not file.content_type or file.content_type not in ALLOWED_IMAGE_TYPES:
        return APIResponse.error(
            400, 
            f"Invalid file type. Supported formats: {', '.join(ALLOWED_IMAGE_TYPES.keys())}"
        )

    # Read file content
    contents = await file.read()
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(contents) > max_size:
        return APIResponse.error(400, "File too large. Maximum size is 10MB.")
    
    # Get file extension from content type
    file_extension = ALLOWED_IMAGE_TYPES.get(file.content_type, ".jpg")
    
    # Generate unique filename with provider prefix for organization
    filename = f"chat/images/{provider_id}/{uuid.uuid4()}{file_extension}"

    try:
        # Upload file to S3-compatible storage (Supabase)
        s3_client = boto3.client(
            's3',
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            endpoint_url=S3_ENDPOINT_URL,
            region_name=S3_REGION
        )
        
        s3_client.put_object(
            Bucket=CHAT_BUCKET_NAME,
            Key=filename,
            Body=contents,
            ContentType=file.content_type
        )
        
        # Construct the public URL
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{CHAT_BUCKET_NAME}/{filename}"
        
        # Log media metadata to media_storage table
        try:
            media_record = {
                "provider_id": provider_id,
                "thread_id": thread_id,
                "type": "image",
                "file_path": file_url,
                "file_name": file.filename or f"image{file_extension}",
                "file_type": file.content_type,
                "file_size": len(contents),
                "storage_bucket": CHAT_BUCKET_NAME,
                "metadata": {
                    "original_filename": file.filename,
                    "upload_path": filename,
                    "content_type": file.content_type
                }
            }
            
            supabase.table("media_storage").insert(media_record).execute()
            logger.info(f"Media metadata logged for: {file_url}")
        except Exception as db_error:
            # Log error but don't fail the upload
            logger.error(f"Failed to log media metadata: {db_error}", exc_info=True)
        
        logger.info(f"Chat image uploaded successfully: {file_url}")

        return APIResponse.success(
            data={
                "file_url": file_url,
                "filename": file.filename or f"image{file_extension}",
                "size": len(contents),
                "content_type": file.content_type
            },
            message="Image uploaded successfully"
        )
            
    except ClientError as e:
        logger.error(f"S3 upload error for provider {provider_id}: {e}")
        return APIResponse.error(500, f"Failed to upload file to storage: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading chat image for provider {provider_id}: {e}", exc_info=True)
        return APIResponse.error(500, f"File upload failed: {str(e)}")
