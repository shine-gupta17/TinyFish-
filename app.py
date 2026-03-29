# app.py - Optimized for VPS Deployment with Full Async Support

import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# Initialize async Supabase client
from supabase_client_async import async_supabase

# --- Import Refactored Routers ---
from routers import user_profiles
from routers import rag_data_sources as chat_rag
from routers import ai_chat_config as bot_config
from instagram_routers import instagram_webhook
from instagram_routers import instagram_automations as handle_instagram_automation
from routers import instagram_user_data as insta_user_data 
from instagram_routers import instagram_auth as insta_auth 
from instagram_routers import instagram_profile
from facebook_routers import facebook_auth
from routers.plans import billing_plan    
from instagram_routers import instagram_insight
from routers import automations
from routers.twitter_routers import twitter_auth
from routers.gmail import gmail_auth
from routers.youtube import youtube_auth
from routers.google_sheets import google_sheets_auth
from routers.google_slides import google_slides_auth
from routers.google_forms import google_forms_auth
from routers.google_calendar import google_calendar_auth
from routers.google_meet import google_meet_auth
from routers.google_drive import google_drive_auth
from routers.linkedin import linkedin_auth
from routers.gdoc import gdoc_auth
from routers.notion import notion_auth
from routers.powerbi import powerbi_auth
from routers.hubspot import hubspot_auth
from routers.platforms import mcp_router
from routers.feedback import feedback_router
from routers import transactions
from routers import chat_pdf_upload
from routers import rag_sessions
from routers import chat_image_upload
from routers import hackathon



# Configure logging
logging.basicConfig(level=logging.INFO)
from routers.dodo_payments import subscriptions_router, webhooks_router

# Configure logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
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
    logger.info("🚀 Starting ChatVerse API v3.0.0 (Async Optimized)")
    logger.info("📊 Initializing async database client...")
    
    # Verify async client is ready
    try:
        db = await async_supabase.get_instance()
        logger.info("✅ Database client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database client: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down application...")
    await async_supabase.close()
    logger.info("✅ Database connections closed gracefully")

app = FastAPI(
    title="ChatVerse API",
    description="Async-optimized API for social media automation with AI",
    version="3.0.0",
    lifespan=lifespan
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any exception not explicitly handled by endpoints.
    """
    logger.error(
        f"❌ Unhandled exception for {request.method} {request.url}: {exc}",
        exc_info=True,
        extra={
            "path": str(request.url),
            "method": request.method,
            "client": request.client.host if request.client else None
        }
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"An unexpected internal server error occurred: {type(exc).__name__}",
            "error_type": type(exc).__name__
        }
    )

# CORS Configuration
import os
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    origins = cors_origins_env.split(",")
else:
    origins = [
        "http://localhost:5173",
        "https://chatverses.web.app",
        "https://chatverse.io",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

# Middleware Configuration (order matters!)

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "X-Request-ID"]
)

# 2. Session
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "super-secret-session-key-change-in-production"),
    same_site="none",
    https_only=True
)

# 3. GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- Include Refactored Routers ---
app.include_router(user_profiles.router)
app.include_router(insta_auth.router)
app.include_router(instagram_profile.router)
app.include_router(facebook_auth.router)
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
app.include_router(google_calendar_auth.router)
app.include_router(google_meet_auth.router)
app.include_router(google_sheets_auth.router)
app.include_router(google_slides_auth.router)
app.include_router(google_forms_auth.router)
app.include_router(google_drive_auth.router)
app.include_router(linkedin_auth.router)
app.include_router(gdoc_auth.router)
app.include_router(gdoc_auth.router_callback)
app.include_router(notion_auth.router)
app.include_router(powerbi_auth.router)
app.include_router(hubspot_auth.router)
app.include_router(mcp_router)
app.include_router(feedback_router)
app.include_router(transactions.router)
app.include_router(chat_pdf_upload.router)
app.include_router(rag_sessions.router)
app.include_router(chat_image_upload.router)
app.include_router(hackathon.router)

# Include Dodo Payments routers
app.include_router(subscriptions_router)
app.include_router(webhooks_router)



# Health Check Endpoints
@app.get("/", tags=["Health Check"])
async def root():
    """Root endpoint - health check"""
    return {
        "status": "healthy",
        "service": "ChatVerse API",
        "version": "9.0.0",
        "message": "Welcome to ChatVerse API - Async Optimized for VPS Deployment"
    }

@app.get("/health", tags=["Health Check"])
async def health_check():
    """
    Comprehensive health check endpoint for monitoring
    """
    health_status = {
        "status": "healthy",
        "version": "9.0.0",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        db = await async_supabase.get_instance()
        # Simple query to test connection
        result = await db.select(
            "user_profiles",
            select="provider_id",
            limit=1
        )
        health_status["checks"]["database"] = "connected" if result["error"] is None else "error"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.get("/ready", tags=["Health Check"])
async def readiness_check():
    """Readiness probe for deployment orchestration"""
    return {"ready": True}

@app.get("/live", tags=["Health Check"])
async def liveness_check():
    """Liveness probe for deployment orchestration"""
    return {"alive": True}


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 4))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    logger.info(f"👷 Workers: {workers}")
    logger.info(f"🐛 Debug mode: {debug}")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        workers=1 if debug else workers,
        log_level="info",
        access_log=True,
        use_colors=True,
        # Optimize for VPS deployment
        limit_concurrency=1000,
        limit_max_requests=10000,
        timeout_keep_alive=5
    )
