"""
Production-Ready FastAPI Application with Async Support
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# Configuration
from config.settings import settings

# Core modules
from core.database import AsyncSupabaseClient
from core.rate_limiter import RateLimitMiddleware

# Import Routers
from routers import user_profiles
from routers import rag_data_sources as chat_rag
from routers import ai_chat_config as bot_config
from instagram_routers import instagram_webhook
from instagram_routers import instagram_automations as handle_instagram_automation
from routers import instagram_user_data as insta_user_data
from instagram_routers import instagram_auth as insta_auth
from routers.plans import billing_plan
from instagram_routers import instagram_insight
from routers import automations
from routers.twitter_routers import twitter_auth
from routers.gmail import gmail_auth
from routers.youtube import youtube_auth
from routers.google_sheets import google_sheets_auth
from routers.google_forms import google_forms_auth
from routers.google_meet import google_meet_auth
from routers.linkedin import linkedin_auth
from routers.gdoc import gdoc_auth
from routers import tinyfish
from routers import hackathon

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log') if settings.ENVIRONMENT == 'production' else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)


# Application Lifespan Management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup and shutdown)
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Initialize async database client
    db_client = await AsyncSupabaseClient.get_instance()
    logger.info("Database client initialized")
    
    # Initialize Sentry for production error tracking
    if settings.SENTRY_DSN and settings.ENVIRONMENT == 'production':
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=0.1,
            )
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("Sentry SDK not installed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await db_client.close()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready API for social media automation with AI",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch all unhandled exceptions
    """
    logger.error(
        f"Unhandled exception for {request.method} {request.url}: {exc}",
        exc_info=True,
        extra={
            "path": str(request.url),
            "method": request.method,
            "client": request.client.host if request.client else None
        }
    )
    
    # Don't expose internal errors in production
    error_detail = str(exc) if settings.DEBUG else "Internal server error"
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": error_detail,
            "error_type": type(exc).__name__
        }
    )


# Middleware Configuration

# 1. Trusted Host (security - prevent host header attacks)
if settings.ENVIRONMENT == 'production':
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.chatverse.io", "*.azurewebsites.net"]
    )

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"]
)

# 3. Session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="none",
    https_only=settings.SESSION_COOKIE_SECURE
)

# 4. GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 5. Rate Limiting
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE
    )
    logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} req/min")


# Prometheus metrics (optional - uncomment if you have prometheus-fastapi-instrumentator installed)
# try:
#     from prometheus_fastapi_instrumentator import Instrumentator
#     Instrumentator().instrument(app).expose(app)
#     logger.info("Prometheus metrics enabled at /metrics")
# except ImportError:
#     logger.info("Prometheus instrumentator not installed")


# Include Routers
app.include_router(user_profiles.router)
app.include_router(insta_auth.router)
app.include_router(instagram_insight.router)
app.include_router(instagram_webhook.router)
app.include_router(insta_user_data.router)
app.include_router(chat_rag.router)
app.include_router(bot_config.router)
app.include_router(handle_instagram_automation.router)
app.include_router(automations.router)
app.include_router(twitter_auth.router)
app.include_router(gmail_auth.router)
app.include_router(billing_plan.router)
app.include_router(youtube_auth.router)
app.include_router(google_sheets_auth.router)
app.include_router(google_forms_auth.router)
app.include_router(google_meet_auth.router)
app.include_router(linkedin_auth.router)
app.include_router(gdoc_auth.router)
app.include_router(gdoc_auth.router_callback)
app.include_router(tinyfish.router)
app.include_router(hackathon.router)


# Health Check Endpoints
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Comprehensive health check endpoint
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }
    
    # Check database connectivity
    try:
        db_client = await AsyncSupabaseClient.get_instance()
        # Simple query to test connection
        result = await db_client.execute_query(
            table="user_profiles",
            operation="select",
            select="provider_id",
            filters={"provider_id": "health_check_test"}
        )
        health_status["checks"]["database"] = "connected" if result["error"] is None else "error"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Add more health checks as needed
    # - Redis connectivity
    # - External API availability
    # - Disk space
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Kubernetes readiness probe endpoint
    """
    return {"ready": True}


@app.get("/live", tags=["Health"])
async def liveness_check():
    """
    Kubernetes liveness probe endpoint
    """
    return {"alive": True}


# Run application (for development)
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        use_colors=True
    )
