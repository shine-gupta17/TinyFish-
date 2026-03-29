"""
Redis caching layer with async support
"""
import logging
from typing import Optional, Any, Callable
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)

# Simple in-memory cache for development (replace with Redis in production)
_memory_cache: dict = {}


class CacheManager:
    """Cache manager with TTL support"""
    
    @staticmethod
    def _generate_key(prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if key in _memory_cache:
                return _memory_cache[key]
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    @staticmethod
    async def set(key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL (seconds)"""
        try:
            _memory_cache[key] = value
            # Note: In-memory cache doesn't support TTL, implement Redis for production
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    @staticmethod
    async def delete(key: str) -> bool:
        """Delete key from cache"""
        try:
            if key in _memory_cache:
                del _memory_cache[key]
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    @staticmethod
    async def clear_pattern(pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            keys_to_delete = [k for k in _memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del _memory_cache[key]
            return len(keys_to_delete)
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0


def cache_async(prefix: str = "default", ttl: int = 300):
    """
    Async cache decorator
    
    Usage:
        @cache_async(prefix="user_profile", ttl=600)
        async def get_user_profile(user_id: str):
            # ... database query
            return data
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = CacheManager._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = await CacheManager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value
            
            # Cache miss - execute function
            logger.debug(f"Cache miss for key: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            await CacheManager.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str):
    """
    Invalidate cache entries matching pattern
    
    Usage:
        await invalidate_cache_pattern("user_profile:123")
    """
    async def invalidate():
        count = await CacheManager.clear_pattern(pattern)
        logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")
    
    return invalidate()
