"""
Router initialization for Dodo Payments
"""

from .dodo_subscriptions import router as subscriptions_router
from .dodo_webhooks import router as webhooks_router

__all__ = ["subscriptions_router", "webhooks_router"]
