from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel

class PrivateReply(BaseModel):
    name: Optional[str] = None,
    description:Optional[str] = None,
    platform_user_id: Optional[str] = None
    provider_id: Optional[str] = None
    post_selection_type: Optional[Literal["ALL", "SPECIFIC", "DATE_RANGE"]] = None
    specific_post_ids: Optional[List[str]] = None
    date_range: Optional[Literal["1d", "1w", "1m", None]] = None
    trigger_type: Optional[Literal["KEYWORD", "AI_DECISION"]] = None
    keywords: Optional[str] = None
    match_type: Optional[Literal["CONTAINS", "EXACT", "STARTSWITH"]] = None
    ai_context_rules: Optional[str] = None
    system_prompt: Optional[str] = None
    reply_template_type: Optional[Literal["text", "image", "button_template", "quick_replies", ""]] = None
    reply_template_content: Optional[Dict[str, Any]] = None
    model_provider: Optional[Literal["GROQ", "OPENAI"]] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    is_rag_enabled: Optional[bool] = None
    confidence_threshold: Optional[float] = None
    model_usage: Optional[Literal["PLATFORM_DEFAULT", "CUSTOM"]] = None
    schedule_type: Optional[Literal["CONTINUOUS", "DAILY_ONE_TIME"]] = None
    max_actions: Optional[int] = None
    time_period_seconds: Optional[int] = None
    user_cooldown_seconds: Optional[int] = None

