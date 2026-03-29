"""
Utility script to check and fix Instagram automations for providers with low credits
This can be run as a scheduled job or manually for maintenance
"""

import asyncio
import logging
from supabase_client import supabase
from instagram_routers.automation_core.shared_utils import (
    check_user_credits,
    deactivate_all_instagram_automations
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_all_providers_credits():
    """
    Check all providers and deactivate Instagram automations for those with credits < 0
    """
    try:
        # Get all providers with their current credits
        billing_data = supabase.table("billing_usage").select(
            "provider_id, current_credits"
        ).execute()
        
        if not billing_data.data:
            logger.info("No billing records found")
            return
        
        low_credit_count = 0
        total_deactivated = 0
        
        for record in billing_data.data:
            provider_id = record.get('provider_id')
            current_credits = record.get('current_credits', 0)
            
            if current_credits < 0:
                logger.warning(
                    f"Provider {provider_id} has negative credits: {current_credits}"
                )
                low_credit_count += 1
                
                # Deactivate all Instagram automations
                result = await deactivate_all_instagram_automations(provider_id)
                
                if result.get('success'):
                    automations_count = result.get('automations_deactivated', 0)
                    total_deactivated += automations_count
                    logger.info(
                        f"Deactivated {automations_count} automations for provider {provider_id}"
                    )
        
        logger.info(
            f"\n{'='*60}\n"
            f"Credit Check Summary:\n"
            f"  - Total providers checked: {len(billing_data.data)}\n"
            f"  - Providers with negative credits: {low_credit_count}\n"
            f"  - Total automations deactivated: {total_deactivated}\n"
            f"{'='*60}"
        )
        
    except Exception as e:
        logger.error(f"Error checking provider credits: {e}")


async def reactivate_automations_for_provider(provider_id: str):
    """
    Reactivate all Instagram automations for a provider (when credits are restored)
    
    Args:
        provider_id: Provider ID to reactivate automations for
    """
    try:
        # First check if they have credits
        credit_check = await check_user_credits(provider_id)
        
        if not credit_check.get('has_credits', False):
            logger.warning(
                f"Cannot reactivate automations for {provider_id} - "
                f"insufficient credits: {credit_check.get('current_credits', 0)}"
            )
            return False
        
        # Get all platform_user_ids for this provider on Instagram
        accounts_response = supabase.table("connected_accounts").select(
            "platform_user_id"
        ).eq("provider_id", provider_id).eq("platform", "instagram").execute()
        
        if not accounts_response.data:
            logger.warning(f"No Instagram accounts found for provider {provider_id}")
            return False
        
        platform_user_ids = [account['platform_user_id'] for account in accounts_response.data]
        reactivated_count = 0
        
        # Reactivate all paused automations
        for platform_user_id in platform_user_ids:
            result = supabase.table("automations").update({
                "activation_status": "ACTIVE",
                "updated_at": "NOW()"
            }).eq("platform_user_id", platform_user_id).eq(
                "platform", "instagram"
            ).eq("activation_status", "PAUSED").execute()
            
            if result.data:
                reactivated_count += len(result.data)
                logger.info(
                    f"Reactivated {len(result.data)} automations for "
                    f"platform_user_id {platform_user_id}"
                )
        
        logger.info(
            f"Successfully reactivated {reactivated_count} automations for provider {provider_id}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error reactivating automations for {provider_id}: {e}")
        return False


async def main():
    """Main function to run the credit check"""
    logger.info("Starting credit check and automation deactivation process...")
    await check_all_providers_credits()
    logger.info("Credit check completed")


if __name__ == "__main__":
    # Run the credit check
    asyncio.run(main())
    
    # To reactivate for a specific provider:
    # asyncio.run(reactivate_automations_for_provider("YOUR_PROVIDER_ID"))
