"""
Configuration package for ChatVerse Backend
"""

from .env_config import (
    INSTAGRAM_CLIENT_ID,
    INSTAGRAM_CLIENT_SECRET,
    INSTAGRAM_REDIRECT_URI,
    FACEBOOK_CLIENT_ID,
    FACEBOOK_CLIENT_SECRET,
    FACEBOOK_REDIRECT_URI,
    FRONTEND_PLATFORM_URL,
    BACKEND_URL,
    SUPABASE_URL,
    SUPABASE_KEY,
    PINECONE_CHAT_INDEX,
    CHAT_BUCKET_NAME,
    S3_ACCESS_KEY_ID,
    S3_SECRET_ACCESS_KEY,
    S3_ENDPOINT_URL,
    S3_REGION,
    RAZORPAY_KEY_ID,
    RAZORPAY_SECRET
)

from .oauth_config import (
    PlatformScopes,
    CredentialFiles,
    get_platform_scopes,
    get_credential_file,
    validate_credential_files
)

__all__ = [
    # Environment config
    'INSTAGRAM_CLIENT_ID',
    'INSTAGRAM_CLIENT_SECRET',
    'INSTAGRAM_REDIRECT_URI',
    'FACEBOOK_CLIENT_ID',
    'FACEBOOK_CLIENT_SECRET',
    'FACEBOOK_REDIRECT_URI',
    'FRONTEND_PLATFORM_URL',
    'BACKEND_URL',
    'SUPABASE_URL',
    'SUPABASE_KEY',
    'PINECONE_CHAT_INDEX',
    'CHAT_BUCKET_NAME',
    'S3_ACCESS_KEY_ID',
    'S3_SECRET_ACCESS_KEY',
    'S3_ENDPOINT_URL',
    'S3_REGION',
    'RAZORPAY_KEY_ID',
    'RAZORPAY_SECRET',
    # OAuth config
    'PlatformScopes',
    'CredentialFiles', 
    'get_platform_scopes',
    'get_credential_file',
    'validate_credential_files'
]
