import httpx
import uuid
import bs4
import logging
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, File, UploadFile, Form
from fastapi.responses import JSONResponse
from supabase_client import supabase
from agentic.agentic_utils import extract_text_from_pdf
from agentic.pinecone_utils import upload_data_to_index
from config import (
    PINECONE_CHAT_INDEX, 
    CHAT_BUCKET_NAME, 
    SUPABASE_URL,
    S3_ACCESS_KEY_ID,
    S3_SECRET_ACCESS_KEY,
    S3_ENDPOINT_URL,
    S3_REGION
)
from models.api_models import WebUrlPayload, CustomTextPayload # Assuming these are updated or compatible
from models.ai_conversation_model import RagSourceType, ProcessingStatus, PlatformEnum # Import your Pydantic models
from utils.api_responses import APIResponse

router = APIRouter(
    prefix="/rag/sources",
    tags=["RAG Data Sources"]
)

logger = logging.getLogger(__name__)

@router.get("/{platform_user_id}")
def get_rag_sources(platform_user_id: str) -> JSONResponse:
    """
    Fetches all RAG data sources for a given platform user ID.
    """
    try:
        # Query the new 'rag_data_sources' table
        response = supabase.table("rag_data_sources").select("*").eq("platform_user_id", platform_user_id).execute()
        return APIResponse.success(
            data=response.data,
            message="RAG data sources fetched successfully"
        )
    except Exception as e:
        logger.error(f"Error getting RAG sources for {platform_user_id}: {e}")
        return APIResponse.error(500, str(e))

