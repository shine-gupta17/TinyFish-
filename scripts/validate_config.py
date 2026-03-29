#!/usr/bin/env python3
"""
Credential and Configuration Validation Script

This script validates that all required OAuth credentials and environment
variables are properly configured for the ChatVerse Backend.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path to import project modules
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from config.oauth_config import validate_credential_files, get_credential_file, get_platform_scopes
    from config.env_config import (
        INSTAGRAM_CLIENT_ID,
        INSTAGRAM_CLIENT_SECRET,
        INSTAGRAM_REDIRECT_URI,
        FRONTEND_PLATFORM_URL,
        BACKEND_URL,
        SUPABASE_URL,
        SUPABASE_KEY
    )
except ImportError as e:
    print(f"❌ Error importing config modules: {e}")
    print("   Make sure you're running this from the ChatVerse-Backend-Dev directory")
    sys.exit(1)


def check_env_variables() -> Tuple[bool, List[str]]:
    """Check if all required environment variables are set"""
    print("\n" + "="*60)
    print("🔍 Checking Environment Variables")
    print("="*60)
    
    required_vars = {
        "INSTAGRAM_CLIENT_ID": INSTAGRAM_CLIENT_ID,
        "INSTAGRAM_CLIENT_SECRET": INSTAGRAM_CLIENT_SECRET,
        "INSTAGRAM_REDIRECT_URI": INSTAGRAM_REDIRECT_URI,
        "FRONTEND_PLATFORM_URL": FRONTEND_PLATFORM_URL,
        "BACKEND_URL": BACKEND_URL,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }
    
    missing = []
    all_ok = True
    
    for var_name, var_value in required_vars.items():
        if var_value and var_value != "":
            print(f"✅ {var_name}: Set")
        else:
            print(f"❌ {var_name}: Missing")
            missing.append(var_name)
            all_ok = False
    
    return all_ok, missing


def check_credential_files() -> Tuple[bool, List[str]]:
    """Check if all OAuth credential files exist"""
    print("\n" + "="*60)
    print("🔍 Checking OAuth Credential Files")
    print("="*60)
    
    platforms = ["gmail", "google_sheets", "google_forms", "google_docs", "youtube"]
    missing = []
    all_ok = True
    
    for platform in platforms:
        cred_file = get_credential_file(platform)
        if os.path.exists(cred_file):
            # Validate JSON structure
            try:
                with open(cred_file, 'r') as f:
                    data = json.load(f)
                    if "web" in data or "installed" in data:
                        print(f"✅ {platform.replace('_', ' ').title()}: {cred_file}")
                    else:
                        print(f"⚠️  {platform.replace('_', ' ').title()}: Invalid format")
                        all_ok = False
            except json.JSONDecodeError:
                print(f"❌ {platform.replace('_', ' ').title()}: Invalid JSON")
                missing.append(platform)
                all_ok = False
        else:
            print(f"❌ {platform.replace('_', ' ').title()}: Not found at {cred_file}")
            missing.append(platform)
            all_ok = False
    
    return all_ok, missing


def check_scopes_configuration() -> bool:
    """Check if scopes are properly configured for each platform"""
    print("\n" + "="*60)
    print("🔍 Checking OAuth Scopes Configuration")
    print("="*60)
    
    platforms = ["gmail", "google_sheets", "google_forms", "google_docs", "youtube", "instagram"]
    all_ok = True
    
    for platform in platforms:
        scopes = get_platform_scopes(platform)
        if scopes:
            print(f"✅ {platform.replace('_', ' ').title()}: {len(scopes)} scope(s)")
            for scope in scopes:
                print(f"   • {scope}")
        else:
            print(f"❌ {platform.replace('_', ' ').title()}: No scopes defined")
            all_ok = False
    
    return all_ok


def check_gitignore() -> bool:
    """Check if .gitignore properly excludes credential files"""
    print("\n" + "="*60)
    print("🔍 Checking .gitignore Configuration")
    print("="*60)
    
    gitignore_path = Path(__file__).parent / ".gitignore"
    
    if not gitignore_path.exists():
        print("❌ .gitignore not found")
        return False
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    required_patterns = [
        "credentials/*.json",
        "gmail.json",
        "*.json"
    ]
    
    found = []
    for pattern in required_patterns:
        if pattern in content or "credentials/*.json" in content:
            found.append(pattern)
    
    if found:
        print(f"✅ Credential files excluded from git")
        print(f"   Found patterns: {', '.join(found)}")
        return True
    else:
        print("⚠️  Credential files may not be excluded from git")
        print("   Add 'credentials/*.json' to .gitignore")
        return False


def check_directory_structure() -> bool:
    """Check if the credentials directory structure is correct"""
    print("\n" + "="*60)
    print("🔍 Checking Directory Structure")
    print("="*60)
    
    base_dir = Path(__file__).parent
    required_dirs = [
        "credentials",
        "config",
        "routers",
        "routers/gmail",
        "routers/google_sheets",
        "routers/google_forms",
        "routers/gdoc",
        "routers/youtube",
        "instagram_routers",
    ]
    
    all_ok = True
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"✅ {dir_path}/")
        else:
            print(f"❌ {dir_path}/ - Not found")
            all_ok = False
    
    return all_ok


def main():
    """Run all validation checks"""
    print("\n" + "="*60)
    print("🚀 ChatVerse Backend Configuration Validator")
    print("="*60)
    
    # Track overall status
    all_checks_passed = True
    
    # Check environment variables
    env_ok, missing_env = check_env_variables()
    if not env_ok:
        all_checks_passed = False
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_env)}")
    
    # Check credential files
    creds_ok, missing_creds = check_credential_files()
    if not creds_ok:
        all_checks_passed = False
        print(f"\n⚠️  Missing credential files: {', '.join(missing_creds)}")
    
    # Check scopes
    scopes_ok = check_scopes_configuration()
    if not scopes_ok:
        all_checks_passed = False
    
    # Check .gitignore
    gitignore_ok = check_gitignore()
    if not gitignore_ok:
        all_checks_passed = False
    
    # Check directory structure
    dirs_ok = check_directory_structure()
    if not dirs_ok:
        all_checks_passed = False
    
    # Final summary
    print("\n" + "="*60)
    print("📊 Validation Summary")
    print("="*60)
    
    if all_checks_passed:
        print("✅ All checks passed! Your configuration is ready.")
        print("\nNext steps:")
        print("   1. Test each OAuth flow")
        print("   2. Check database connection")
        print("   3. Start the application: uvicorn app:app --reload")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nFor help, see:")
        print("   • OAUTH_SETUP.md - OAuth configuration guide")
        print("   • README.md - General setup instructions")
        return 1


if __name__ == "__main__":
    sys.exit(main())
