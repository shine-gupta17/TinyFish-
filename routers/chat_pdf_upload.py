"""
Simple Chat PDF Upload Router
Uploads PDF files to Supabase storage and returns the URL.
No Pinecone indexing - the RAG agent handles session-based vector storage.
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
    prefix="/chat/pdf",
    tags=["Chat PDF Upload"]
)

logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_chat_pdf(
    file: UploadFile = File(...),
    provider_id: str = Form(...),
    thread_id: str = Form(...)  # Required thread_id
) -> JSONResponse:
    """
    Upload a PDF file to Supabase storage for chat RAG.
    Returns the file URL which can be passed to the chat agent.
    
    This endpoint does NOT index the content - the RAG agent will
    handle document processing with session-based vector storage.
    
    Also logs the upload metadata to media_storage table for tracking.
    """
    logger.info(f"PDF upload request - provider_id: {provider_id}, thread_id: {thread_id}, filename: {file.filename}")
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return APIResponse.error(400, "Invalid file type. Only PDF files are allowed.")

    # Read file content
    contents = await file.read()
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(contents) > max_size:
        return APIResponse.error(400, "File too large. Maximum size is 10MB.")
    
    # Generate unique filename with provider prefix for organization
    filename = f"chat/{provider_id}/{uuid.uuid4()}.pdf"

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
            ContentType='application/pdf'
        )
        
        # Construct the public URL
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{CHAT_BUCKET_NAME}/{filename}"
        
        # Log media metadata to media_storage table
        try:
            media_record = {
                "provider_id": provider_id,
                "thread_id": thread_id,
                "type": "pdf",
                "file_path": file_url,
                "file_name": file.filename,
                "file_type": "application/pdf",
                "file_size": len(contents),
                "storage_bucket": CHAT_BUCKET_NAME,
                "metadata": {
                    "original_filename": file.filename,
                    "upload_path": filename
                }
            }
            
            supabase.table("media_storage").insert(media_record).execute()
            logger.info(f"Media metadata logged for: {file_url}")
        except Exception as db_error:
            # Log error but don't fail the upload
            logger.error(f"Failed to log media metadata: {db_error}", exc_info=True)
        
        logger.info(f"Chat PDF uploaded successfully: {file_url}")

        return APIResponse.success(
            data={
                "file_url": file_url,
                "filename": file.filename,
                "size": len(contents)
            },
            message="PDF uploaded successfully"
        )
            
    except ClientError as e:
        logger.error(f"S3 upload error for provider {provider_id}: {e}")
        return APIResponse.error(500, f"Failed to upload file to storage: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading chat PDF for provider {provider_id}: {e}", exc_info=True)
        return APIResponse.error(500, f"File upload failed: {str(e)}")
