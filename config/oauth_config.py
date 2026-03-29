"""
Centralized OAuth Scope Configuration

This module defines all OAuth scopes for different platforms to prevent scope conflicts
and ensure proper authorization handling.

The key issue we're solving:
- Google OAuth returns different scopes than requested if you request overlapping scopes
- This causes oauthlib to raise a "Scope has changed" warning/error
- By carefully managing scopes per platform, we avoid conflicts

Strategy:
1. Each platform gets its own minimal, non-overlapping set of scopes
2. Common scopes (openid, email, profile) are included but managed carefully
3. Store actual granted scopes in database, not requested scopes
"""

import os
from typing import List, Dict
from pathlib import Path

# Base directory for all credential files
CREDENTIALS_DIR = Path(__file__).parent.parent / "credentials"

# Fallback to root directory if credentials folder doesn't exist
if not CREDENTIALS_DIR.exists():
    CREDENTIALS_DIR = Path(__file__).parent.parent


class PlatformScopes:
    """Defines OAuth scopes for each platform"""
    
    # Common Google OAuth scopes (used by all Google services)
    GOOGLE_OPENID = ["openid"]
    GOOGLE_PROFILE = ["https://www.googleapis.com/auth/userinfo.profile"]
    GOOGLE_EMAIL = ["https://www.googleapis.com/auth/userinfo.email"]
    
    # Gmail specific scopes
    GMAIL = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.modify"
    ]
    
    # Google Sheets specific scopes
    GOOGLE_SHEETS = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.file",
        # "https://www.googleapis.com/auth/spreadsheets",
        # "https://www.googleapis.com/auth/spreadsheets.readonly",
        # "https://www.googleapis.com/auth/drive.readonly"
    ]
    
    # Google Slides specific scopes
    GOOGLE_SLIDES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.file",
        # "https://www.googleapis.com/auth/presentations",
        # "https://www.googleapis.com/auth/presentations.readonly",
        # "https://www.googleapis.com/auth/drive.readonly"
    ]
    
    # Google Forms specific scopes
    GOOGLE_FORMS = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        # "https://www.googleapis.com/auth/forms.body",
        # "https://www.googleapis.com/auth/forms.body.readonly",
        # "https://www.googleapis.com/auth/forms.responses.readonly",
        "https://www.googleapis.com/auth/drive.file"
    ]
    
    # Google Docs specific scopes
    GOOGLE_DOCS = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.file",
        # "https://www.googleapis.com/auth/documents",
        # "https://www.googleapis.com/auth/documents.readonly",
        # "https://www.googleapis.com/auth/drive.readonly"
    ]
    
    # Google Drive specific scopes
    GOOGLE_DRIVE = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/drive.file",
        # "https://www.googleapis.com/auth/drive",
        # "https://www.googleapis.com/auth/drive.readonly",
        # "https://www.googleapis.com/auth/drive.metadata.readonly"
    ]
    
    # YouTube specific scopes
    YOUTUBE = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/youtube",  # Full YouTube access (read/write)
        "https://www.googleapis.com/auth/youtube.upload",  # Upload videos
        "https://www.googleapis.com/auth/youtube.force-ssl",  # Manage videos, ratings, comments
        # "https://www.googleapis.com/auth/youtube.readonly",  # Read-only access
        "https://www.googleapis.com/auth/youtubepartner",  # YouTube Analytics and reporting
    ]
    
    # Google Calendar specific scopes
    GOOGLE_CALENDAR = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar",
        # "https://www.googleapis.com/auth/calendar.events"
    ]
    
    # Google Meet specific scopes
    GOOGLE_MEET = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/calendar",
        # "https://www.googleapis.com/auth/calendar.events"
    ]
    
    # Instagram specific scopes (Meta Graph API)
    INSTAGRAM = [
        "instagram_business_basic",
        "instagram_business_manage_comments",
        "instagram_business_manage_insights",
        "instagram_business_content_publish",
        "instagram_business_manage_messages"
    ]
    
    # Facebook specific scopes (Meta Graph API)
    FACEBOOK = [
        "public_profile",
        "email",
        "pages_show_list",
        "pages_manage_posts",
        "pages_read_engagement",
        "instagram_basic",
        "instagram_manage_comments",
        "instagram_manage_insights"
    ]
    
    # LinkedIn specific scopes
    LINKEDIN = [
        "openid",
        "profile",
        "email",
        "w_member_social"
    ]
    
    # Twitter/X specific scopes
    TWITTER = [
        "tweet.read",
        "tweet.write",
        "users.read",
        "offline.access"
    ]
    
    # Power BI specific scopes (Microsoft Graph API)
    POWERBI = [
        "openid",
        "https://analysis.windows.net/powerbi/api/.default"
    ]
    
    # Notion specific scopes
    NOTION = [
        "read_content",
        "read_user",
        "insert_content"
    ]
    
    # HubSpot specific scopes (CRM API)
    HUBSPOT = [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "crm.objects.companies.read",
        "crm.objects.companies.write",
        "crm.objects.deals.read",
        "crm.objects.deals.write",
        "crm.schemas.contacts.read",
        "crm.schemas.companies.read",
        "crm.schemas.deals.read"
    ]


