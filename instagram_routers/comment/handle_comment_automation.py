"""
Comment Automation Handler - Main Entry Point
Routes comment events to the new refactored handler.
"""

import logging
from instagram_routers.comment.comment_automation_handler import handle_comment_automation as handle_comment_automation_new

logger = logging.getLogger(__name__)


async def handle_comment_automation(comment_event: dict, automation: dict, platform_user_id: str):
    """
    Handle comment events - routes to new refactored handler.
    
    This function maintains backward compatibility while using the new modular structure.
    """
    await handle_comment_automation_new(comment_event, automation, platform_user_id)
