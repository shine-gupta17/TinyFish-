"""
Bulk Email Campaign: Chatverse Launch & Beta Credits Offer
Sends a professional, humanized email to all users in the database with:
- Chatverse launch announcement
- Demo video link
- Beta credits offer
- Feedback request
- Optional investor intro mention

This script uses Resend API and fetches all user emails from Supabase
"""

import asyncio
import os
import sys
import logging
from typing import List, Dict, Optional
from datetime import datetime
import httpx

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client_async import async_supabase

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class BulkEmailCampaign:
    """Manages bulk email campaigns via Resend API"""
    
    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY",)
        self.from_email = os.getenv("FROM_EMAIL", "hello@chatverse.io")
        self.resend_url = "https://api.resend.com/emails"
        
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY environment variable not set")
        
        logger.info(f"Email campaign initialized. Sending from: {self.from_email}")
    
    async def fetch_all_user_emails(self) -> List[Dict[str, str]]:
        """
        Fetch all user emails and names from Supabase
        
        Returns:
            List of dicts with email and name
        """
        try:
            logger.info("Fetching user emails from Supabase...")
            
            # Get all users with email addresses
            response = await async_supabase.select(
                "user_profiles",
                select="email,full_name",
                limit=10000  # Increase limit to fetch all users
            )
            
            if response.get("error"):
                logger.error(f"Database error: {response['error']}")
                return []
            
            users = response.get("data", [])
            
            # Filter users who have email addresses
            valid_users = [
                {
                    "email": user.get("email"),
                    "name": user.get("full_name") or "ChatVerse User"
                }
                for user in users
                if user.get("email") and "@" in user.get("email", "")
            ]
            
            logger.info(f"Found {len(valid_users)} users with valid emails")
            return valid_users
            
        except Exception as e:
            logger.error(f"Error fetching user emails: {str(e)}")
            return []
    
    def _create_email_html(self, user_name: str) -> str:
        """
        Create professional, humanized HTML email content
        
        Args:
            user_name: Name of the recipient
            
        Returns:
            HTML email content
        """
        # Extract first name for personalization
        first_name = user_name.split()[0] if user_name else "there"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #c2410c 0%, #ea580c 100%);
                    color: #ffffff;
                    padding: 40px 20px;
                    text-align: center;
                }}
                .header h1 {{
                    font-size: 32px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    letter-spacing: -0.5px;
                }}
                .header p {{
                    font-size: 16px;
                    opacity: 0.95;
                    font-weight: 300;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .greeting {{
                    font-size: 16px;
                    margin-bottom: 20px;
                    color: #333;
                }}
                .greeting strong {{
                    color: #c2410c;
                }}
                .section {{
                    margin: 25px 0;
                }}
                .section h2 {{
                    font-size: 18px;
                    color: #c2410c;
                    margin-bottom: 12px;
                    font-weight: 600;
                }}
                .highlight-box {{
                    background-color: #fff3e0;
                    border-left: 4px solid #ea580c;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .highlight-box strong {{
                    color: #c2410c;
                }}
                .button-group {{
                    margin: 25px 0;
                    text-align: center;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #c2410c 0%, #ea580c 100%);
                    color: #ffffff;
                    padding: 14px 32px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 8px;
                    transition: transform 0.2s, box-shadow 0.2s;
                    border: none;
                    cursor: pointer;
                    font-size: 14px;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(194, 65, 12, 0.3);
                }}
                .button-secondary {{
                    background: #f0f0f0;
                    color: #c2410c;
                    border: 2px solid #ea580c;
                }}
                .button-secondary:hover {{
                    background: #f5f5f5;
                }}
                .features {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin: 20px 0;
                }}
                .feature-item {{
                    padding: 15px;
                    background-color: #f9f9f9;
                    border-radius: 6px;
                    border: 1px solid #e0e0e0;
                }}
                .feature-item strong {{
                    color: #c2410c;
                    display: block;
                    margin-bottom: 5px;
                }}
                .divider {{
                    height: 1px;
                    background-color: #e0e0e0;
                    margin: 25px 0;
                }}
                .footer {{
                    background-color: #f9f9f9;
                    padding: 25px 30px;
                    text-align: center;
                    font-size: 13px;
                    color: #666;
                    border-top: 1px solid #e0e0e0;
                }}
                .footer p {{
                    margin: 8px 0;
                }}
                .signature {{
                    margin-top: 20px;
                    padding-top: 15px;
                    border-top: 1px solid #e0e0e0;
                }}
                .signature-name {{
                    font-weight: 600;
                    color: #333;
                }}
                ul {{
                    margin: 10px 0 10px 20px;
                    padding: 0;
                }}
                li {{
                    margin: 8px 0;
                    color: #555;
                }}
                .emoji {{
                    margin: 0 4px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Header -->
                <div class="header">
                    <h1>🎉 Chatverse is LIVE!</h1>
                    <p>Your AI Digital Operator is Ready to Go</p>
                </div>
                
                <!-- Main Content -->
                <div class="content">
                    <div class="greeting">
                        Hey <strong>{first_name}</strong>! 👋
                    </div>
                    
                    <p>
                        You won't believe it, but Chatverse is finally out there! The AI Digital Operator we've been building is now turning plain English into actual, complex automation across Instagram, Sheets, Notion, Gmail, and 10+ more apps.
                    </p>
                    
                    <p style="margin-top: 15px; color: #666; font-size: 14px;">
                        No more coding Zapier flowcharts. No more manual busywork. Just pure automation.
                    </p>
                    
                    <!-- What You Can Do -->
                    <div class="section">
                        <h2>What You Can Do With Chatverse</h2>
                        <div class="features">
                            <div class="feature-item">
                                <strong>✨ Create Automations</strong>
                                Just describe what you want in plain English
                            </div>
                            <div class="feature-item">
                                <strong>🔗 Connect Apps</strong>
                                Link 10+ platforms seamlessly
                            </div>
                            <div class="feature-item">
                                <strong>⚡ Save Time</strong>
                                Eliminate repetitive tasks instantly
                            </div>
                            <div class="feature-item">
                                <strong>🧠 AI-Powered</strong>
                                Intelligent automation that learns
                            </div>
                        </div>
                    </div>
                    
                    <!-- Call to Action -->
                    <div class="button-group">
                        <a href="https://chatverse.io" class="button">
                            🚀 Start Playing With It
                        </a>
                    </div>
                    
                    <!-- Demo & Links -->
                    <div class="section">
                        <h2>See It In Action</h2>
                        <p>Check out our killer demo video to see the full magic:</p>
                        <div class="button-group">
                            <a href="https://x.com/cuby575/status/1999172532268908795?s=20" class="button button-secondary">
                                👀 Watch Demo on Twitter/X
                            </a>
                        </div>
                    </div>
                    
                    <!-- Beta Credits Offer -->
                    <div class="highlight-box">
                        <strong>💝 Beta User Credits</strong><br>
                        <p style="margin-top: 10px; font-size: 14px;">
                            We're giving all beta users a solid batch of credits to crush your first automations. If you end up using them, seriously just hit me back and I'll personally hook you up with <strong>100 extra credits for free</strong>.
                        </p>
                    </div>
                    
                    <!-- Social Proof & Help -->
                    <div class="section">
                        <h2>Quick Favors We'd Appreciate 🙏</h2>
                        <ul>
                            <li><strong>Love this?</strong> Help us out with a repost/upvote on Twitter/X – it seriously means a ton</li>
                            <li><strong>Know investors?</strong> If you happen to know anyone obsessed with the AI/no-code space, I'd owe you a massive one for an intro. We're quietly fundraising right now.</li>
                            <li><strong>Got feedback?</strong> Reply to this email anytime – we love hearing from our users!</li>
                        </ul>
                    </div>
                    
                    <div class="divider"></div>
                    
                    <p style="font-size: 14px; color: #666;">
                        Thanks so much for being part of this journey, {first_name}. Let's build something amazing together.
                    </p>
                    
                    <div class="signature">
                        <p style="margin: 15px 0 5px 0;">
                            Talk soon! 🚀
                        </p>
                        <p class="signature-name">The Chatverse Team</p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div class="footer">
                    <p><strong>Chatverse</strong> • Your AI Digital Operator</p>
                    <p>
                        <a href="https://chatverse.io" style="color: #c2410c; text-decoration: none;">Website</a> • 
                        <a href="https://x.com/ChatVerse_io" style="color: #c2410c; text-decoration: none;">Twitter/X</a>
                    </p>
                    <p style="margin-top: 12px; font-size: 12px; color: #999;">
                        You're receiving this email because you signed up for Chatverse beta.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    async def send_email(self, to_email: str, user_name: str) -> bool:
        """
        Send email to a single user via Resend API
        
        Args:
            to_email: Recipient email address
            user_name: Recipient name for personalization
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": self.from_email,
                "to": to_email,
                "subject": "🎉 Chatverse is LIVE! (+ Free Beta Credits Inside)",
                "html": self._create_email_html(user_name),
                "reply_to": "hello@chatverse.io"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.resend_url, json=payload, headers=headers)
                
                if response.status_code in [200, 201]:
                    logger.info(f"✅ Email sent to {to_email}")
                    return True
                else:
                    logger.error(f"❌ Failed to send to {to_email}: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error sending email to {to_email}: {str(e)}")
            return False
    
    async def send_to_all_users(self, batch_delay: float = 0.5) -> Dict[str, int]:
        """
        Send campaign email to all users in database
        
        Args:
            batch_delay: Delay between emails in seconds (to avoid rate limiting)
            
        Returns:
            Dict with success and failure counts
        """
        users = await self.fetch_all_user_emails()
        
        if not users:
            logger.warning("No users found to send emails to")
            return {"success": 0, "failed": 0, "total": 0}
        
        total = len(users)
        success_count = 0
        failed_count = 0
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting campaign email to {total} users")
        logger.info(f"{'='*60}\n")
        
        for idx, user in enumerate(users, 1):
            email = user.get("email")
            name = user.get("name", "ChatVerse User")
            
            logger.info(f"[{idx}/{total}] Sending to {email}...")
            
            if await self.send_email(email, name):
                success_count += 1
            else:
                failed_count += 1
            
            # Add delay between emails to avoid rate limiting
            if idx < total:
                await asyncio.sleep(batch_delay)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Campaign Complete!")
        logger.info(f"✅ Successful: {success_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info(f"📊 Total: {total}")
        logger.info(f"{'='*60}\n")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": total
        }


async def main():
    """Main function to run the email campaign"""
    try:
        campaign = BulkEmailCampaign()
        results = await campaign.send_to_all_users(batch_delay=0.5)
        
        # Print summary
        print("\n" + "="*60)
        print("EMAIL CAMPAIGN SUMMARY")
        print("="*60)
        print(f"Total Sent: {results['total']}")
        print(f"Successful: {results['success']}")
        print(f"Failed: {results['failed']}")
        print(f"Success Rate: {(results['success']/results['total']*100):.1f}%" if results['total'] > 0 else "N/A")
        print("="*60 + "\n")
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
