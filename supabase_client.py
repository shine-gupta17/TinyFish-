from supabase import create_client, Client
from config import SUPABASE_KEY, SUPABASE_URL
import os


if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase environment variables are missing")

# For backend operations, use service role key if available (bypasses RLS)
# Otherwise fallback to anon key (subject to RLS policies)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