class CredentialFiles:
    """Defines credential file paths for each platform"""
    
    # Fallback unified Google credentials file
    GOOGLE_CREDENTIALS = str(CREDENTIALS_DIR / "google_credentials.json")
    
    # Individual credential file paths for each Google service
    GMAIL = str(CREDENTIALS_DIR / "gmail.json")
    GOOGLE_SHEETS = str(CREDENTIALS_DIR / "google_sheets.json")
    GOOGLE_SLIDES = str(CREDENTIALS_DIR / "google_slides.json")
    GOOGLE_FORMS = str(CREDENTIALS_DIR / "google_forms.json")
    GOOGLE_DOCS = str(CREDENTIALS_DIR / "google_docs.json")
    GOOGLE_DRIVE = str(CREDENTIALS_DIR / "google_drive.json")
    GOOGLE_CALENDAR = str(CREDENTIALS_DIR / "google_calender.json")
    GOOGLE_MEET = str(CREDENTIALS_DIR / "google_meet.json")
    YOUTUBE = str(CREDENTIALS_DIR / "youtube.json")
    
    # Non-Google platforms (still use individual files)
    NOTION = str(CREDENTIALS_DIR / "notion.json")
    POWERBI = str(CREDENTIALS_DIR / "powerbi.json")
    HUBSPOT = str(CREDENTIALS_DIR / "hubspot.json")
    
    @classmethod
    def _get_google_credentials(cls) -> str:
        """
        Get fallback unified Google credentials file path.
        Only used if individual file doesn't exist.
        """
        if os.path.exists(cls.GOOGLE_CREDENTIALS):
            return cls.GOOGLE_CREDENTIALS
        return None
    
    @classmethod
    def get_gmail_credentials(cls) -> str:
        """Get Gmail credentials file path - prioritizes individual file"""
        # Primary: Use individual Gmail credentials
        if os.path.exists(cls.GMAIL):
            return cls.GMAIL
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "gmail.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GMAIL  # Return individual path as default
    
    @classmethod
    def get_sheets_credentials(cls) -> str:
        """Get Google Sheets credentials file path - prioritizes individual file"""
        # Primary: Use individual Sheets credentials
        if os.path.exists(cls.GOOGLE_SHEETS):
            return cls.GOOGLE_SHEETS
        # Fallback to old locations
        for old_name in ["sheet.json", "gsheet.json"]:
            old_path = str(Path(__file__).parent.parent / old_name)
            if os.path.exists(old_path):
                return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_SHEETS
    
    @classmethod
    def get_slides_credentials(cls) -> str:
        """Get Google Slides credentials file path - prioritizes individual file"""
        # Primary: Use individual Slides credentials
        if os.path.exists(cls.GOOGLE_SLIDES):
            return cls.GOOGLE_SLIDES
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "google_slides.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_SLIDES
    
    @classmethod
    def get_forms_credentials(cls) -> str:
        """Get Google Forms credentials file path - prioritizes individual file"""
        # Primary: Use individual Forms credentials
        if os.path.exists(cls.GOOGLE_FORMS):
            return cls.GOOGLE_FORMS
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "google_form.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_FORMS
    
    @classmethod
    def get_docs_credentials(cls) -> str:
        """Get Google Docs credentials file path - prioritizes individual file"""
        # Primary: Use individual Docs credentials
        if os.path.exists(cls.GOOGLE_DOCS):
            return cls.GOOGLE_DOCS
        # Fallback to old locations
        for old_name in ["gdoc.json", "gsheet.json"]:
            old_path = str(Path(__file__).parent.parent / old_name)
            if os.path.exists(old_path):
                return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_DOCS
    
    @classmethod
    def get_drive_credentials(cls) -> str:
        """Get Google Drive credentials file path - prioritizes individual file"""
        # Primary: Use individual Drive credentials
        if os.path.exists(cls.GOOGLE_DRIVE):
            return cls.GOOGLE_DRIVE
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "google_drive.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_DRIVE
    
    @classmethod
    def get_youtube_credentials(cls) -> str:
        """Get YouTube credentials file path - prioritizes individual file"""
        # Primary: Use individual YouTube credentials
        if os.path.exists(cls.YOUTUBE):
            return cls.YOUTUBE
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "youtube.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.YOUTUBE
    
    @classmethod
    def get_calendar_credentials(cls) -> str:
        """Get Google Calendar credentials file path - prioritizes individual file"""
        # Primary: Use individual Calendar credentials
        if os.path.exists(cls.GOOGLE_CALENDAR):
            return cls.GOOGLE_CALENDAR
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "google_calender.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_CALENDAR
    
    @classmethod
    def get_meet_credentials(cls) -> str:
        """Get Google Meet credentials file path - prioritizes individual file"""
        # Primary: Use individual Meet credentials
        if os.path.exists(cls.GOOGLE_MEET):
            return cls.GOOGLE_MEET
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "google_meet.json")
        if os.path.exists(old_path):
            return old_path
        # Last resort: unified credentials
        unified = cls._get_google_credentials()
        if unified:
            return unified
        return cls.GOOGLE_MEET
    
    @classmethod
    def get_notion_credentials(cls) -> str:
        """Get Notion credentials file path (non-Google, uses individual file)"""
        if os.path.exists(cls.NOTION):
            return cls.NOTION
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "notion.json")
        if os.path.exists(old_path):
            return old_path
        return cls.NOTION
    
    @classmethod
    def get_powerbi_credentials(cls) -> str:
        """Get Power BI credentials file path (non-Google, uses individual file)"""
        if os.path.exists(cls.POWERBI):
            return cls.POWERBI
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "powerbi.json")
        if os.path.exists(old_path):
            return old_path
        return cls.POWERBI
    
    @classmethod
    def get_hubspot_credentials(cls) -> str:
        """Get HubSpot credentials file path (non-Google, uses individual file)"""
        if os.path.exists(cls.HUBSPOT):
            return cls.HUBSPOT
        # Fallback to old location
        old_path = str(Path(__file__).parent.parent / "hubspot.json")
        if os.path.exists(old_path):
            return old_path
        return cls.HUBSPOT


