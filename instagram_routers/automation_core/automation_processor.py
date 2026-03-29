"""
Unified Automation Processor
Handles common automation flow: validation, execution tracking, and token management.
"""

import logging
from typing import Dict, Any, Optional, Callable
from supabase_client import supabase
from instagram_routers.automation_core.shared_utils import (
    check_execution_limits,
    check_post_selection,
    track_automation_tokens,
    get_provider_id
)
from instagram_routers.automation_core.constants import (
    AutomationType,
    TriggerType,
    PostSelectionType
)
from utils.supabase_utils import increment_automation_execution_count

logger = logging.getLogger(__name__)


class AutomationProcessor:
    """
    Unified processor for Instagram automations.
    Handles validation, execution, and tracking.
    """
    
    def __init__(self):
        pass
    
    async def process_automation(
        self,
        automation: Dict[str, Any],
        event_data: Dict[str, Any],
        platform_user_id: str,
        handler_func: Callable,
        **handler_kwargs
    ) -> bool:
        """
        Process automation with unified validation and tracking.
        
        Args:
            automation: Automation configuration
            event_data: Event data (comment or message)
            platform_user_id: Platform user ID
            handler_func: Async function to handle the automation
            **handler_kwargs: Additional kwargs for handler function
            
        Returns:
            bool: True if processed successfully
        """
        try:
            automation_id = automation.get('automation_id')
            automation_type = automation.get('automation_type')
            
            logger.info(f"Processing automation {automation_id} of type {automation_type}")
            
            # Check execution limits
            if not check_execution_limits(automation):
                logger.info(f"Automation {automation_id} reached execution limits")
                return False
            
            # Call handler function
            result = await handler_func(
                automation=automation,
                event_data=event_data,
                platform_user_id=platform_user_id,
                **handler_kwargs
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing automation: {e}", exc_info=True)
            return False
    
    async def track_execution(
        self,
        automation_id: str,
        tokens_consumed: int,
        platform_user_id: str,
        config: Dict[str, Any] = None
    ) -> bool:
        """
        Track automation execution and token usage.
        
        Args:
            automation_id: Automation ID
            tokens_consumed: Tokens consumed
            platform_user_id: Platform user ID
            config: Optional config with provider_id
            
        Returns:
            bool: True if tracking successful
        """
        try:
            # Always increment execution count
            execution_updated = increment_automation_execution_count(
                automation_id=automation_id
            )
            
            if execution_updated:
                logger.info(f"Incremented execution count for {automation_id}")
            
            # Track tokens if any consumed
            if tokens_consumed > 0:
                provider_id = await get_provider_id(
                    platform_user_id=platform_user_id,
                    config=config
                )
                
                if provider_id:
                    token_tracked = await track_automation_tokens(
                        automation_id=automation_id,
                        tokens_consumed=tokens_consumed,
                        provider_id=provider_id
                    )
                    
                    if token_tracked:
                        logger.info(f"Tracked {tokens_consumed} tokens for {automation_id}")
                        return True
                    else:
                        logger.warning(f"Failed to track tokens for {automation_id}")
                        return False
                else:
                    logger.warning(f"No provider_id found for token tracking")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error tracking execution: {e}", exc_info=True)
            return False
    
    def validate_event_data(
        self,
        event_data: Dict[str, Any],
        platform_user_id: str,
        required_fields: list
    ) -> bool:
        """
        Validate event data has required fields.
        
        Args:
            event_data: Event data to validate
            platform_user_id: Platform user ID
            required_fields: List of required field paths (e.g., ['sender.id', 'message.text'])
            
        Returns:
            bool: True if valid
        """
        try:
            for field_path in required_fields:
                parts = field_path.split('.')
                value = event_data
                
                for part in parts:
                    value = value.get(part)
                    if value is None:
                        logger.warning(f"Missing required field: {field_path}")
                        return False
            
            # Check if sender is not the platform user (avoid self-interaction)
            sender_id = self._get_nested_value(event_data, ['sender', 'id']) or \
                        self._get_nested_value(event_data, ['value', 'from', 'id'])
            
            if sender_id and sender_id == platform_user_id:
                logger.info("Skipping self-interaction")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating event data: {e}")
            return False
    
    def _get_nested_value(self, data: Dict, path: list) -> Any:
        """Get nested value from dict using path list."""
        value = data
        for key in path:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    async def get_automation_config(
        self,
        automation_id: str,
        config_table: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get automation configuration from database.
        
        Args:
            automation_id: Automation ID
            config_table: Table name for configuration
            
        Returns:
            Optional[Dict]: Configuration or None
        """
        try:
            response = supabase.table(config_table).select("*").eq(
                "automation_id", automation_id
            ).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            logger.warning(f"No config found in {config_table} for {automation_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching config from {config_table}: {e}")
            return None


# Global processor instance
automation_processor = AutomationProcessor()
