"""
Rate limiting middleware for production API
"""
import time
import logging
from typing import Dict, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter (replace with Redis for distributed systems)
    """
    
    def __init__(self):
        # Store: {user_id: [(timestamp, count), ...]}
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 3600  # Cleanup old entries every hour
        self.last_cleanup = time.time()
    
    def _cleanup_old_entries(self):
        """Remove expired entries to prevent memory leak"""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            for user_id in list(self.requests.keys()):
                self.requests[user_id] = [
                    (ts, count) for ts, count in self.requests[user_id]
                    if current_time - ts < 3600
                ]
                if not self.requests[user_id]:
                    del self.requests[user_id]
            self.last_cleanup = current_time
    
    def is_allowed(
        self, 
        identifier: str, 
        max_requests: int = 100, 
        window_seconds: int = 60
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed under rate limit
        
        Args:
            identifier: User ID or IP address
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        
        Returns:
            (is_allowed, retry_after_seconds)
        """
        self._cleanup_old_entries()
        
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Filter requests within current window
        recent_requests = [
            (ts, count) for ts, count in self.requests[identifier]
            if ts > window_start
        ]
        
        total_requests = sum(count for _, count in recent_requests)
        
        if total_requests >= max_requests:
            # Calculate when the oldest request will expire
            if recent_requests:
                oldest_request_time = min(ts for ts, _ in recent_requests)
                retry_after = int(window_seconds - (current_time - oldest_request_time)) + 1
                return False, retry_after
            return False, window_seconds
        
        # Add current request
        recent_requests.append((current_time, 1))
        self.requests[identifier] = recent_requests
        
        return True, None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        self.requests_per_minute = requests_per_minute
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check endpoints
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Extract user identifier (use user_id from auth or IP address)
        identifier = request.client.host
        
        # Try to get user_id from headers or query params
        user_id = request.headers.get("X-User-ID") or request.query_params.get("user_id")
        if user_id:
            identifier = f"user:{user_id}"
        
        # Check rate limit
        is_allowed, retry_after = self.rate_limiter.is_allowed(
            identifier,
            max_requests=self.requests_per_minute,
            window_seconds=60
        )
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {identifier}")
            return HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - sum(
                count for _, count in self.rate_limiter.requests.get(identifier, [])
            )
        )
        
        return response