def get_platform_scopes(platform: str) -> List[str]:
    """
    Get the appropriate scopes for a given platform
    
    Args:
        platform: Platform name (e.g., 'gmail', 'google_sheets', 'youtube')
        
    Returns:
        List of OAuth scopes for that platform
    """
    platform_map = {
        "gmail": PlatformScopes.GMAIL,
        "google_sheets": PlatformScopes.GOOGLE_SHEETS,
        "google_slides": PlatformScopes.GOOGLE_SLIDES,
        "google_forms": PlatformScopes.GOOGLE_FORMS,
        "google_docs": PlatformScopes.GOOGLE_DOCS,
        "docs": PlatformScopes.GOOGLE_DOCS,  # alias
        "google_drive": PlatformScopes.GOOGLE_DRIVE,
        "drive": PlatformScopes.GOOGLE_DRIVE,  # alias
        "google_calendar": PlatformScopes.GOOGLE_CALENDAR,
        "calendar": PlatformScopes.GOOGLE_CALENDAR,  # alias
        "google_meet": PlatformScopes.GOOGLE_MEET,
        "meet": PlatformScopes.GOOGLE_MEET,  # alias
        "youtube": PlatformScopes.YOUTUBE,
        "instagram": PlatformScopes.INSTAGRAM,
        "facebook": PlatformScopes.FACEBOOK,
        "linkedin": PlatformScopes.LINKEDIN,
        "twitter": PlatformScopes.TWITTER,
        "notion": PlatformScopes.NOTION,
        "powerbi": PlatformScopes.POWERBI,
        "hubspot": PlatformScopes.HUBSPOT,
    }
    
    return platform_map.get(platform.lower(), [])


