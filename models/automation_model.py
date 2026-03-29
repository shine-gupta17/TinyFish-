import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

class PlatformEnum(str, enum.Enum):
    instagram = 'instagram'
    facebook = 'facebook'
    whatsapp = 'whatsapp'
    telegram = 'telegram'
    x = 'x'
    threads = 'threads'

class AutomationHealthStatus(str, enum.Enum):
    HEALTHY = 'HEALTHY'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


class Automation(BaseModel):
    automation_id: UUID = Field(default_factory=uuid4)
    platform: PlatformEnum
    platform_user_id: str
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    automation_type: str
    activation_status: str = 'ACTIVE'
    health_status: AutomationHealthStatus = AutomationHealthStatus.HEALTHY
    model_usage: str = 'PLATFORM_DEFAULT'
    cumulative_cost: Decimal = Field(default=Decimal("0.00"), max_digits=10, decimal_places=6)
    execution_count: int = 0
    last_triggered_at: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_actions: Optional[int] = None
    time_period_seconds: Optional[int] = None
    user_cooldown_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('automation_type')
    def validate_automation_type(cls, v):
        allowed_types = {'AI_DM_CONVERSATION', 'DM_REPLY', 'COMMENT_REPLY'}
        if v not in allowed_types:
            raise ValueError(f'automation_type must be one of {allowed_types}')
        return v

    @validator('activation_status')
    def validate_activation_status(cls, v):
        allowed_statuses = {'ACTIVE', 'PAUSED','SCHEDULE'}
        if v not in allowed_statuses:
            raise ValueError(f'activation_status must be one of {allowed_statuses}')
        return v

    @validator('model_usage')
    def validate_model_usage(cls, v):
        allowed_usages = {'PLATFORM_DEFAULT', 'USER_CUSTOM'}
        if v not in allowed_usages:
            raise ValueError(f'model_usage must be one of {allowed_usages}')
        return v

    class Config:
        from_attributes = True
        use_enum_values = True