@router.post("/web-url")
async def add_web_url_source(payload: WebUrlPayload) -> JSONResponse:
    """
    Adds or updates a RAG data source from a web URL.
    """
    try:
        # Fetch and parse the web page content, following redirects
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(str(payload.website_url))
            response.raise_for_status()

        soup = bs4.BeautifulSoup(response.content, 'html.parser')
        scraped_text = soup.get_text(separator=' ', strip=True)

        # Delete existing source if it's a different type
        platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
        _delete_existing_source_if_different_type(payload.platform_user_id, platform_str, RagSourceType.WEBSITE.value)

        # Get or create AI conversation automation for this user
        automation_response = supabase.table("automations").select("automation_id").eq(
            "platform_user_id", payload.platform_user_id
        ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()
        
        automation_id = None
        if automation_response and automation_response.data:
            automation_id = automation_response.data['automation_id']
        else:
            # Create a new automation for RAG data sources
            new_automation = {
                "platform": payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform,
                "platform_user_id": payload.platform_user_id,
                "name": f"RAG Knowledge Base - {payload.platform_user_id}",
                "description": "Automation for RAG data sources",
                "automation_type": "AI_DM_CONVERSATION",
                "activation_status": "ACTIVE",
                "schedule_type": "CONTINUOUS",
                "model_usage": "PLATFORM_DEFAULT"
            }
            auto_result = supabase.table("automations").insert(new_automation).execute()
            if auto_result.data:
                automation_id = auto_result.data[0]['automation_id']

        # Create a dictionary matching the RagDataSource model
        source_data = {
            "automation_id": automation_id,
            "platform": payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform,
            "platform_user_id": payload.platform_user_id,
            "rag_source_type": RagSourceType.WEBSITE.value,
            "input_source": str(payload.website_url),
            "content": scraped_text,
            "processing_status": ProcessingStatus.PENDING.value,
        }

        # Use upsert to insert or update the record based on a unique constraint
        # Assumes a UNIQUE constraint exists on (platform, platform_user_id)
        upsert_response = supabase.table("rag_data_sources").upsert(source_data, on_conflict="platform,platform_user_id").execute()
        
        # Upload the extracted text to the vector index
        platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
        # Use platform_user_id as provider_id if provider_id is None
        provider_id_value = payload.provider_id if payload.provider_id else payload.platform_user_id
        upload_successful = upload_data_to_index(
            index=PINECONE_CHAT_INDEX, text=scraped_text, type="web_url",
            platform_user_id=payload.platform_user_id, provider_id=provider_id_value,
            platform=platform_str
        )

        if upload_successful:
            # Update the status to COMPLETED after successful indexing
            platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
            supabase.table("rag_data_sources").update(
                {"processing_status": ProcessingStatus.COMPLETED.value}
            ).eq("platform_user_id", payload.platform_user_id).eq("platform", platform_str).execute()
            
            return APIResponse.success(
                data=upsert_response.data,
                message="Web URL source processed and indexed successfully."
            )
        else:
            return APIResponse.error(500, "Failed to index the web content.")

    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch webpage {payload.website_url}: {e}")
        return APIResponse.error(400, "Failed to fetch the webpage.")
    except Exception as e:
        logger.error(f"Error processing web URL {payload.website_url}: {e}")
        return APIResponse.error(500, str(e))

@router.post("/custom-text")
async def add_custom_text_source(payload: CustomTextPayload) -> JSONResponse:
    """
    Adds or updates a RAG data source from custom text.
    Limited to 2000 characters.
    """
    # try:
    # Validate text is not None or empty
    logger.info(f"Received custom text payload for platform_user_id: {payload.platform_user_id}")
    if not payload.text or payload.text is None:
        return APIResponse.error(400, "Text cannot be empty or None")
    
    logger.debug(f"Received custom text: {payload.text}")
    text_content = str(payload.text).strip()
    if not text_content:
        return APIResponse.error(400, "Text cannot be empty after trimming whitespace")
    
    logger.debug(f"Trimmed custom text: {text_content}")
    # Validate text length
    if len(text_content) > 2000:
        return APIResponse.error(400, "Custom text cannot exceed 2000 characters")

    logger.debug(f"Validated custom text length: {len(text_content)}")

    # Delete existing source if it's a different type
    platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
    _delete_existing_source_if_different_type(payload.platform_user_id, platform_str, RagSourceType.TEXT.value)

    logger.info(f"Deleted existing source if different type for platform_user_id: {payload.platform_user_id}, platform: {platform_str}")

    # Get or create AI conversation automation for this user
    automation_response = supabase.table("automations").select("automation_id").eq(
        "platform_user_id", payload.platform_user_id
    ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()

    logger.debug(f"Automation response: {automation_response}")
    
    automation_id = None
    if automation_response and automation_response.data:
        automation_id = automation_response.data['automation_id']
    else:
        logger.info(f"No existing automation found for platform_user_id: {payload.platform_user_id}. Creating a new one.")
        # Create a new automation for RAG data sources
        new_automation = {
            "platform": payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform,
            "platform_user_id": payload.platform_user_id,
            "name": f"RAG Knowledge Base - {payload.platform_user_id}",
            "description": "Automation for RAG data sources",
            "automation_type": "AI_DM_CONVERSATION",
            "activation_status": "ACTIVE",
            "schedule_type": "CONTINUOUS",
            "model_usage": "PLATFORM_DEFAULT"
        }
        auto_result = supabase.table("automations").insert(new_automation).execute()
        if auto_result.data:
            automation_id = auto_result.data[0]['automation_id']

    logger.info(f"Using automation_id: {automation_id}")

    source_data = {
        "automation_id": automation_id,
        "platform": payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform,
        "platform_user_id": payload.platform_user_id,
        "rag_source_type": RagSourceType.TEXT.value,
        "input_source": "Custom Text",
        "content": text_content,  # Use validated text_content
        "processing_status": ProcessingStatus.PENDING.value,
    }

    upsert_response = supabase.table("rag_data_sources").upsert(source_data, on_conflict="platform,platform_user_id").execute()
    
    platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
    # Use platform_user_id as provider_id if provider_id is None
    provider_id_value = payload.provider_id if payload.provider_id else payload.platform_user_id
    logger.info(f"Using provider_id: {provider_id_value} for platform_user_id: {payload.platform_user_id}")
    upload_successful = upload_data_to_index(
        index=PINECONE_CHAT_INDEX, text=text_content,  # Use validated text_content
        type="custom_text",
        platform_user_id=payload.platform_user_id, provider_id=provider_id_value,
        platform=platform_str
    )
    
    if upload_successful:
        platform_str = payload.platform.value if isinstance(payload.platform, PlatformEnum) else payload.platform
        supabase.table("rag_data_sources").update(
            {"processing_status": ProcessingStatus.COMPLETED.value}
        ).eq("platform_user_id", payload.platform_user_id).eq("platform", platform_str).execute()

        logger.info(f"Updated processing status to COMPLETED for platform_user_id: {payload.platform_user_id}, platform: {platform_str}")

        return APIResponse.success(
            data=upsert_response.data,
            message="Custom text source processed and indexed successfully."
        )
        # else:
        #     return APIResponse.error(500, "Failed to index the custom text.")

    # except Exception as e:
    #     logger.error(f"Error adding custom text for {payload.platform_user_id}: {e}")
    #     return APIResponse.error(500, str(e))

@router.post("/file-upload")
async def add_file_source(
    file: UploadFile = File(...),
    provider_id: str = Form(...),
    platform_user_id: str = Form(...),
    platform: PlatformEnum = Form(...)
) -> JSONResponse:
    """
    Adds or updates a RAG data source from a file upload (PDF).
    Uses S3-compatible storage (Supabase) for file uploads.
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        return APIResponse.error(400, "Invalid file type. Only PDF files are allowed.")

    contents = await file.read()
    filename = f"{uuid.uuid4()}.pdf"

    try:
        # Extract text from PDF content BEFORE uploading to S3
        # This avoids issues with immediate URL availability
        import fitz  # PyMuPDF
        from io import BytesIO
        
        pdf_stream = BytesIO(contents)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        extracted_text = ""
        for page in doc:
            extracted_text += page.get_text()
        
        doc.close()
        
        if not extracted_text.strip():
            return APIResponse.error(400, "Could not extract text from PDF. The file may be empty or contains only images.")
        
        logger.info(f"Extracted {len(extracted_text)} characters from PDF")
        
        # Delete existing source if it's a different type (this also deletes old PDF if same type)
        platform_str = platform.value if isinstance(platform, PlatformEnum) else platform
        _delete_existing_source_if_different_type(platform_user_id, platform_str, RagSourceType.FILE.value)
        
        # Check if there's an existing file source and delete old PDF from S3 (for same type replacement)
        existing_source = supabase.table("rag_data_sources").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", platform_str).maybe_single().execute()
        
        if existing_source and existing_source.data:
            source = existing_source.data
            if source.get("rag_source_type") == RagSourceType.FILE.value:
                old_file_url = source.get("input_source")
                if old_file_url:
                    _delete_file_from_s3(old_file_url)
                    logger.info(f"Deleted old PDF before uploading new one")
        
        # Now upload file to S3-compatible storage
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
        
        logger.info(f"File uploaded successfully to: {file_url}")

        # Get or create AI conversation automation for this user
        # Check if AI_DM_CONVERSATION automation exists
        automation_response = supabase.table("automations").select("automation_id").eq(
            "platform_user_id", platform_user_id
        ).eq("automation_type", "AI_DM_CONVERSATION").maybe_single().execute()
        
        automation_id = None
        if automation_response and automation_response.data:
            automation_id = automation_response.data['automation_id']
            logger.info(f"Found existing automation: {automation_id}")
        else:
            # Create a new automation for RAG data sources
            logger.info("Creating new automation for RAG data sources")
            platform_str = platform.value if isinstance(platform, PlatformEnum) else platform
            new_automation = {
                "platform": platform_str,
                "platform_user_id": platform_user_id,
                "name": f"RAG Knowledge Base - {platform_user_id}",
                "description": "Automation for RAG data sources",
                "automation_type": "AI_DM_CONVERSATION",
                "activation_status": "ACTIVE",
                "schedule_type": "CONTINUOUS",
                "model_usage": "PLATFORM_DEFAULT"
            }
            auto_result = supabase.table("automations").insert(new_automation).execute()
            if auto_result.data:
                automation_id = auto_result.data[0]['automation_id']
                logger.info(f"Created new automation: {automation_id}")

        platform_str = platform.value if isinstance(platform, PlatformEnum) else platform
        source_data = {
            "automation_id": automation_id,
            "platform": platform_str,
            "platform_user_id": platform_user_id,
            "rag_source_type": RagSourceType.FILE.value,
            "input_source": file_url,
            "content": extracted_text,
            "processing_status": ProcessingStatus.PENDING.value,
        }
        
        upsert_response = supabase.table("rag_data_sources").upsert(
            source_data, 
            on_conflict="platform,platform_user_id"
        ).execute()

        # Upload extracted text to Pinecone vector database
        platform_str = platform.value if isinstance(platform, PlatformEnum) else platform
        upload_successful = upload_data_to_index(
            index=PINECONE_CHAT_INDEX, 
            text=extracted_text, 
            type="file",
            platform_user_id=platform_user_id, 
            provider_id=provider_id, 
            platform=platform_str
        )

        if upload_successful:
            platform_str = platform.value if isinstance(platform, PlatformEnum) else platform
            supabase.table("rag_data_sources").update(
                {"processing_status": ProcessingStatus.COMPLETED.value}
            ).eq("platform_user_id", platform_user_id).eq("platform", platform_str).execute()

            return APIResponse.success(
                data=upsert_response.data,
                message="File source processed and indexed successfully."
            )
        else:
            return APIResponse.error(500, "Failed to index the file content.")
            
    except ClientError as e:
        logger.error(f"S3 upload error for {platform_user_id}: {e}")
        return APIResponse.error(500, f"Failed to upload file to storage: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing file upload for {platform_user_id}: {e}", exc_info=True)
        return APIResponse.error(500, f"File upload failed: {str(e)}")


def _delete_file_from_s3(file_url: str) -> bool:
    """
    Helper function to delete a file from S3 bucket given its public URL.
    Extracts the key from the URL and deletes the file.
    """
    try:
        # Extract filename from URL
        # URL format: {SUPABASE_URL}/storage/v1/object/public/{CHAT_BUCKET_NAME}/{filename}
        if CHAT_BUCKET_NAME in file_url:
            parts = file_url.split(f"{CHAT_BUCKET_NAME}/")
            if len(parts) > 1:
                filename = parts[1]
                
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=S3_ACCESS_KEY_ID,
                    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                    endpoint_url=S3_ENDPOINT_URL,
                    region_name=S3_REGION
                )
                
                s3_client.delete_object(Bucket=CHAT_BUCKET_NAME, Key=filename)
                logger.info(f"Deleted file from S3: {filename}")
                return True
    except Exception as e:
        logger.error(f"Error deleting file from S3: {e}", exc_info=True)
    return False


def _delete_existing_source_if_different_type(platform_user_id: str, platform: str, new_source_type: str) -> None:
    """
    Helper function to delete existing source if it's a different type than what's being uploaded.
    This ensures only one source type exists at a time per user.
    """
    try:
        # Get existing source
        existing_source = supabase.table("rag_data_sources").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", platform).maybe_single().execute()
        
        if existing_source and existing_source.data:
            source = existing_source.data
            existing_type = source.get("rag_source_type")
            
            # If source type is different, delete the old one
            if existing_type != new_source_type:
                logger.info(f"Deleting existing source of type {existing_type} before adding {new_source_type}")
                
                # If old source is a file, delete from S3
                if existing_type == RagSourceType.FILE.value:
                    file_url = source.get("input_source")
                    if file_url:
                        _delete_file_from_s3(file_url)
                
                # Delete from database
                supabase.table("rag_data_sources").delete().eq(
                    "platform_user_id", platform_user_id
                ).eq("platform", platform).execute()
                
                # Delete from Pinecone
                from agentic.pinecone_utils import pc
                try:
                    pc_index = pc.Index(PINECONE_CHAT_INDEX)
                    pc_index.delete(
                        filter={
                            "platform": {"$eq": platform},
                            "platform_user_id": {"$eq": platform_user_id}
                        },
                        namespace=platform_user_id
                    )
                    logger.info(f"Deleted vectors from Pinecone for platform_user_id: {platform_user_id}")
                except Exception as e:
                    logger.warning(f"Error deleting from Pinecone: {e}")
                    
    except Exception as e:
        logger.error(f"Error in _delete_existing_source_if_different_type: {e}", exc_info=True)


@router.delete("/{platform_user_id}")
def delete_rag_source(platform_user_id: str, platform: str) -> JSONResponse:
    """
    Deletes a RAG data source for a given platform user ID.
    Also deletes the associated PDF file from S3 if it's a file source.
    """
    try:
        # Get the existing source to check if it has a file to delete
        existing_source = supabase.table("rag_data_sources").select("*").eq(
            "platform_user_id", platform_user_id
        ).eq("platform", platform).maybe_single().execute()
        
        if existing_source and existing_source.data:
            source = existing_source.data
            
            # If it's a file source, delete from S3
            if source.get("rag_source_type") == RagSourceType.FILE.value:
                file_url = source.get("input_source")
                if file_url:
                    _delete_file_from_s3(file_url)
            
            # Delete from database
            supabase.table("rag_data_sources").delete().eq(
                "platform_user_id", platform_user_id
            ).eq("platform", platform).execute()
            
            # Delete from Pinecone (get provider_id from source or use platform_user_id)
            provider_id = source.get("platform_user_id")  # Adjust if you have provider_id field
            from agentic.pinecone_utils import pc
            try:
                pc_index = pc.Index(PINECONE_CHAT_INDEX)
                pc_index.delete(
                    filter={
                        "platform": {"$eq": platform},
                        "provider_id": {"$eq": provider_id}
                    },
                    namespace=platform_user_id
                )
                logger.info(f"Deleted vectors from Pinecone for platform_user_id: {platform_user_id}")
            except Exception as e:
                logger.warning(f"Error deleting from Pinecone: {e}")
            
            return APIResponse.success(
                data={"deleted": True},
                message="RAG data source deleted successfully"
            )
        else:
            return APIResponse.error(404, "RAG data source not found")
            
    except Exception as e:
        logger.error(f"Error deleting RAG source for {platform_user_id}: {e}", exc_info=True)
        return APIResponse.error(500, str(e))

