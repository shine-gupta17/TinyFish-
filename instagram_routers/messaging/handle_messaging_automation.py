"""
DM/Messaging Automation Handler - Main Entry Point
Routes messaging events to the new refactored handler.
"""

import logging
from typing import Optional
from instagram_routers.messaging.messaging_automation_handler import handle_messaging_automation as handle_messaging_automation_new

logger = logging.getLogger(__name__)


async def handle_messaging_automation(
    messaging_event: dict, 
    automation: dict, 
    platform_user_id: str,
    event_type: Optional[str] = None
):
    """
    Handle messaging events - routes to new refactored handler.
    
    This function maintains backward compatibility while using the new modular structure.
    
    Args:
        messaging_event: The messaging event from webhook
        automation: The automation configuration
        platform_user_id: Instagram platform user ID
        event_type: Type of event (user_text_message, user_image_message, user_audio_message, etc.)
    """
    await handle_messaging_automation_new(messaging_event, automation, platform_user_id, event_type)

