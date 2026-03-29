import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

class PlatformEnum(str, enum.Enum):
    instagram = 'instagram'
    facebook = 'facebook'
    whatsapp = 'whatsapp'
    telegram = 'telegram'
    x = 'x'
    threads = 'threads'

class RagSourceType(str, enum.Enum):
    WEBSITE = 'WEBSITE'
    FILE = 'FILE'
    TEXT = 'TEXT'

class ProcessingStatus(str, enum.Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'

class ModelProviderEnum(str, enum.Enum):
    OPENAI = 'OPENAI'
    GROQ = 'GROQ'
    ANTHROPIC = 'ANTHROPIC'
    GOOGLE = 'GOOGLE'

class AiConversation(BaseModel):
    ai_conversation_id: UUID = Field(default_factory=uuid4)
    automation_id: UUID
    source_id: Optional[UUID] = None
    model_provider: ModelProviderEnum = ModelProviderEnum.OPENAI
    model_name: str = 'gpt-4o'
    system_prompt: str = 'You are a helpful assistant.'
    temperature: Decimal = Field(default=Decimal("0.7"), max_digits=2, decimal_places=1)
    is_rag_enabled: bool = False
    rag_system_prompt: str = 'Use the provided context to answer the user question. If the context does not contain the answer, say you do not have enough information.'
    confidence_threshold: Decimal = Field(default=Decimal("0.75"), max_digits=3, decimal_places=2)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        use_enum_values = True


class RagDataSource(BaseModel):
    source_id: UUID = Field(default_factory=uuid4)
    platform: PlatformEnum
    platform_user_id: str
    rag_source_type: RagSourceType
    input_source: str
    content: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    vector_db_provider: str = 'pinecone'
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
        use_enum_values = True

