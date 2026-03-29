from dotenv import load_dotenv
import os

load_dotenv()

# --- Instagram API Credentials ---
INSTAGRAM_CLIENT_ID = os.getenv("INSTAGRAM_CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("INSTAGRAM_CLIENT_SECRET")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI")

# --- Facebook API Credentials ---
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")

# --- Frontend URL ---
# Used for redirecting users back to your app after authentication.

FRONTEND_PLATFORM_URL = os.getenv("FRONTEND_PLATFORM_URL") 

BACKEND_URL = os.getenv("BACKEND_URL")

# --- Supabase Credentials ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# --- Vector Database & Storage Config ---
PINECONE_CHAT_INDEX = os.getenv("PINECONE_CHAT_INDEX")
CHAT_BUCKET_NAME = os.getenv("CHAT_BUCKET_NAME","chatrag")

# --- S3-Compatible Storage (Supabase) ---
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_REGION = os.getenv("S3_REGION", "ap-southeast-1")

# --- Razorpay Credentials ---
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")