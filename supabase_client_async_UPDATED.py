"""
Async Supabase Client using httpx for optimal performance
This client provides async database operations with optimized connection pooling
"""
import os
import httpx
from typing import Optional, Dict, Any, List
from config import SUPABASE_KEY, SUPABASE_URL
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class AsyncSupabaseClient:
    """Async Supabase client for database operations with retry logic"""
    
    _instance: Optional['AsyncSupabaseClient'] = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise Exception("Supabase environment variables are missing")
        
        self.supabase_url = SUPABASE_URL
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)
        self.base_url = f"{self.supabase_url}/rest/v1"
        
        # Create persistent async client with optimized connection pooling
        self._client = httpx.AsyncClient(
            http2=True,  # Enable HTTP/2 multiplexing for better concurrency
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=100,  # ✅ INCREASED from 20
                max_connections=500,            # ✅ INCREASED from 100
                max_idle_redirect_loops=5,
                keep_alive_expiry=30.0
            ),
            headers={
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
        )
        logger.info("✅ AsyncSupabaseClient initialized with optimized pooling")
    
    @classmethod
    async def get_instance(cls) -> 'AsyncSupabaseClient':
        """Singleton pattern for client reuse"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            logger.info("✅ AsyncSupabaseClient connection closed")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def select(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Async SELECT operation with retry logic
        
        Args:
            table: Table name
            select: Columns to select (default: "*")
            filters: Dict of column: value filters (eq operator)
            limit: Maximum number of rows
            order: Order by column (e.g., "created_at.desc")
        """
        try:
            url = f"{self.base_url}/{table}"
            params = {"select": select}
            
            if filters:
                for key, value in filters.items():
                    params[key] = f"eq.{value}"
            
            if limit:
                params["limit"] = str(limit)
            
            if order:
                params["order"] = order
            
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            
            return {"data": response.json(), "error": None}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in select: {e.response.text}")
            return {"data": None, "error": str(e)}
        except Exception as e:
            logger.error(f"Error in select: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def insert(
        self,
        table: str,
        data: Dict[str, Any] | List[Dict[str, Any]],
        upsert: bool = False
    ) -> Dict[str, Any]:
        """
        Async INSERT operation with retry logic
        
        Args:
            table: Table name
            data: Single dict or list of dicts to insert
            upsert: If True, update on conflict
        """
        try:
            url = f"{self.base_url}/{table}"
            headers = {}
            
            if upsert:
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            
            response = await self._client.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            return {"data": response.json(), "error": None}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in insert: {e.response.text}")
            return {"data": None, "error": str(e)}
        except Exception as e:
            logger.error(f"Error in insert: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Async UPDATE operation with retry logic
        
        Args:
            table: Table name
            data: Data to update
            filters: Dict of column: value filters (eq operator)
        """
        try:
            url = f"{self.base_url}/{table}"
            params = {}
            
            for key, value in filters.items():
                params[key] = f"eq.{value}"
            
            response = await self._client.patch(url, json=data, params=params)
            response.raise_for_status()
            
            return {"data": response.json(), "error": None}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in update: {e.response.text}")
            return {"data": None, "error": str(e)}
        except Exception as e:
            logger.error(f"Error in update: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Async DELETE operation with retry logic
        
        Args:
            table: Table name
            filters: Dict of column: value filters (eq operator)
        """
        try:
            url = f"{self.base_url}/{table}"
            params = {}
            
            for key, value in filters.items():
                params[key] = f"eq.{value}"
            
            response = await self._client.delete(url, params=params)
            response.raise_for_status()
            
            return {"data": response.json(), "error": None}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in delete: {e.response.text}")
            return {"data": None, "error": str(e)}
        except Exception as e:
            logger.error(f"Error in delete: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True
    )
    async def rpc(
        self,
        function_name: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call a Supabase RPC function with retry logic
        
        Args:
            function_name: Name of the RPC function
            params: Function parameters
        """
        try:
            url = f"{self.supabase_url}/rest/v1/rpc/{function_name}"
            
            response = await self._client.post(url, json=params or {})
            response.raise_for_status()
            
            return {"data": response.json(), "error": None}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in rpc: {e.response.text}")
            return {"data": None, "error": str(e)}
        except Exception as e:
            logger.error(f"Error in rpc: {str(e)}")
            raise


# Keep the synchronous client for backward compatibility
from supabase import create_client, Client

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase environment variables are missing")

SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Async client instance
async_supabase = AsyncSupabaseClient()
