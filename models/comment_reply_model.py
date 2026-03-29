from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class CommentReplyPayload(BaseModel):
    rule_id: Optional[str] = None
    automation_id: Optional[str] = None
    name: str
    platform: Optional[str] = None
    description: Optional[str] = None

    platform_user_id: str
    provider_id: UUID
    reply_type:Optional[str]
    custom_message:Optional[str]
    trigger_type: Optional[str] = None
    keywords: Optional[str] = None
    match_type: Optional[str] = None

    post_selection_type: Optional[str] = None
    specific_post_ids: Optional[List[str]] = None
    dateRange: Optional[str] = "1d"

    ai_context_rules: Optional[str] = None
    system_prompt: Optional[str] = ""

    comment_reply_template_type: Optional[str] = None

    max_replies_per_post: Optional[int] = None
    max_actions: Optional[int] = None

    reply_count_condition: Optional[str] = None
    reply_count_value: int

    model_provider: Optional[str] = None
    model_name: str
    temperature: float

    is_rag_enabled: bool = False
    confidence_threshold: float

    model_usage: Optional[str] = None

    time_period_seconds: Optional[int] = None
    user_cooldown_seconds: Optional[int] = None
