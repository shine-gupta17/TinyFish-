"""
Pydantic models for Dodo Payments subscription management
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal, Dict, Any, List
from datetime import datetime
from enum import Enum


class SubscriptionType(str, Enum):
    """Types of subscriptions available"""
    MONTHLY_5M = "monthly_5m"
    CUSTOM_PACKAGE = "custom_package"


class PaymentStatus(str, Enum):
    """Payment status types"""
    PENDING = "pending"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class Currency(str, Enum):
    """Supported currencies"""
    USD = "USD"
    INR = "INR"


# ==================== Request Models ====================

class CreateSubscriptionRequest(BaseModel):
    """Request to create a new subscription"""
    user_id: str = Field(..., description="User's provider ID")
    plan_key: str = Field(..., description="Subscription plan key (e.g., 'monthly_5m')")
    currency: Currency = Field(default=Currency.INR, description="Billing currency")
    
    # Customer details
    email: EmailStr = Field(..., description="Customer email")
    name: str = Field(..., description="Customer full name")
    
    # Billing address
    country: str = Field(default="IN", description="Country code (ISO 2-letter)")
    city: Optional[str] = Field(None, description="City")
    street: Optional[str] = Field(None, description="Street address")
    zipcode: Optional[str] = Field(None, description="Zip/Postal code")
    state: Optional[str] = Field(None, description="State")
    
    # Optional
    return_url: Optional[str] = Field(None, description="URL to redirect after payment")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional metadata")


class PurchaseTokenPackageRequest(BaseModel):
    """Request to purchase custom token packages"""
    user_id: str = Field(..., description="User's provider ID")
    package_key: str = Field(default="payg", description="Token package key (default: 'payg' for pay-as-you-go)")
    quantity: int = Field(default=1, ge=1, description="Number of packages to purchase")
    currency: Currency = Field(default=Currency.INR, description="Billing currency")
    
    # Customer details
    email: EmailStr = Field(..., description="Customer email")
    name: str = Field(..., description="Customer full name")
    
    # Billing address
    country: str = Field(default="IN", description="Country code")
    city: Optional[str] = Field(None, description="City")
    street: Optional[str] = Field(None, description="Street address")
    zipcode: Optional[str] = Field(None, description="Zip/Postal code")
    state: Optional[str] = Field(None, description="State")
    
    return_url: Optional[str] = Field(None, description="URL to redirect after payment")


class UpdateSubscriptionRequest(BaseModel):
    """Request to update subscription"""
    cancel_at_next_billing_date: Optional[bool] = Field(None, description="Cancel at next billing cycle")
    status: Optional[PaymentStatus] = Field(None, description="New subscription status")
    metadata: Optional[Dict[str, str]] = Field(None, description="Updated metadata")


class ReportTokenUsageRequest(BaseModel):
    """Request to report token usage"""
    user_id: str = Field(..., description="User's provider ID")
    tokens_consumed: int = Field(..., ge=0, description="Number of tokens consumed")
    subscription_id: Optional[str] = Field(None, description="Associated subscription ID")
    operation_type: Optional[str] = Field(None, description="Type of operation (e.g., 'chat', 'automation')")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


# ==================== Response Models ====================

class SubscriptionResponse(BaseModel):
    """Response for subscription operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    
    # Subscription details
    subscription_id: Optional[str] = None
    payment_url: Optional[str] = None
    status: Optional[str] = None
    tokens_allocated: Optional[int] = None
    next_billing_date: Optional[datetime] = None


class TokenPackageResponse(BaseModel):
    """Response for token package purchase"""
    success: bool
    message: str
    payment_url: str
    payment_id: Optional[str] = None
    tokens: int
    total_cost: float
    currency: str


class TokenUsageResponse(BaseModel):
    """Response for token usage query"""
    user_id: str
    total_tokens_purchased: int
    total_tokens_consumed: int
    tokens_remaining: int
    active_subscriptions: List[Dict[str, Any]]
    usage_history: Optional[List[Dict[str, Any]]] = None


class WebhookVerificationResponse(BaseModel):
    """Response for webhook verification"""
    verified: bool
    event_type: Optional[str] = None
    message: str


# ==================== Database Models ====================

class DodoSubscriptionRecord(BaseModel):
    """Record for storing Dodo subscription in database"""
    id: Optional[int] = None
    dodo_subscription_id: str = Field(..., description="Subscription ID from Dodo Payments")
    dodo_customer_id: str = Field(..., description="Customer ID from Dodo Payments")
    provider_id: str = Field(..., description="User's provider ID")
    
    plan_type: str = Field(..., description="Type of plan")
    product_id: str = Field(..., description="Dodo product ID")
    
    status: str = Field(..., description="Subscription status")
    tokens_allocated: int = Field(..., description="Total tokens for this subscription")
    tokens_consumed: int = Field(default=0, description="Tokens consumed from this subscription")
    
    billing_interval: Optional[str] = Field(None, description="Billing interval (monthly, yearly)")
    currency: str = Field(..., description="Currency code")
    amount: float = Field(..., description="Subscription amount")
    
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "dodo_subscription_id": "sub_abc123",
                "dodo_customer_id": "cus_xyz789",
                "provider_id": "user_123",
                "plan_type": "monthly_5m",
                "product_id": "prod_5m_monthly",
                "status": "active",
                "tokens_allocated": 5000000,
                "tokens_consumed": 1234567,
                "billing_interval": "monthly",
                "currency": "INR",
                "amount": 850.00
            }
        }


class TokenUsageRecord(BaseModel):
    """Record for tracking token usage events"""
    id: Optional[int] = None
    provider_id: str
    subscription_id: Optional[str] = None
    
    tokens_consumed: int
    operation_type: Optional[str] = None
    
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "user_123",
                "subscription_id": "sub_abc123",
                "tokens_consumed": 1500,
                "operation_type": "chat_completion",
                "metadata": {"model": "gpt-4", "conversation_id": "conv_456"}
            }
        }


class DodoPaymentRecord(BaseModel):
    """Record for one-time token package purchases"""
    id: Optional[str] = None  # Payment ID from Dodo
    provider_id: str
    payment_id: str
    
    package_key: str
    tokens_purchased: int
    quantity: int
    
    amount: float
    currency: str
    status: str
    
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "user_123",
                "payment_id": "pay_xyz123",
                "package_key": "500k",
                "tokens_purchased": 1000000,
                "quantity": 2,
                "amount": 200.00,
                "currency": "INR",
                "status": "succeeded"
            }
        }
