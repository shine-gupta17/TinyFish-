from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Literal, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field
from typing import Optional, Literal

class UserProfile(BaseModel):
    email: Optional[str] = None
    phone_number: Optional[str] = None
    auth_provider: str
    provider_id: str
    full_name: Optional[str] = None
    username: Optional[str] = None
    profile_picture: Optional[str] = None
    is_verified: Optional[bool] = False

class CreateUserProfilePayload(BaseModel):
    provider_id: str
    email: str
    auth_provider: Literal["google", "email", "custom"]

class PlatformAccount(BaseModel):
    connected_account_id: int
    provider_id: str
    platform_user_id: str
    platform: str

class AutomationSettings(BaseModel):
    name: str
    selectedPostId: Optional[int] = None
    replyScope: Literal['specific', 'all', 'range']
    dateRange: Literal['1d', '3d', '7d']
    replyLogic: Literal['keyword', 'contextual', 'analyse']
    keywordMatchType: str
    keywords: List[str]
    aiContext: str
    replyCondition: str
    maxComments: int = Field(gt=0)
    delayTime: int = Field(ge=0)

class CommentReplyAutomationPayload(BaseModel):
    automation_id: Optional[int] = None
    automation_settings: AutomationSettings
    platform_account: PlatformAccount


class DmKeywordReplyAutomationPayload(BaseModel):
    automation_id: Optional[UUID] = None
    provider_id: str
    platform_user_id: str
    name: str = Field(..., min_length=1)
    description: str = "No Desc"

    platform: Literal["instagram"]

    trigger_type: Literal["KEYWORD", "AI_DECISION"]
    keywords: Optional[List[str]] = Field(default=None)
    match_type: Literal["EXACT", "CONTAINS", "STARTS_WITH"]

    # AI context
    ai_context_rules: Optional[str] = ""
    system_prompt: str = ""
    reply_template_type: Literal["text", "image", "button_template", "quick_replies"] = "text"
    reply_template_content: Dict[str, Any]

    # Additional automation parameters
    model_usage: Literal["PLATFORM_DEFAULT", "USER_CUSTOM"] = "PLATFORM_DEFAULT"
    execution_count: Optional[int] = None # Keeping this as is, as it was not explicitly requested for removal
    user_cooldown_seconds: Optional[int] = None


class AIChatBotConfigPayload(BaseModel):
    connected_account_id: int
    platform_user_id: str
    platform: Literal["instagram"]
    provider_id: str
    bot_name: str = Field(..., min_length=1)
    system_prompt: str
    model_name: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    is_rag_enabled: bool = False
    is_active: bool = True
    
    class Config:
        extra = "forbid"  # This will help catch any extra fields being sent

class RagStatusPayload(BaseModel):
    is_rag_enabled: bool

class WebUrlPayload(BaseModel):
    website_url: HttpUrl
    provider_id: str | None = None
    platform_user_id: str
    platform: Literal["instagram"]

class CustomTextPayload(BaseModel):
    text: str = Field(..., min_length=1)
    provider_id: str | None = None
    platform_user_id: str
    platform: Literal["instagram"]

class SendMessagePayload(BaseModel):
    recipient_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    platform_user_id: str = Field(..., min_length=1)

class GetPostPayload(BaseModel):
    platform_user_id: str = Field(..., min_length=1)
