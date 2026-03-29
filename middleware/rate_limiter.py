"""
Rate Limiter Middleware
Prevents abuse and protects against concurrent request overload
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exception handler"""
    logger.warning(f"Rate limit exceeded for {get_remote_address(request)}")
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Too many requests. Please try again later.",
            "error_type": "RateLimitExceeded"
        }
    )


# Rate limit configurations
RATE_LIMITS = {
    "login": "5/minute",           # 5 login attempts per minute per IP
    "auth_callback": "10/minute",  # 10 OAuth callbacks per minute
    "credit_operations": "20/minute",  # 20 credit operations per minute
    "default": "100/minute",       # 100 general requests per minute
}
