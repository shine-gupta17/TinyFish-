"""
Email Service - Handles sending emails via Resend API
Supports: Welcome, Credit Notifications, Feedback Requests, and Transaction Confirmations
"""

import os
import logging
from typing import Optional
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails via Resend API"""
    
    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.admin_email = os.getenv("ADMIN_EMAIL")
        self.from_email = os.getenv("FROM_EMAIL")
        self.resend_url = "https://api.resend.com/emails"
        
        if not self.resend_api_key:
            logger.warning("RESEND_API_KEY not set in environment variables. Email sending may fail.")
        if not self.admin_email:
            logger.warning("ADMIN_EMAIL not set in environment variables. Email sending may fail.")
        if not self.from_email:
            logger.warning("FROM_EMAIL not set in environment variables. Email sending may fail.")
    
    def send_feedback_email(
        self,
        user_name: Optional[str],
        user_email: Optional[str],
        feedback_type: str,
        rating: Optional[int],
        message: str,
        page_url: Optional[str],
        feedback_id: str
    ) -> bool:
        """
        Send feedback email to admin via Resend
        
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            # Create HTML email body
            html_content = self._create_feedback_html(
                user_name, user_email, feedback_type, rating, message, page_url, feedback_id
            )
            
            # Send email via Resend REST API
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": self.admin_email,
                "subject": f"New {feedback_type.upper()} Feedback from ChatVerse",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Feedback email sent successfully. Feedback ID: {feedback_id}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
            
        except Exception as e:
            logger.error(f"Error sending feedback email via Resend: {str(e)}")
            return False
    
    @staticmethod
    def _create_feedback_html(
        user_name: Optional[str],
        user_email: Optional[str],
        feedback_type: str,
        rating: Optional[int],
        message: str,
        page_url: Optional[str],
        feedback_id: str
    ) -> str:
        """Create HTML email content for feedback"""
        
        rating_display = f"<strong>Rating:</strong> {'⭐' * rating}/{5 * '⭐'}<br>" if rating else ""
        
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #c2410c 0%, #ea580c 100%);
                        color: white;
                        padding: 20px;
                        border-radius: 8px 8px 0 0;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                    }}
                    .feedback-type {{
                        display: inline-block;
                        background-color: #fff3cd;
                        color: #856404;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                        margin-top: 10px;
                        text-transform: capitalize;
                    }}
                    .field {{
                        margin: 15px 0;
                        padding: 10px;
                        background-color: #fff;
                        border-left: 4px solid #ea580c;
                        border-radius: 4px;
                    }}
                    .field-label {{
                        font-weight: bold;
                        color: #ea580c;
                        margin-bottom: 5px;
                    }}
                    .message-box {{
                        background-color: #f0f0f0;
                        padding: 15px;
                        border-radius: 4px;
                        margin: 10px 0;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                    .feedback-id {{
                        font-family: monospace;
                        background-color: #f0f0f0;
                        padding: 2px 6px;
                        border-radius: 3px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📬 New Feedback Received</h1>
                        <div class="feedback-type">{feedback_type.upper()}</div>
                    </div>
                    
                    <div class="field">
                        <div class="field-label">Feedback from:</div>
                        <div>{user_name or 'Anonymous'}</div>
                        {f'<div style="color: #666; font-size: 14px;">{user_email}</div>' if user_email else ''}
                    </div>
                    
                    {rating_display if rating_display else '<div class="field"><em>No rating provided</em></div>'}
                    
                    {f'<div class="field"><div class="field-label">Page URL:</div><div><a href="{page_url}">{page_url}</a></div></div>' if page_url else ''}
                    
                    <div class="field">
                        <div class="field-label">Message:</div>
                        <div class="message-box">{message}</div>
                    </div>
                    
                    <div class="footer">
                        <p><strong>Feedback ID:</strong> <span class="feedback-id">{feedback_id}</span></p>
                        <p>This feedback was submitted through the ChatVerse feedback form.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    # ============= NEW EMAIL METHODS =============
    
    def send_welcome_email(self, user_email: str, user_name: str = "User") -> bool:
        """
        Send welcome email to new user on signup
        
        Args:
            user_email: User's email address
            user_name: User's name
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_welcome_html(user_name)
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": "Welcome to ChatVerse! 🚀",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Welcome email sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
            return False
    
    def send_credit_consumption_email(
        self,
        user_email: str,
        user_name: str,
        automation_name: str,
        credits_consumed: int,
        remaining_credits: int
    ) -> bool:
        """
        Send email notifying user about credit consumption during automation
        
        Args:
            user_email: User's email
            user_name: User's name
            automation_name: Name of the automation
            credits_consumed: Number of credits consumed
            remaining_credits: Remaining credits after consumption
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_credit_consumption_html(
                user_name, automation_name, credits_consumed, remaining_credits
            )
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": f"Credit Update: {credits_consumed} Credits Used for {automation_name}",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Credit consumption email sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending credit consumption email: {str(e)}")
            return False
    
    def send_zero_credits_email(self, user_email: str, user_name: str) -> bool:
        """
        Send warning email when user's credits reach zero
        
        Args:
            user_email: User's email
            user_name: User's name
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_zero_credits_html(user_name)
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": "⚠️ Your ChatVerse Credits Have Run Out",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Zero credits alert sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending zero credits email: {str(e)}")
            return False
    
    def send_feedback_request_email(self, user_email: str, user_name: str) -> bool:
        """
        Send feedback request email 10 days after user signup
        
        Args:
            user_email: User's email
            user_name: User's name
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_feedback_request_html(user_name)
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": "How's Your ChatVerse Experience? 💭",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Feedback request email sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending feedback request email: {str(e)}")
            return False
    
    def send_credit_purchase_confirmation_email(
        self,
        user_email: str,
        user_name: str,
        credits_purchased: int,
        total_credits: int,
        amount_paid: float,
        plan_type: str = "Pay-As-You-Go"
    ) -> bool:
        """
        Send confirmation email after user purchases credits or subscribes
        
        Args:
            user_email: User's email
            user_name: User's name
            credits_purchased: Credits bought in this transaction
            total_credits: Total credits after purchase
            amount_paid: Amount paid
            plan_type: Type of plan (Monthly Subscription/Pay-As-You-Go)
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_credit_purchase_html(
                user_name, credits_purchased, total_credits, amount_paid, plan_type
            )
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": f"✅ Credit Purchase Confirmed - {credits_purchased} Credits Added!",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Credit purchase confirmation sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending purchase confirmation email: {str(e)}")
            return False
    
    # ============= HTML TEMPLATE METHODS =============
    
    @staticmethod
    def _create_welcome_html(user_name: str) -> str:
        """Create HTML for welcome email"""
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
                        color: white;
                        padding: 30px 20px;
                        border-radius: 8px 8px 0 0;
                        text-align: center;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 32px;
                    }}
                    .header p {{
                        margin: 10px 0 0 0;
                        font-size: 16px;
                        opacity: 0.9;
                    }}
                    .content {{
                        padding: 20px;
                        background: white;
                    }}
                    .highlight {{
                        background-color: #f0f0f0;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 15px 0;
                        border-left: 4px solid #000;
                    }}
                    .feature {{
                        display: inline-block;
                        background-color: #f9f9f9;
                        padding: 10px 15px;
                        border-radius: 4px;
                        margin: 5px;
                        font-size: 14px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background-color: #000;
                        color: white;
                        padding: 12px 30px;
                        border-radius: 4px;
                        text-decoration: none;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .cta-button:hover {{
                        background-color: #333;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to ChatVerse! 🚀</h1>
                        <p>Your AI-Powered Automation Companion</p>
                    </div>
                    
                    <div class="content">
                        <p>Hi {user_name},</p>
                        
                        <p>Welcome aboard! We're thrilled to have you join ChatVerse. You've just unlocked a powerful platform for automating your customer interactions across multiple channels.</p>
                        
                        <div class="highlight">
                            <strong>🎁 You've been credited with 20,000 starting credits!</strong>
                            <p>Use these to train your AI, set up automations, and engage with your audience.</p>
                        </div>
                        
                        <h3>What You Can Do Now:</h3>
                        <div>
                            <div class="feature">✨ Create AI Automations</div>
                            <div class="feature">💬 Live Chat Management</div>
                            <div class="feature">📊 Performance Analytics</div>
                            <div class="feature">🔄 Multi-Platform Support</div>
                        </div>
                        
                        <p>Get started by connecting your first platform and creating your first automation. Our AI will learn from your content and interactions to provide personalized responses.</p>
                        
                        <a href="https://app.chatverse.io/dashboard" class="cta-button">Go to Your Dashboard</a>
                        
                        <h3>Need Help?</h3>
                        <p>Check out our documentation or reach out to our support team at {os.getenv("ADMIN_EMAIL")}. We're here to help!</p>
                        
                        <div class="footer">
                            <p><strong>ChatVerse</strong> - AI-Powered Automation Platform</p>
                            <p>© 2025 ChatVerse. All rights reserved.</p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_credit_consumption_html(
        user_name: str,
        automation_name: str,
        credits_consumed: int,
        remaining_credits: int
    ) -> str:
        """Create HTML for credit consumption email"""
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
                        color: white;
                        padding: 20px;
                        border-radius: 8px 8px 0 0;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                    }}
                    .stat-box {{
                        display: inline-block;
                        background-color: white;
                        color: #000;
                        padding: 15px 20px;
                        border-radius: 4px;
                        margin: 10px 5px 0 0;
                        min-width: 200px;
                    }}
                    .stat-value {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #000;
                    }}
                    .stat-label {{
                        font-size: 12px;
                        color: #666;
                        margin-top: 5px;
                    }}
                    .warning {{
                        background-color: #fff3cd;
                        border-left: 4px solid #ff9800;
                        padding: 15px;
                        border-radius: 4px;
                        margin: 15px 0;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>💳 Credit Update</h1>
                        <p style="margin: 10px 0 0 0;">Automation: {automation_name}</p>
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>Your automation "<strong>{automation_name}</strong>" has just consumed credits. Here's what happened:</p>
                    
                    <div class="stat-box">
                        <div class="stat-value">{credits_consumed}</div>
                        <div class="stat-label">Credits Consumed</div>
                    </div>
                    
                    <div class="stat-box">
                        <div class="stat-value">{remaining_credits}</div>
                        <div class="stat-label">Credits Remaining</div>
                    </div>
                    
                    {f'<div class="warning"><strong>⚠️ Low Credits Alert!</strong><br>You have less than 50,000 credits remaining. Consider purchasing more to avoid service interruption.</div>' if remaining_credits < 50000 else ''}
                    
                    <p>Keep running your automations smoothly! If you need to purchase more credits, visit your billing dashboard anytime.</p>
                    
                    <div class="footer">
                        <p>ChatVerse - AI-Powered Automation Platform</p>
                        <p>This is an automated notification. Do not reply to this email.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_zero_credits_html(user_name: str) -> str:
        """Create HTML for zero credits alert"""
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #d32f2f 0%, #b71c1c 100%);
                        color: white;
                        padding: 30px 20px;
                        border-radius: 8px 8px 0 0;
                        text-align: center;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 32px;
                    }}
                    .alert {{
                        background-color: #ffebee;
                        border: 2px solid #d32f2f;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 15px 0;
                        text-align: center;
                    }}
                    .alert h2 {{
                        color: #d32f2f;
                        margin: 0;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background-color: #d32f2f;
                        color: white;
                        padding: 12px 30px;
                        border-radius: 4px;
                        text-decoration: none;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .cta-button:hover {{
                        background-color: #b71c1c;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>⚠️ Out of Credits!</h1>
                    </div>
                    
                    <div class="alert">
                        <h2>Your ChatVerse credits have reached zero</h2>
                        <p>Your automations are currently inactive due to insufficient credits.</p>
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>We wanted to notify you that your ChatVerse account has run out of credits. This means:</p>
                    
                    <ul>
                        <li>✗ Your automations are temporarily paused</li>
                        <li>✗ AI responses are unavailable</li>
                        <li>✗ Live chat features are disabled</li>
                    </ul>
                    
                    <p><strong>Good news:</strong> You can reactivate everything instantly by purchasing more credits!</p>
                    
                    <a href="https://app.chatverse.io/billing" class="cta-button">Buy Credits Now</a>
                    
                    <h3>Our Plans:</h3>
                    <ul>
                        <li><strong>Monthly Plan:</strong> ₹850/month for 5M tokens</li>
                        <li><strong>Pay-As-You-Go:</strong> ₹100 per 500K tokens (flexible)</li>
                    </ul>
                    
                    <p>Questions? We're here to help!</p>
                    
                    <div class="footer">
                        <p>ChatVerse - AI-Powered Automation Platform</p>
                        <p>© 2025 ChatVerse. All rights reserved.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_feedback_request_html(user_name: str) -> str:
        """Create HTML for feedback request email (10 days after signup)"""
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
                        color: white;
                        padding: 30px 20px;
                        border-radius: 8px 8px 0 0;
                        text-align: center;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                    }}
                    .question {{
                        background-color: #e3f2fd;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 15px 0;
                        border-left: 4px solid #2196F3;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background-color: #2196F3;
                        color: white;
                        padding: 12px 30px;
                        border-radius: 4px;
                        text-decoration: none;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .cta-button:hover {{
                        background-color: #1976D2;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>We'd Love Your Feedback! 💭</h1>
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>It's been 10 days since you joined ChatVerse, and we hope you're having a great experience! We'd love to hear what you think about our platform.</p>
                    
                    <div class="question">
                        <strong>How has ChatVerse been working for you?</strong>
                        <p style="margin: 10px 0 0 0;">Your feedback helps us improve and build features that matter to you.</p>
                    </div>
                    
                    <p>Tell us about:</p>
                    <ul>
                        <li>What you loved ❤️</li>
                        <li>What could be better 🔧</li>
                        <li>Features you'd like to see 🚀</li>
                        <li>Your overall experience 🌟</li>
                    </ul>
                    
                    <a href="https://app.chatverse.io/feedback" class="cta-button">Share Your Feedback</a>
                    
                    <p>Your input directly influences our roadmap and helps us serve you better. Plus, every feedback submission enters you into our monthly raffle for exclusive rewards!</p>
                    
                    <p>Thank you for being a ChatVerse user!</p>
                    
                    <div class="footer">
                        <p>ChatVerse - AI-Powered Automation Platform</p>
                        <p>© 2025 ChatVerse. All rights reserved.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    @staticmethod
    def _create_credit_purchase_html(
        user_name: str,
        credits_purchased: int,
        total_credits: int,
        amount_paid: float,
        plan_type: str
    ) -> str:
        """Create HTML for credit purchase confirmation"""
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                        color: white;
                        padding: 30px 20px;
                        border-radius: 8px 8px 0 0;
                        text-align: center;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                    }}
                    .invoice-box {{
                        background-color: white;
                        border: 1px solid #ddd;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                    .invoice-row {{
                        display: flex;
                        justify-content: space-between;
                        padding: 10px 0;
                        border-bottom: 1px solid #eee;
                    }}
                    .invoice-row:last-child {{
                        border-bottom: 2px solid #333;
                        padding: 15px 0;
                        font-weight: bold;
                        font-size: 18px;
                    }}
                    .stat-box {{
                        display: inline-block;
                        background-color: #f0f0f0;
                        padding: 15px 20px;
                        border-radius: 4px;
                        margin: 10px 5px;
                        min-width: 180px;
                    }}
                    .stat-value {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #4CAF50;
                    }}
                    .stat-label {{
                        font-size: 12px;
                        color: #666;
                        margin-top: 5px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background-color: #4CAF50;
                        color: white;
                        padding: 12px 30px;
                        border-radius: 4px;
                        text-decoration: none;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .cta-button:hover {{
                        background-color: #45a049;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✅ Purchase Confirmed!</h1>
                        <p style="margin: 10px 0 0 0;">Your credits have been added to your account</p>
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>Great news! Your credit purchase has been completed successfully. Here are the details:</p>
                    
                    <div class="invoice-box">
                        <div class="invoice-row">
                            <span>Plan Type:</span>
                            <strong>{plan_type}</strong>
                        </div>
                        <div class="invoice-row">
                            <span>Credits Purchased:</span>
                            <strong>{credits_purchased:,}</strong>
                        </div>
                        <div class="invoice-row">
                            <span>Amount Paid:</span>
                            <strong>₹{amount_paid:.2f}</strong>
                        </div>
                        <div class="invoice-row">
                            <span>Total Credits Available:</span>
                            <strong>{total_credits:,}</strong>
                        </div>
                    </div>
                    
                    <p><strong>Your Account Status:</strong></p>
                    <div class="stat-box">
                        <div class="stat-value">{total_credits:,}</div>
                        <div class="stat-label">Total Credits</div>
                    </div>
                    
                    <p>Your automations are now fully active and ready to use. You can start creating new automations or manage your existing ones from your dashboard.</p>
                    
                    <a href="https://app.chatverse.io/dashboard" class="cta-button">Go to Dashboard</a>
                    
                    <h3>Tips to Maximize Your Credits:</h3>
                    <ul>
                        <li>📊 Monitor automation usage in real-time</li>
                        <li>⚙️ Optimize automation triggers to reduce unnecessary runs</li>
                        <li>💾 Keep your knowledge base updated for better AI responses</li>
                        <li>📧 Enable low-credit alerts to never run out unexpectedly</li>
                    </ul>
                    
                    <p>Questions or need help? Our support team is always ready to assist!</p>
                    
                    
                    <div class="footer">
                        <p>ChatVerse - AI-Powered Automation Platform</p>
                        <p>Transaction Date: {datetime.now().strftime('%B %d, %Y')}</p>
                        <p>© 2025 ChatVerse. All rights reserved.</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    def send_automation_created_email(
        self,
        user_email: str,
        user_name: str,
        automation_name: str,
        automation_type: str,
        credits_per_execution: int
    ) -> bool:
        """
        Send notification email when user creates an automation.
        Informs them about credits that will be consumed per execution.
        
        Args:
            user_email: User's email
            user_name: User's name
            automation_name: Name of the automation
            automation_type: Type of automation (COMMENT_REPLY, PRIVATE_MESSAGE, etc)
            credits_per_execution: Credits consumed per automation run
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if not self.resend_api_key:
                logger.warning("Cannot send email: RESEND_API_KEY not configured")
                return False
            
            html_content = self._create_automation_created_html(
                user_name, automation_name, automation_type, credits_per_execution
            )
            
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": user_email,
                "subject": f"🤖 Automation Created: {automation_name}",
                "html": html_content
            }
            
            with httpx.Client() as client:
                response = client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"Automation creation email sent to {user_email}")
                    return True
                else:
                    logger.error(f"Resend API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending automation creation email: {str(e)}")
            return False
    
    @staticmethod
    def _create_automation_created_html(
        user_name: str,
        automation_name: str,
        automation_type: str,
        credits_per_execution: int
    ) -> str:
        """Create HTML for automation creation notification email"""
        
        # Format automation type nicely
        automation_type_display = automation_type.replace("_", " ").title()
        
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #333;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px 20px;
                        border-radius: 8px 8px 0 0;
                        text-align: center;
                        margin: -20px -20px 20px -20px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                    }}
                    .automation-info {{
                        background-color: white;
                        border: 2px solid #667eea;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                    }}
                    .info-row {{
                        display: flex;
                        justify-content: space-between;
                        padding: 12px 0;
                        border-bottom: 1px solid #eee;
                    }}
                    .info-row:last-child {{
                        border-bottom: none;
                    }}
                    .info-label {{
                        font-weight: bold;
                        color: #667eea;
                    }}
                    .info-value {{
                        text-align: right;
                        font-weight: 500;
                    }}
                    .credit-box {{
                        background-color: #f0f4ff;
                        border: 2px solid #667eea;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        text-align: center;
                    }}
                    .credit-label {{
                        color: #666;
                        font-size: 14px;
                        margin-bottom: 10px;
                    }}
                    .credit-value {{
                        font-size: 32px;
                        font-weight: bold;
                        color: #667eea;
                    }}
                    .credit-unit {{
                        font-size: 14px;
                        color: #666;
                        margin-top: 5px;
                    }}
                    .warning-box {{
                        background-color: #fff3cd;
                        border-left: 4px solid #ff9800;
                        padding: 15px;
                        border-radius: 4px;
                        margin: 20px 0;
                    }}
                    .tips {{
                        background-color: #f5f5f5;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 15px 0;
                    }}
                    .tips h4 {{
                        margin: 0 0 10px 0;
                        color: #667eea;
                    }}
                    .tips ul {{
                        margin: 0;
                        padding-left: 20px;
                    }}
                    .tips li {{
                        margin: 5px 0;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background-color: #667eea;
                        color: white;
                        padding: 12px 30px;
                        border-radius: 4px;
                        text-decoration: none;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .cta-button:hover {{
                        background-color: #764ba2;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding-top: 20px;
                        border-top: 1px solid #ddd;
                        font-size: 12px;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🤖 Automation Created!</h1>
                        <p style="margin: 10px 0 0 0;">Your new automation is live and ready to go</p>
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>Congratulations! Your new automation has been successfully created and is now active on your account.</p>
                    
                    <div class="automation-info">
                        <div class="info-row">
                            <span class="info-label">📝 Automation Name:</span>
                            <span class="info-value">{automation_name}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">⚙️ Automation Type:</span>
                            <span class="info-value">{automation_type_display}</span>
                        </div>
                    </div>
                    
                    <div class="credit-box">
                        <div class="credit-label">⚡ Credits Per Execution:</div>
                        <div class="credit-value">{credits_per_execution:,}</div>
                        <div class="credit-unit">credits deducted per run</div>
                    </div>
                    
                    <div class="warning-box">
                        <strong>💡 Pro Tip:</strong> This automation will consume <strong>{credits_per_execution:,} credits</strong> each time it runs. Make sure you have enough credits available to keep it running smoothly.
                    </div>
                    
                    <div class="tips">
                        <h4>📊 How to Monitor Your Credits:</h4>
                        <ul>
                            <li>Check your credit balance in the Dashboard anytime</li>
                            <li>You'll receive notifications when credits run low</li>
                            <li>Set up automated credit top-ups for peace of mind</li>
                            <li>View detailed usage reports for each automation</li>
                        </ul>
                    </div>
                    
                    <p><strong>Next Steps:</strong></p>
                    <ul>
                        <li>✅ Your automation is now active</li>
                        <li>✅ It will start executing based on your schedule</li>
                        <li>✅ You can monitor performance in your dashboard</li>
                        <li>✅ Credits will be deducted automatically per execution</li>
                    </ul>
                    
                    <a href="https://app.chatverse.io/automations" class="cta-button">View Your Automations</a>
                    
                    <p>Questions about credit consumption or need help optimizing your automation? Our support team is here to help!</p>
                    
                    <div class="footer">
                        <p>ChatVerse - AI-Powered Automation Platform</p>
                        <p>Created: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p>© 2025 ChatVerse. All rights reserved.</p>
                    </div>
                </div>
            </body>
        </html>
        """

# Create singleton instance
email_service = EmailService()

