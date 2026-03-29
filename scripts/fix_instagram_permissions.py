#!/usr/bin/env python3
"""
Script to diagnose and fix Instagram webhook subscription issues.
Run this to check if your Instagram account is properly subscribed to webhooks.
"""

import asyncio
import sys
import os
import httpx

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram_routers.insta_utils import get_access_token

async def check_and_fix_subscriptions(platform_user_id: str):
    """Check and fix webhook subscriptions for an Instagram account"""
    
    print(f"\n🔍 Checking webhook subscriptions for Instagram Account: {platform_user_id}\n")
    
    try:
        # Get access token
        access_token, puid = await get_access_token(platform_user_id=platform_user_id)
        print(f"✓ Access token retrieved")
        print(f"✓ Instagram Business Account ID: {puid}\n")
        
        # Check current subscription status
        check_url = f"https://graph.instagram.com/v23.0/{puid}/subscribed_apps"
        params = {"access_token": access_token}
        
        async with httpx.AsyncClient() as client:
            print("📋 Checking current subscription status...")
            response = await client.get(check_url, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}\n")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    current_fields = data["data"][0].get("subscribed_fields", [])
                    print(f"✓ Currently subscribed to: {current_fields}\n")
                else:
                    print("⚠️  No active subscriptions found\n")
            
            # Subscribe to all required fields
            print("🔧 Subscribing to webhook fields...")
            
            # All possible Instagram webhook fields
            all_fields = [
                "messages",
                "messaging_postbacks", 
                "comments",
                "mentions",
                "message_echoes",
                "message_reactions",
                "story_insights"
            ]
            
            subscribe_url = f"https://graph.instagram.com/v23.0/{puid}/subscribed_apps"
            subscribe_params = {
                "subscribed_fields": ",".join(all_fields),
                "access_token": access_token
            }
            
            subscribe_response = await client.post(subscribe_url, params=subscribe_params)
            print(f"Subscription Status: {subscribe_response.status_code}")
            print(f"Subscription Response: {subscribe_response.text}\n")
            
            if subscribe_response.status_code == 200:
                print(f"✅ Successfully subscribed to: {', '.join(all_fields)}\n")
            else:
                print(f"❌ Failed to subscribe. Error: {subscribe_response.text}\n")
                
                # Check if it's a permission error
                if "permission" in subscribe_response.text.lower():
                    print("⚠️  PERMISSION ERROR DETECTED\n")
                    print("This usually means:")
                    print("1. The Meta App doesn't have 'instagram_manage_messages' permission approved")
                    print("2. The app needs to go through App Review for advanced permissions")
                    print("3. The Instagram account type might not support this feature\n")
                    print("📝 Next Steps:")
                    print("   a. Go to Meta App Dashboard: https://developers.facebook.com/apps")
                    print("   b. Select your app")
                    print("   c. Go to 'App Review' > 'Permissions and Features'")
                    print("   d. Request 'instagram_manage_messages' permission")
                    print("   e. Make sure your app is in 'Live' mode (not Development)\n")
            
            # Verify subscription again
            print("🔄 Verifying final subscription status...")
            verify_response = await client.get(check_url, params=params)
            if verify_response.status_code == 200:
                verify_data = verify_response.json()
                if verify_data.get("data"):
                    final_fields = verify_data["data"][0].get("subscribed_fields", [])
                    print(f"✓ Final subscribed fields: {final_fields}\n")
                    
                    # Check for missing critical fields
                    critical_fields = ["messages", "comments"]
                    missing = [f for f in critical_fields if f not in final_fields]
                    if missing:
                        print(f"⚠️  Warning: Missing critical fields: {missing}")
                        print("   These fields are required for DM and comment automation to work\n")
                    else:
                        print("✅ All critical fields are subscribed!\n")
    
    except Exception as e:
        print(f"❌ Error: {e}\n")
        import traceback
        traceback.print_exc()

async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python fix_instagram_permissions.py <platform_user_id>")
        print("\nExample: python fix_instagram_permissions.py 17841475611988088")
        sys.exit(1)
    
    platform_user_id = sys.argv[1]
    await check_and_fix_subscriptions(platform_user_id)
    
    print("\n" + "="*80)
    print("IMPORTANT NOTES:")
    print("="*80)
    print("""
1. WEBHOOK CONFIGURATION (Meta App Dashboard):
   - Go to your Meta App Dashboard
   - Navigate to Products > Webhooks
   - Subscribe to Instagram webhook
   - Make sure these fields are checked:
     ✓ messages
     ✓ messaging_postbacks
     ✓ comments
     ✓ mentions

2. APP PERMISSIONS:
   - Your app must have 'instagram_manage_messages' permission
   - For production: Submit for App Review if not already approved
   - For testing: Make sure test users are added

3. INSTAGRAM ACCOUNT TYPE:
   - Must be an Instagram Business or Creator account
   - Must be connected to a Facebook Page
   - Personal Instagram accounts won't work

4. COMMON 403 ERRORS:
   - App not in Live mode (still in Development mode)
   - Missing instagram_manage_messages permission
   - Account not properly connected to Facebook Page
   - Trying to message users who haven't messaged you first
   - Comment-to-DM might have 24-hour window restriction

5. TESTING:
   - Use Instagram's test mode for development
   - Add test users in Meta App Dashboard > Roles > Test Users
   - Test with accounts that have messaged your business account first
    """)

if __name__ == "__main__":
    asyncio.run(main())
