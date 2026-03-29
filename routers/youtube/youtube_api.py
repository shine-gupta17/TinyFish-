from fastapi import APIRouter
from supabase_client import supabase
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os

router = APIRouter(
    prefix="/youtube",
    tags=["YouTube"]
)

google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")


async def get_youtube_service(user_id: str):
    """
    Creates and returns a YouTube service object for the given user.
    """
    gmail_data = (
        supabase.table("connected_accounts")
        .select("*")
        .eq("provider_id", user_id)
        .eq("platform", "youtube")
        .execute()
    )

    if not gmail_data.data:
        raise Exception("YouTube account not connected.")

    data = gmail_data.data[0]
    creds = Credentials.from_authorized_user_info(
        {
            "token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": google_client_id,
            "client_secret": google_client_secret,
            "scopes": data["scopes"],
            "universe_domain": "googleapis.com",
        }
    )
    return build("youtube", "v3", credentials=creds)


async def get_channel_details(user_id: str) -> dict:
    """
    Fetches basic details for the user's YouTube channel.
    """
    try:
        service = await get_youtube_service(user_id)
        response = service.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()
        return response
    except Exception as e:
        return {"error": str(e)}