def get_credential_file(platform: str) -> str:
    """
    Get the credential file path for a given platform
    
    Args:
        platform: Platform name (e.g., 'gmail', 'google_sheets', 'youtube')
        
    Returns:
        Path to the credential file
    """
    platform_map = {
        "gmail": CredentialFiles.get_gmail_credentials,
        "google_sheets": CredentialFiles.get_sheets_credentials,
        "google_slides": CredentialFiles.get_slides_credentials,
        "google_forms": CredentialFiles.get_forms_credentials,
        "google_docs": CredentialFiles.get_docs_credentials,
        "docs": CredentialFiles.get_docs_credentials,  # alias
        "google_drive": CredentialFiles.get_drive_credentials,
        "drive": CredentialFiles.get_drive_credentials,  # alias
        "google_calendar": CredentialFiles.get_calendar_credentials,
        "calendar": CredentialFiles.get_calendar_credentials,  # alias
        "google_meet": CredentialFiles.get_meet_credentials,
        "meet": CredentialFiles.get_meet_credentials,  # alias
        "youtube": CredentialFiles.get_youtube_credentials,
        "notion": CredentialFiles.get_notion_credentials,
        "powerbi": CredentialFiles.get_powerbi_credentials,
        "hubspot": CredentialFiles.get_hubspot_credentials,
    }
    
    getter = platform_map.get(platform.lower())
    if getter:
        return getter()
    
    return ""


def validate_credential_files() -> Dict[str, bool]:
    """
    Check which credential files exist.
    
    Checks individual credential files for each service.
    Falls back to unified google_credentials.json if individual file doesn't exist.
    
    Returns:
        Dictionary mapping platform names to existence status
    """
    # Fallback unified Google credentials
    google_creds_exist = os.path.exists(CredentialFiles.GOOGLE_CREDENTIALS)
    
    return {
        # Google products - check individual files first, then fallback to unified
        "google_credentials": google_creds_exist,
        "gmail": os.path.exists(CredentialFiles.GMAIL) or google_creds_exist,
        "google_sheets": os.path.exists(CredentialFiles.GOOGLE_SHEETS) or google_creds_exist,
        "google_forms": os.path.exists(CredentialFiles.GOOGLE_FORMS) or google_creds_exist,
        "google_docs": os.path.exists(CredentialFiles.GOOGLE_DOCS) or google_creds_exist,
        "google_drive": os.path.exists(CredentialFiles.GOOGLE_DRIVE) or google_creds_exist,
        "google_calendar": os.path.exists(CredentialFiles.GOOGLE_CALENDAR) or google_creds_exist,
        "google_meet": os.path.exists(CredentialFiles.GOOGLE_MEET) or google_creds_exist,
        "google_slides": os.path.exists(CredentialFiles.GOOGLE_SLIDES) or google_creds_exist,
        "youtube": os.path.exists(CredentialFiles.YOUTUBE) or google_creds_exist,
        # Non-Google products - individual files
        "notion": os.path.exists(CredentialFiles.get_notion_credentials()),
        "powerbi": os.path.exists(CredentialFiles.get_powerbi_credentials()),
    }


