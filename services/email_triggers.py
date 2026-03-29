"""
Email Trigger Service - Handles sending emails at appropriate times
Integrates with user events, automation runs, and scheduled tasks
"""

import logging
from typing import Optional
from services.email_service import email_service
from supabase_client_async import async_supabase

logger = logging.getLogger(__name__)


async def get_user_email(provider_id: str) -> Optional[str]:
    """
    Fetch user's email address from their provider_id.
    Checks multiple fields to find the email.
    
    Args:
        provider_id: User's unique provider ID
        
    Returns:
        str: User's email address or None if not found
    """
    try:
        response = await async_supabase.select(
            "user_profiles",
            select="email,provider_id,auth_provider",
            filters={"provider_id": provider_id},
            limit=1
        )
        
        if response.get("data") and len(response["data"]) > 0:
            user_data = response["data"][0]
            email = user_data.get("email")
            
            if email:
                logger.info(f"Found email for provider_id {provider_id}: {email}")
                return email
            else:
                logger.warning(f"User {provider_id} has no email in user_profiles table")
                logger.debug(f"User data: {user_data}")
                return None
        
        logger.warning(f"No user profile found for provider_id: {provider_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching user email for {provider_id}: {str(e)}")
        return None


async def get_user_name(provider_id: str) -> str:
    """
    Fetch user's full name from their provider_id.
    
    Args:
        provider_id: User's unique provider ID
        
    Returns:
        str: User's full name or "User" as default
    """
    try:
        response = await async_supabase.select(
            "user_profiles",
            select="full_name",
            filters={"provider_id": provider_id},
            limit=1
        )
        
        if response.get("data") and len(response["data"]) > 0:
            name = response["data"][0].get("full_name")
            return name if name else "User"
        
        return "User"
        
    except Exception as e:
        logger.error(f"Error fetching user name for {provider_id}: {str(e)}")
        return "User"


