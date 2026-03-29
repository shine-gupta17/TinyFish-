"""
Async Redis Cache Utility
Provides singleton Redis cache instance for session and data caching
"""
import redis.asyncio as redis
import json
from typing import Optional, Any
import os
import logging

logger = logging.getLogger(__name__)


class AsyncRedisCache:
    """Async Redis cache wrapper with singleton pattern"""
    
    _instance: Optional[redis.Redis] = None
    
    @classmethod
    async def get_instance(cls) -> redis.Redis:
        """Get or create Redis connection instance"""
        if cls._instance is None:
            try:
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                cls._instance = await redis.from_url(redis_url, decode_responses=True)
                await cls._instance.ping()
                logger.info("✅ Redis cache connected successfully")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Redis: {e}")
                raise
        return cls._instance
    
    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            cache = await cls.get_instance()
            data = await cache.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 1 hour)
            
        Returns:
            True if successful
        """
        try:
            cache = await cls.get_instance()
            await cache.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    @classmethod
    async def delete(cls, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        try:
            cache = await cls.get_instance()
            await cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    @classmethod
    async def clear_pattern(cls, pattern: str) -> int:
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Redis key pattern (e.g., "user_*")
            
        Returns:
            Number of keys deleted
        """
        try:
            cache = await cls.get_instance()
            keys = await cache.keys(pattern)
            if keys:
                return await cache.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}")
            return 0
    
    @classmethod
    async def close(cls):
        """Close Redis connection"""
        try:
            if cls._instance:
                await cls._instance.close()
                cls._instance = None
                logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Decorators for easy caching
def cache_result(ttl: int = 3600, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time to live for cache in seconds
        key_prefix: Prefix for cache key
        
    Example:
        @cache_result(ttl=300, key_prefix="user")
        async def get_user_data(user_id: str):
            return await db.get_user(user_id)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = await AsyncRedisCache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            await AsyncRedisCache.set(cache_key, result, ttl=ttl)
            return result
        
        return wrapper
    return decorator
