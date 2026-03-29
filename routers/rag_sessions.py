"""
RAG Sessions Router
Endpoints for managing RAG vector chunk sessions
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from supabase_client_async import async_supabase
from utils.api_responses import APIResponse

router = APIRouter(
    prefix="/rag-sessions",
    tags=["RAG Sessions"]
)

logger = logging.getLogger(__name__)


@router.get("/{provider_id}")
async def get_rag_sessions(provider_id: str) -> JSONResponse:
    """
    Get all unique RAG sessions for a provider with metadata.
    Returns session_id, document count, total chunks, created_at, and document names.
    """
    try:
        db = await async_supabase.get_instance()
        
        # Direct query to get all chunks for this provider
        response = await db.select(
            "rag_vector_chunks",
            select="session_id, provider_id, doc_hash, doc_name, doc_url, created_at",
            filters={"provider_id": provider_id}
        )
        
        if response.get("error"):
            logger.error(f"Error querying RAG chunks: {response['error']}")
            raise HTTPException(status_code=500, detail=str(response["error"]))
        
        data = response.get("data", [])
        
        # Group by session_id
        sessions_dict = {}
        for row in data:
            session_id = row['session_id']
            if session_id not in sessions_dict:
                sessions_dict[session_id] = {
                    'session_id': session_id,
                    'provider_id': row['provider_id'],
                    'document_count': 0,
                    'total_chunks': 0,
                    'created_at': row['created_at'],
                    'last_updated': row['created_at'],
                    'document_names': set(),
                    'document_urls': set(),
                    'doc_hashes': set()
                }
            
            session = sessions_dict[session_id]
            session['total_chunks'] += 1
            session['doc_hashes'].add(row['doc_hash'])
            if row['doc_name']:
                session['document_names'].add(row['doc_name'])
            if row['doc_url']:
                session['document_urls'].add(row['doc_url'])
            
            # Update timestamps
            if row['created_at'] < session['created_at']:
                session['created_at'] = row['created_at']
            if row['created_at'] > session['last_updated']:
                session['last_updated'] = row['created_at']
        
        # Convert sets to lists and calculate document_count
        sessions_list = []
        for session in sessions_dict.values():
            session['document_count'] = len(session['doc_hashes'])
            session['document_names'] = list(session['document_names'])
            session['document_urls'] = list(session['document_urls'])
            del session['doc_hashes']  # Remove internal tracking field
            sessions_list.append(session)
        
        # Sort by created_at descending
        sessions_list.sort(key=lambda x: x['created_at'], reverse=True)
        
        return APIResponse.success(
            data=sessions_list,
            message=f"Found {len(sessions_list)} RAG sessions"
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions so they return the correct status code
        raise
    except Exception as e:
        logger.error(f"Error fetching RAG sessions for {provider_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{provider_id}/{session_id}")
async def delete_rag_session(provider_id: str, session_id: str) -> JSONResponse:
    """
    Delete all chunks for a specific RAG session.
    """
    try:
        db = await async_supabase.get_instance()
        
        # First check if session exists and belongs to user
        check_response = await db.select(
            "rag_vector_chunks",
            select="id",
            filters={"provider_id": provider_id, "session_id": session_id},
            limit=1
        )
        
        if check_response.get("error"):
            logger.error(f"Error checking session existence: {check_response['error']}")
            raise HTTPException(status_code=500, detail=str(check_response["error"]))
        
        if not check_response.get("data"):
            logger.warning(
                f"Session {session_id} not found for user {provider_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Session {session_id} not found for user {provider_id}",
                    "error_type": "NOT_FOUND"
                }
            )
        
        # Delete all chunks for this session
        delete_response = await db.delete(
            "rag_vector_chunks",
            filters={"provider_id": provider_id, "session_id": session_id}
        )
        
        if delete_response.get("error"):
            logger.error(f"Error deleting chunks: {delete_response['error']}")
            raise HTTPException(status_code=500, detail=str(delete_response["error"]))
        
        deleted_count = len(delete_response.get("data", [])) if delete_response.get("data") else 0
        
        logger.info(
            f"Deleted {deleted_count} chunks for session {session_id} "
            f"(provider: {provider_id})"
        )
        
        return APIResponse.success(
            data={
                "session_id": session_id,
                "provider_id": provider_id,
                "chunks_deleted": deleted_count
            },
            message=f"Successfully deleted session {session_id} ({deleted_count} chunks)"
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions (404, etc.) so they return the correct status code
        raise
    except Exception as e:
        logger.error(
            f"Error deleting RAG session {session_id} for {provider_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/{session_id}/details")
async def get_session_details(provider_id: str, session_id: str) -> JSONResponse:
    """
    Get detailed information about a specific RAG session.
    """
    try:
        db = await async_supabase.get_instance()
        
        # Get all chunks for this session (without embeddings to save bandwidth)
        response = await db.select(
            "rag_vector_chunks",
            select="id, doc_hash, doc_name, doc_url, chunk_index, chunk_size, "
                   "page_number, metadata, created_at",
            filters={"provider_id": provider_id, "session_id": session_id}
        )
        
        if response.get("error"):
            logger.error(f"Error querying session details: {response['error']}")
            raise HTTPException(status_code=500, detail=str(response["error"]))
        
        data = response.get("data", [])
        
        if not data:
            logger.warning(
                f"Session {session_id} not found for user {provider_id}"
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": f"Session {session_id} not found for user {provider_id}",
                    "error_type": "NOT_FOUND"
                }
            )
        
        # Sort by doc_hash and chunk_index
        data.sort(key=lambda x: (x.get('doc_hash', ''), x.get('chunk_index', 0)))
        
        # Group chunks by document
        documents = {}
        for chunk in data:
            doc_hash = chunk['doc_hash']
            if doc_hash not in documents:
                documents[doc_hash] = {
                    'doc_hash': doc_hash,
                    'doc_name': chunk['doc_name'],
                    'doc_url': chunk['doc_url'],
                    'chunk_count': 0,
                    'chunks': []
                }
            documents[doc_hash]['chunk_count'] += 1
            documents[doc_hash]['chunks'].append({
                'id': chunk['id'],
                'chunk_index': chunk['chunk_index'],
                'chunk_size': chunk['chunk_size'],
                'page_number': chunk['page_number'],
                'metadata': chunk['metadata'],
                'created_at': chunk['created_at']
            })
        
        session_info = {
            'session_id': session_id,
            'provider_id': provider_id,
            'document_count': len(documents),
            'total_chunks': len(data),
            'documents': list(documents.values())
        }
        
        return APIResponse.success(
            data=session_info,
            message=f"Session details retrieved successfully"
        )
        
    except HTTPException:
        # Re-raise HTTPExceptions (404, etc.) so they return the correct status code
        raise
    except Exception as e:
        logger.error(
            f"Error fetching session details for {session_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
