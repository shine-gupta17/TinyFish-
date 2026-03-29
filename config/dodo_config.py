"""
Dodo Payments Configuration and Client Setup
Handles initialization of Dodo Payments client with environment variables
"""

import os
from typing import Optional
from dodopayments import DodoPayments, AsyncDodoPayments
from functools import lru_cache

# Environment Variables
DODO_PAYMENTS_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY")
DODO_PAYMENTS_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")  # "test_mode" or "live_mode"
DODO_BRAND_ID = os.getenv("DODO_BRAND_ID")  # Your Dodo Payments Brand ID

# Validate required configuration
if not DODO_PAYMENTS_API_KEY:
    raise ValueError("DODO_PAYMENTS_API_KEY must be set as an environment variable")

if not DODO_BRAND_ID:
    raise ValueError("DODO_BRAND_ID must be set as an environment variable")


@lru_cache()
def get_dodo_client() -> DodoPayments:
    """
    Get or create a cached Dodo Payments synchronous client
    
    Returns:
        DodoPayments: Configured Dodo Payments client instance
    """
    return DodoPayments(
        bearer_token=DODO_PAYMENTS_API_KEY,
        environment=DODO_PAYMENTS_ENVIRONMENT
    )


@lru_cache()
def get_async_dodo_client() -> AsyncDodoPayments:
    """
    Get or create a cached Dodo Payments asynchronous client
    
    Returns:
        AsyncDodoPayments: Configured async Dodo Payments client instance
    """
    return AsyncDodoPayments(
        bearer_token=DODO_PAYMENTS_API_KEY,
        environment=DODO_PAYMENTS_ENVIRONMENT
    )


# Pricing Configuration
# Two models available for users

# Model 1: Fixed Monthly Subscription (Usage-based, resets monthly)
SUBSCRIPTION_PLANS = {
    "monthly_5m": {
        "name": "Monthly 5M Tokens Subscription",
        "product_id": os.getenv("DODO_PRODUCT_MONTHLY_5M"),
        "tokens": 5_000_000,
        "price_usd": 10,
        "price_inr": 850,
        "billing_interval": "monthly",
        "description": "5 million tokens per month. Usage-based: tokens reset every month on renewal."
    }
}

# Model 2: Flexible Pay-As-You-Go (Buy exact tokens you need)
# Base unit: 500K tokens for ₹100
# Users can buy in multiples: 1x, 2x, 3x, 4x, 5x, 10x, etc.
# Examples:
#   - 1x (500K) = ₹100
#   - 2x (1M) = ₹200
#   - 4x (2M) = ₹400
#   - 10x (5M) = ₹1000
#   - 20x (10M) = ₹2000
PAY_AS_YOU_GO = {
    "base_unit": {
        "name": "Pay-As-You-Go Tokens",
        "product_id": os.getenv("DODO_PRODUCT_PAYG"),  # Single product for flexible quantity
        "tokens_per_unit": 500_000,  # 500K tokens per unit
        "price_per_unit_usd": 1,     # $1 per 500K
        "price_per_unit_inr": 100,   # ₹100 per 500K
        "min_units": 1,              # Minimum 1 unit (500K tokens)
        "max_units": 100,            # Maximum 100 units (50M tokens)
        "description": "Buy exactly the tokens you need. Each unit = 500K tokens for ₹100. No subscription, no expiry."
    }
}

# Meter Configuration
METER_CONFIG = {
    "token_usage": {
        "meter_id": os.getenv("DODO_METER_TOKEN_USAGE"),  # Set in Dodo dashboard
        "event_name": "token_consumed",
        "description": "Track token consumption for usage-based billing"
    }
}


def get_subscription_plan(plan_key: str) -> Optional[dict]:
    """Get subscription plan configuration by key"""
    return SUBSCRIPTION_PLANS.get(plan_key)


def get_payg_config() -> dict:
    """Get pay-as-you-go configuration"""
    return PAY_AS_YOU_GO["base_unit"]


def calculate_payg_price(units: int, currency: str = "INR") -> dict:
    """
    Calculate price for pay-as-you-go tokens
    
    Args:
        units: Number of units (1 unit = 500K tokens)
        currency: Currency code (USD or INR)
    
    Returns:
        dict with tokens, price, and breakdown
    """
    config = get_payg_config()
    
    if units < config["min_units"] or units > config["max_units"]:
        raise ValueError(
            f"Units must be between {config['min_units']} and {config['max_units']}"
        )
    
    tokens = units * config["tokens_per_unit"]
    price_per_unit = config["price_per_unit_usd"] if currency == "USD" else config["price_per_unit_inr"]
    total_price = units * price_per_unit
    
    return {
        "units": units,
        "tokens": tokens,
        "price_per_unit": price_per_unit,
        "total_price": total_price,
        "currency": currency,
        "description": f"{tokens:,} tokens for {currency} {total_price}"
    }