class EmailTrigger:
    """Service to trigger emails based on user events"""
    
    @staticmethod
    async def send_welcome_email_on_signup(user_email: str, user_name: str = "User") -> bool:
        """
        Trigger welcome email when new user signs up
        
        Args:
            user_email: User's email address
            user_name: User's full name
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            logger.info(f"Sending welcome email to {user_email}")
            success = email_service.send_welcome_email(user_email, user_name)
            
            if success:
                logger.info(f"Welcome email sent successfully to {user_email}")
            else:
                logger.warning(f"Failed to send welcome email to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_welcome_email_on_signup: {str(e)}")
            return False
    
    @staticmethod
    async def send_credit_consumption_notification(
        user_email: str,
        user_name: str,
        automation_name: str,
        credits_consumed: int,
        remaining_credits: int
    ) -> bool:
        """
        Send notification when automation consumes credits
        
        Args:
            user_email: User's email
            user_name: User's name
            automation_name: Name of the automation that consumed credits
            credits_consumed: Number of credits consumed
            remaining_credits: Credits remaining after consumption
            
        Returns:
            bool: True if sent successfully
        """
        try:
            logger.info(f"Sending credit consumption notification to {user_email} for automation: {automation_name}")
            success = email_service.send_credit_consumption_email(
                user_email,
                user_name,
                automation_name,
                credits_consumed,
                remaining_credits
            )
            
            if success:
                logger.info(f"Credit consumption email sent to {user_email}")
            else:
                logger.warning(f"Failed to send credit consumption email to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_credit_consumption_notification: {str(e)}")
            return False
    
    @staticmethod
    async def send_zero_credits_alert(user_email: str, user_name: str) -> bool:
        """
        Send alert when user's credits reach zero
        
        Args:
            user_email: User's email
            user_name: User's name
            
        Returns:
            bool: True if sent successfully
        """
        try:
            logger.info(f"Sending zero credits alert to {user_email}")
            success = email_service.send_zero_credits_email(user_email, user_name)
            
            if success:
                logger.info(f"Zero credits alert sent to {user_email}")
            else:
                logger.warning(f"Failed to send zero credits alert to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_zero_credits_alert: {str(e)}")
            return False
    
    @staticmethod
    async def send_feedback_request(user_email: str, user_name: str) -> bool:
        """
        Send feedback request email 10 days after signup
        
        Args:
            user_email: User's email
            user_name: User's name
            
        Returns:
            bool: True if sent successfully
        """
        try:
            logger.info(f"Sending feedback request to {user_email}")
            success = email_service.send_feedback_request_email(user_email, user_name)
            
            if success:
                logger.info(f"Feedback request sent to {user_email}")
            else:
                logger.warning(f"Failed to send feedback request to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_feedback_request: {str(e)}")
            return False
    
    @staticmethod
    async def send_purchase_confirmation(
        user_email: str,
        user_name: str,
        credits_purchased: int,
        total_credits: int,
        amount_paid: float,
        plan_type: str = "Pay-As-You-Go"
    ) -> bool:
        """
        Send confirmation email after credit purchase or subscription
        
        Args:
            user_email: User's email
            user_name: User's name
            credits_purchased: Credits bought in this transaction
            total_credits: Total credits after purchase
            amount_paid: Amount paid in rupees
            plan_type: Type of plan (Monthly Subscription/Pay-As-You-Go)
            
        Returns:
            bool: True if sent successfully
        """
        try:
            logger.info(f"Sending purchase confirmation to {user_email}")
            success = email_service.send_credit_purchase_confirmation_email(
                user_email,
                user_name,
                credits_purchased,
                total_credits,
                amount_paid,
                plan_type
            )
            
            if success:
                logger.info(f"Purchase confirmation sent to {user_email}")
            else:
                logger.warning(f"Failed to send purchase confirmation to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_purchase_confirmation: {str(e)}")
            return False


# ============ PROVIDER_ID BASED EMAIL METHODS (FOR LOGGED-IN USERS) ============

class EmailTriggerByProvider:
    """Service to trigger emails using provider_id (for authenticated users)"""
    
    @staticmethod
    async def send_welcome_email_by_provider(provider_id: str) -> bool:
        """
        Send welcome email to user identified by provider_id.
        Sends to the logged-in user's email from database (NOT admin email).
        
        Args:
            provider_id: User's unique provider ID
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            user_email = await get_user_email(provider_id)
            if not user_email:
                logger.error(f"Cannot send welcome email: No email found for provider_id {provider_id}")
                return False
            
            user_name = await get_user_name(provider_id)
            
            # Send to logged-in user's email from database
            logger.info(f"Sending welcome email to {user_email} (user's registered email)")
            success = email_service.send_welcome_email(user_email, user_name)
            
            if success:
                logger.info(f"Welcome email sent successfully to {user_email}")
            else:
                logger.warning(f"Failed to send welcome email to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_welcome_email_by_provider: {str(e)}")
            return False
    
    @staticmethod
    async def send_credit_consumption_by_provider(
        provider_id: str,
        automation_name: str,
        credits_consumed: int,
        remaining_credits: int
    ) -> bool:
        """
        Send credit consumption notification using provider_id.
        Sends to the logged-in user's email from database (NOT admin email).
        
        Args:
            provider_id: User's unique provider ID
            automation_name: Name of automation that consumed credits
            credits_consumed: Credits consumed
            remaining_credits: Credits remaining
            
        Returns:
            bool: True if sent successfully
        """
        try:
            user_email = await get_user_email(provider_id)
            if not user_email:
                logger.error(f"Cannot send consumption email: No email found for provider_id {provider_id}")
                return False
            
            user_name = await get_user_name(provider_id)
            
            # Send to logged-in user's email from database
            logger.info(f"Sending credit consumption email to {user_email} (user's registered email)")
            success = email_service.send_credit_consumption_email(
                user_email,
                user_name,
                automation_name,
                credits_consumed,
                remaining_credits
            )
            
            if success:
                logger.info(f"Credit consumption email sent to {user_email}")
            else:
                logger.warning(f"Failed to send credit consumption email to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_credit_consumption_by_provider: {str(e)}")
            return False
    
    @staticmethod
    async def send_zero_credits_alert_by_provider(provider_id: str) -> bool:
        """
        Send zero credits alert using provider_id.
        Sends to the logged-in user's email from database (NOT admin email).
        
        Args:
            provider_id: User's unique provider ID
            
        Returns:
            bool: True if sent successfully
        """
        try:
            user_email = await get_user_email(provider_id)
            if not user_email:
                logger.error(f"Cannot send zero credits alert: No email found for provider_id {provider_id}")
                return False
            
            user_name = await get_user_name(provider_id)
            
            # Send to logged-in user's email from database
            logger.info(f"Sending zero credits alert to {user_email} (user's registered email)")
            success = email_service.send_zero_credits_email(user_email, user_name)
            
            if success:
                logger.info(f"Zero credits alert sent to {user_email}")
            else:
                logger.warning(f"Failed to send zero credits alert to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_zero_credits_alert_by_provider: {str(e)}")
            return False
    
    @staticmethod
    async def send_feedback_request_by_provider(provider_id: str) -> bool:
        """
        Send feedback request email using provider_id.
        Sends to ADMIN_EMAIL (static - chatverses@gmail.com) NOT to user's email.
        This is a special case for feedback collection.
        
        Args:
            provider_id: User's unique provider ID
            
        Returns:
            bool: True if sent successfully
        """
        try:
            import os
            
            user_name = await get_user_name(provider_id)
            
            # Send to static ADMIN_EMAIL for feedback (special case)
            admin_email = os.getenv("ADMIN_EMAIL", "chatverses@gmail.com")
            logger.info(f"Sending feedback request to ADMIN_EMAIL: {admin_email} (for user: {provider_id})")
            success = email_service.send_feedback_request_email(admin_email, user_name)
            
            if success:
                logger.info(f"Feedback request sent to admin email: {admin_email}")
            else:
                logger.warning(f"Failed to send feedback request to admin email: {admin_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_feedback_request_by_provider: {str(e)}")
            return False
    
    @staticmethod
    async def send_purchase_confirmation_by_provider(
        provider_id: str,
        credits_purchased: int,
        total_credits: int,
        amount_paid: float,
        plan_type: str = "Pay-As-You-Go"
    ) -> bool:
        """
        Send purchase confirmation using provider_id.
        Sends to the logged-in user's email from database (NOT admin email).
        
        Args:
            provider_id: User's unique provider ID
            credits_purchased: Credits purchased
            total_credits: Total credits after purchase
            amount_paid: Amount paid
            plan_type: Type of plan (optional)
            
        Returns:
            bool: True if sent successfully
        """
        try:
            user_email = await get_user_email(provider_id)
            if not user_email:
                logger.error(f"Cannot send purchase confirmation: No email found for provider_id {provider_id}")
                return False
            
            user_name = await get_user_name(provider_id)
            
            # Send to logged-in user's email from database
            logger.info(f"Sending purchase confirmation to {user_email} (user's registered email)")
            success = email_service.send_credit_purchase_confirmation_email(
                user_email,
                user_name,
                credits_purchased,
                total_credits,
                amount_paid,
                plan_type
            )
            
            if success:
                logger.info(f"Purchase confirmation sent to {user_email}")
            else:
                logger.warning(f"Failed to send purchase confirmation to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_purchase_confirmation_by_provider: {str(e)}")
            return False
    
    @staticmethod
    async def send_automation_created_notification(
        provider_id: str,
        automation_name: str,
        automation_type: str,
        credits_per_execution: int
    ) -> bool:
        """
        Send notification when user creates a new automation.
        Informs them how many credits the automation will consume per execution.
        Sends to the logged-in user's email from database (NOT admin email).
        
        Args:
            provider_id: User's unique provider ID
            automation_name: Name of the automation created
            automation_type: Type of automation (e.g., "COMMENT_REPLY", "PRIVATE_MESSAGE", "DM_KEYWORD")
            credits_per_execution: Credits consumed per automation run
            
        Returns:
            bool: True if sent successfully
        """
        try:
            user_email = await get_user_email(provider_id)
            if not user_email:
                logger.error(f"Cannot send automation notification: No email found for provider_id {provider_id}")
                return False
            
            user_name = await get_user_name(provider_id)
            
            # Send to logged-in user's email from database
            logger.info(f"Sending automation creation notification to {user_email} (user's registered email)")
            success = email_service.send_automation_created_email(
                user_email,
                user_name,
                automation_name,
                automation_type,
                credits_per_execution
            )
            
            if success:
                logger.info(f"Automation creation notification sent to {user_email}")
            else:
                logger.warning(f"Failed to send automation notification to {user_email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in send_automation_created_notification: {str(e)}")
            return False


# Singleton instances for easy access
email_trigger = EmailTrigger()
email_trigger_by_provider = EmailTriggerByProvider()
