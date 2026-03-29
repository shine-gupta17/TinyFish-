from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import secrets, base64, hashlib, urllib.parse, os, requests
from datetime import datetime, timedelta, timezone
from requests.models import HTTPBasicAuth
from supabase_client import supabase
import httpx
import logging
from typing import Optional

router = APIRouter(
    prefix="/auth/twitter",
    tags=["twitter authorization"]
)

logger = logging.getLogger(__name__)

# Replace with your app credentials/config
CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TWITTER_REDIRECT_URI")
SCOPES = ["tweet.read", "tweet.write", "users.email", "offline.access", "users.read"]

AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"


def generate_code_verifier_challenge():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge

async def get_x_profile(bearer_token: str) -> Optional[dict]:
    url = "https://api.x.com/2/users/me"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

    user = data.get("data", {})
    return {
        "x_user_id": user.get("id"),
        "x_username": user.get("username"),
        "x_name": user.get("name"),
    }

def upsert_twitter(provider_id: str, long_lived_token: str, expires_in_seconds, twitter_user_id, twitter_username):
    token_expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    current_time = datetime.now(timezone.utc).isoformat()

    # Delete existing record if any
    supabase.table("connected_accounts")\
        .delete()\
        .eq("platform_user_id", twitter_user_id)\
        .eq("platform", "twitter")\
        .execute()

    # Insert new record
    account_data = {
        "provider_id": provider_id,
        "platform": "twitter",
        "platform_user_id": twitter_user_id,
        "platform_username": twitter_username,
        "access_token": long_lived_token,
        "token_expires_at": token_expiry_time.isoformat(),
        "connected": True,
        "connected_at": current_time,
        "updated_at": current_time,
    }

    result = supabase.table("connected_accounts").insert(account_data).execute()
    return result


@router.get("/login")
async def login(request: Request):
    logger.debug(f"Twitter login request: {dict(request.query_params)}")
    verifier, challenge = generate_code_verifier_challenge()
    request.session["pkce_verifier"] = verifier
    user_id = request.query_params.get("user_id")

    logger.info(f"Twitter login initiated for user ID: {user_id}")

    # Protect against CSRF
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state+"_"+user_id,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # "user_id": request.query_params.get("user_id"),
    }
    return RedirectResponse(f"{AUTH_URL}?{urllib.parse.urlencode(params)}")


@router.get("/callback")
async def callback(request: Request):
    user_id = request.query_params.get("user_id")
    logger.info(f"Twitter OAuth callback for user ID: {user_id}")
    error = request.query_params.get("error")
    if error:
        return JSONResponse(content={"error": error}, status_code=400)

    state = request.query_params.get("state")
    logger.debug(f"Received state: {state}")

    state,user_id = state.split('_')

    logger.info(f"Parsed state: {state}, user ID: {user_id}")

    # logger.debug(f"STATE: {state}; OAUTH-STATE: {request.session.get('oauth_state')}")

    if not state or state != request.session.get("oauth_state"):
        return JSONResponse(content={"error": "State mismatch or missing"}, status_code=400)

    code = request.query_params.get("code")
    if not code:
        return JSONResponse(content={"error": "Missing authorization code"}, status_code=400)

    verifier = request.session.get("pkce_verifier")
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }

    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("API credentials [CLIENT_ID, CLIENT_SECRET] missing!")

    auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    resp = requests.post(TOKEN_URL, data=data, auth=auth)

    print(f"RESPONSE: {resp}")

    if resp.status_code != 200:
        return JSONResponse(
            content={"error": f"Token exchange failed: {resp.status_code}", "details": resp.text},
            status_code=400,
        )

    tokens = resp.json()
    print("TOKENS", tokens)
    request.session["access_token"] = tokens.get("access_token")
    request.session["refresh_token"] = tokens.get("refresh_token")
    request.session["expires_in"] = tokens.get("expires_in")

    # return {"message": "Authentication successful! You can now make calls as the user."}

    data = await get_x_profile(tokens.get("access_token"))

    data = upsert_twitter(
        user_id,
        tokens.get("refresh_token"),
        3000,
        data.get("x_user_id"),
        data.get("x_username")
    )

    return RedirectResponse(url="https://chatverse.io/platforms#")
