"""
Production configuration settings
"""
from dotenv import load_dotenv
import os
from typing import List

load_dotenv()


class Settings:
    """Application settings"""
    
    # Application
    APP_NAME: str = "ChatVerse API"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    
    # URLs
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_PLATFORM_URL: str = os.getenv("FRONTEND_PLATFORM_URL", "http://localhost:5173")
    
    # CORS Origins (comma-separated in .env)
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://chatverses.web.app"
    ).split(",")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-session-key-change-in-production")
    SESSION_COOKIE_SECURE: bool = ENVIRONMENT == "production"
    
    # Database - Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Redis Cache
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    
    # Instagram API
    INSTAGRAM_CLIENT_ID: str = os.getenv("INSTAGRAM_CLIENT_ID", "")
    INSTAGRAM_CLIENT_SECRET: str = os.getenv("INSTAGRAM_CLIENT_SECRET", "")
    INSTAGRAM_REDIRECT_URI: str = os.getenv("INSTAGRAM_REDIRECT_URI", "")
    
    # Facebook API
    FACEBOOK_CLIENT_ID: str = os.getenv("FACEBOOK_CLIENT_ID", "")
    FACEBOOK_CLIENT_SECRET: str = os.getenv("FACEBOOK_CLIENT_SECRET", "")
    FACEBOOK_REDIRECT_URI: str = os.getenv("FACEBOOK_REDIRECT_URI", "")
    
    # Vector Database
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_CHAT_INDEX: str = os.getenv("PINECONE_CHAT_INDEX", "")
    
    # Storage
    CHAT_BUCKET_NAME: str = os.getenv("CHAT_BUCKET_NAME", "")
    
    # Payment
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_SECRET: str = os.getenv("RAZORPAY_SECRET", "")
    
    # AI Models
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Background Tasks
    MAX_BACKGROUND_WORKERS: int = int(os.getenv("MAX_BACKGROUND_WORKERS", "10"))
    
    @classmethod
    def validate(cls):
        """Validate critical settings"""
        required = [
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_KEY", cls.SUPABASE_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


# Create settings instance
settings = Settings()

# Validate on import
if settings.ENVIRONMENT == "production":
    settings.validate()