def check_scope_permission(granted_scopes: List[str], required_scopes: List[str]) -> Dict[str, any]:
    """
    Check if granted scopes include at least one of the required scopes
    
    Args:
        granted_scopes: List of scopes granted by the user
        required_scopes: List of scopes required for an operation
        
    Returns:
        Dictionary with permission status and details
    """
    if not granted_scopes:
        return {
            "has_permission": False,
            "missing_scopes": required_scopes,
            "granted_scopes": []
        }
    
    granted_set = set(granted_scopes)
    required_set = set(required_scopes)
    
    # Check if at least one required scope is granted
    has_permission = bool(granted_set.intersection(required_set))
    missing_scopes = list(required_set - granted_set)
    
    return {
        "has_permission": has_permission,
        "missing_scopes": missing_scopes,
        "granted_scopes": granted_scopes
    }


def get_scope_descriptions(platform: str) -> Dict[str, str]:
    """
    Get human-readable descriptions for scopes of a platform
    
    Args:
        platform: Platform name (e.g., 'gmail', 'google_sheets')
        
    Returns:
        Dictionary mapping scope URLs to descriptions
    """
    descriptions = {
        "gmail": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/gmail.readonly": "Read your emails",
            "https://www.googleapis.com/auth/gmail.send": "Send emails on your behalf",
            "https://www.googleapis.com/auth/gmail.compose": "Compose new emails",
            "https://www.googleapis.com/auth/gmail.modify": "Modify your emails"
        },
        "google_sheets": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/spreadsheets": "View and manage your spreadsheets",
            "https://www.googleapis.com/auth/drive.file": "Access files created by this app"
        },
        "google_forms": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/forms.body": "Manage your forms",
            "https://www.googleapis.com/auth/forms.body.readonly": "View your forms",
            "https://www.googleapis.com/auth/forms.responses.readonly": "View form responses",
            "https://www.googleapis.com/auth/drive.file": "Access files created by this app"
        },
        "google_meet": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/calendar": "Manage your calendar",
            "https://www.googleapis.com/auth/calendar.events": "View and edit calendar events"
        },
        "google_calendar": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/calendar": "Manage your calendar",
            "https://www.googleapis.com/auth/calendar.events": "View and edit calendar events"
        },
        "google_docs": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/documents": "View and manage your Google Docs",
            "https://www.googleapis.com/auth/drive.file": "Access files created by this app"
        },
        "google_drive": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/drive": "Full access to your Google Drive",
            "https://www.googleapis.com/auth/drive.file": "Access files created by this app",
            "https://www.googleapis.com/auth/drive.readonly": "View and download all your Google Drive files (including videos)",
            "https://www.googleapis.com/auth/drive.metadata.readonly": "View metadata of your Drive files"
        },
        "youtube": {
            "openid": "Basic authentication",
            "https://www.googleapis.com/auth/userinfo.email": "View your email address",
            "https://www.googleapis.com/auth/userinfo.profile": "View your profile info",
            "https://www.googleapis.com/auth/youtube.readonly": "View your YouTube account",
            "https://www.googleapis.com/auth/youtube.force-ssl": "Manage your YouTube account"
        },
        "hubspot": {
            "crm.objects.contacts.read": "Read contacts",
            "crm.objects.contacts.write": "Create and update contacts",
            "crm.objects.companies.read": "Read companies",
            "crm.objects.companies.write": "Create and update companies",
            "crm.objects.deals.read": "Read deals",
            "crm.objects.deals.write": "Create and update deals",
            "crm.schemas.contacts.read": "Read contact properties",
            "crm.schemas.companies.read": "Read company properties",
            "crm.schemas.deals.read": "Read deal properties",
            "automation": "Access automation",
            "forms": "Access forms",
            "content": "Access content"
        }  
    }
    
    return descriptions.get(platform.lower(), {})
