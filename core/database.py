"""
Async Supabase client with connection pooling for production use
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
import httpx
from supabase import create_client, Client
from config.env_config import SUPABASE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)


class AsyncSupabaseClient:
    """
    Async wrapper for Supabase with connection pooling and retry logic
    """
    _instance: Optional['AsyncSupabaseClient'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise Exception("Supabase environment variables are missing")
        
        # Synchronous client for operations that don't have async support
        self.sync_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # HTTP client with connection pooling for async operations
        self.http_client = httpx.AsyncClient(
            base_url=SUPABASE_URL,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=100,  # Max concurrent connections
                max_keepalive_connections=20,  # Keep alive pool
                keepalive_expiry=30.0
            )
        )
        logger.info("AsyncSupabaseClient initialized with connection pooling")
    
    @classmethod
    async def get_instance(cls) -> 'AsyncSupabaseClient':
        """Singleton pattern for database client"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def execute_query(
        self, 
        table: str, 
        operation: str, 
        data: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        select: str = "*",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute database query with retry logic
        
        Args:
            table: Table name
            operation: 'select', 'insert', 'update', 'delete'
            data: Data for insert/update operations
            filters: Filter conditions (e.g., {'provider_id': 'user123'})
            select: Columns to select
            max_retries: Maximum retry attempts
        """
        for attempt in range(max_retries):
            try:
                endpoint = f"/rest/v1/{table}"
                
                if operation == "select":
                    params = {"select": select}
                    if filters:
                        for key, value in filters.items():
                            params[key] = f"eq.{value}"
                    response = await self.http_client.get(endpoint, params=params)
                
                elif operation == "insert":
                    response = await self.http_client.post(endpoint, json=data)
                
                elif operation == "update":
                    params = {}
                    if filters:
                        for key, value in filters.items():
                            params[key] = f"eq.{value}"
                    response = await self.http_client.patch(endpoint, json=data, params=params)
                
                elif operation == "delete":
                    params = {}
                    if filters:
                        for key, value in filters.items():
                            params[key] = f"eq.{value}"
                    response = await self.http_client.delete(endpoint, params=params)
                
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                response.raise_for_status()
                return {"data": response.json(), "error": None}
            
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    return {"data": None, "error": str(e)}
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                    return {"data": None, "error": str(e)}
                await asyncio.sleep(2 ** attempt)
        
        return {"data": None, "error": "Max retries exceeded"}
    
    async def close(self):
        """Close HTTP client connections"""
        await self.http_client.aclose()
        logger.info("AsyncSupabaseClient connections closed")


# Synchronous client for backward compatibility
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@lru_cache()
def get_sync_supabase() -> Client:
    """Get synchronous Supabase client (cached)"""
    return supabase


async def get_async_supabase() -> AsyncSupabaseClient:
    """Dependency injection for async Supabase client"""
    return await AsyncSupabaseClient.get_instance()
