import logging
import os
from typing import List, Dict, Optional, Any
from enum import Enum
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pinecone import Pinecone
from agentic.agentic_utils import AIResponser
import asyncio

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ai_responser = AIResponser()

# Initialize Pinecone and OpenAI clients (async)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INDEX_NAME = "chatrag"
EMBEDDING_DIMENSION = 512
EMBEDDING_MODEL = "text-embedding-3-small"

class AIPersonality(Enum):
    PROFESSIONAL = "a professional assistant"
    FRIENDLY = "a friendly and approachable assistant"
    FORMAL = "a formal assistant"
    CASUAL = "a casual, relaxed assistant"
    EXPERT = "an expert assistant in the relevant field"

class AIResponseStyle(Enum):
    DIRECT = "be direct and to the point"
    CONVERSATIONAL = "be conversational and engaging"
    HUMOROUS = "be light-hearted and occasionally humorous"
    EMPATHETIC = "be understanding and empathetic"

class AIAssistant:
    def __init__(
        self,
        personality: AIPersonality = AIPersonality.FRIENDLY,
        response_style: AIResponseStyle = AIResponseStyle.CONVERSATIONAL,
        use_rag: bool = True
    ):
        self.personality = personality
        self.response_style = response_style
        self.use_rag = use_rag
        self.conversation_history: List[Dict[str, str]] = []

    async def _get_embedding(self, text: str) -> List[float]:
        try:
            response = await client.embeddings.create(
                input=text, model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSION
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    async def _search_vector_db(self, query: str, platform_id: str, provider_id: str) -> Optional[List[Dict]]:
        try:
            # Check if index exists (newer Pinecone API)
            index_list = pc.list_indexes()
            index_names = [idx.name for idx in index_list]
            
            if INDEX_NAME not in index_names:
                logger.warning(f"Pinecone index '{INDEX_NAME}' not found. Available indexes: {index_names}")
                return None
            
            index = pc.Index(INDEX_NAME)
            query_embedding = await self._get_embedding(query)
            if not query_embedding:
                return None
            
            # Pinecone query is synchronous but fast, no async version available
            results = await asyncio.to_thread(
                index.query,
                vector=query_embedding,
                top_k=3,
                namespace=platform_id,
                include_metadata=True,
                filter={"platform_user_id": {"$eq": platform_id}}
            )
            return results.get("matches", [])
        except Exception as e:
            logger.error(f"Error during vector search: {e}", exc_info=True)
            return None


    async def process_query(
        self,
        query: str,
        platform: str,
        platform_id: str,
        system_prompt: Optional[str] = None,
        use_rag_override: Optional[bool] = None,
        model_name: Optional[str] = 'gpt-4o-mini',
        model_provider: Optional[str] = 'OPENAI'
    ) -> Dict[str, Any]:
        """
        Process a query using OpenAI GPT-4o-mini (forced default) asynchronously.
        Returns dict with answer and tokens_used.
        """
        use_rag = use_rag_override if use_rag_override is not None else self.use_rag
        context = ""
        sources = []

        # Force OpenAI GPT-4o-mini regardless of parameters
        model_provider = 'OPENAI'
        model_name = 'gpt-4o-mini'

        logger.info(f"Processing query: {query}, platform_id: {platform_id}, rag: {use_rag}, model: {model_name}")
        
        if use_rag:
            search_results = await self._search_vector_db(query, platform_id, platform_id)
            if search_results:
                context = "\n".join([match.metadata.get("text", "") for match in search_results])
                sources = [match.metadata.get("document_id", "unknown") for match in search_results]
                logger.info(f"RAG enabled: Found {len(search_results)} relevant chunks from Pinecone")
            else:
                # RAG is enabled but no context found - return error message instead of answering
                logger.warning(f"RAG enabled but no relevant data found in Pinecone for platform_id: {platform_id}")
                return {
                    "query": query,
                    "answer": "I don't have enough information in my knowledge base to answer this question. Please upload relevant documents or data first.",
                    "tokens_used": 0,
                    "context_used": False,
                    "sources": [],
                    "rag_required": True,
                    "rag_data_missing": True
                }

        base_prompt = system_prompt or f"You are {self.personality.value}. Your goal is to {self.response_style.value}."
        
        if use_rag and context:
            # RAG is enabled and context is available - must use it
            prompt = f"{base_prompt}\n\nIMPORTANT: You MUST answer ONLY based on the following context. Do not use any external knowledge.\n\nContext:\n{context}\n\nUser's question: {query}"
        elif use_rag and not context:
            # This should not happen as we return early above, but just in case
            return {
                "query": query,
                "answer": "I don't have enough information in my knowledge base to answer this question. Please upload relevant documents or data first.",
                "tokens_used": 0,
                "context_used": False,
                "sources": [],
                "rag_required": True,
                "rag_data_missing": True
            }
        else:
            # RAG is disabled - normal query
            prompt = f"{base_prompt}\n\nUser's question: {query}"
            
        # Call AI with forced GPT-4o-mini - run in thread if synchronous
        ai_response = await asyncio.to_thread(
            ai_responser.query,
            template=prompt,
            model_provider=model_provider,
            model_name=model_name
        )
        
        # Handle both old string format and new dict format
        if isinstance(ai_response, dict):
            answer = ai_response.get("content", "")
            tokens_used = ai_response.get("tokens", 0)
        else:
            answer = ai_response
            tokens_used = 0
        
        logger.info(f"AI conversation used {tokens_used} tokens with model {model_name}")
        
        self.conversation_history.append({"user": query, "assistant": answer})
        
        return {
            "query": query,
            "answer": answer,
            "tokens_used": tokens_used,
            "context_used": bool(context),
            "sources": sources,
            "rag_required": use_rag,
            "rag_data_missing": False  # If we reached here with RAG enabled, we have data
        }