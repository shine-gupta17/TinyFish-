#!/usr/bin/env python3
"""
Production Readiness Validation Script
Tests all critical components before deployment
"""
import asyncio
import sys
import os
from typing import List, Tuple

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class ProductionValidator:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def print_header(self, text: str):
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}{text:^60}{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
    
    def print_success(self, text: str):
        print(f"{GREEN}✓{RESET} {text}")
        self.passed += 1
    
    def print_error(self, text: str):
        print(f"{RED}✗{RESET} {text}")
        self.failed += 1
    
    def print_warning(self, text: str):
        print(f"{YELLOW}⚠{RESET} {text}")
        self.warnings += 1
    
    def print_summary(self):
        total = self.passed + self.failed
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}{'VALIDATION SUMMARY':^60}{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"{GREEN}Passed:{RESET}   {self.passed}/{total}")
        print(f"{RED}Failed:{RESET}   {self.failed}/{total}")
        print(f"{YELLOW}Warnings:{RESET} {self.warnings}")
        
        if self.failed == 0:
            print(f"\n{GREEN}🚀 Ready for production deployment!{RESET}")
            return True
        else:
            print(f"\n{RED}❌ Fix errors before deploying to production{RESET}")
            return False


async def validate_environment_variables() -> Tuple[bool, List[str]]:
    """Check if all required environment variables are set"""
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "BACKEND_URL",
        "FRONTEND_PLATFORM_URL",
        "SECRET_KEY"
    ]
    
    recommended_vars = [
        "ENVIRONMENT",
        "WORKERS",
        "REDIS_URL",
        "RATE_LIMIT_ENABLED",
        "CORS_ORIGINS"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    missing_recommended = []
    for var in recommended_vars:
        if not os.getenv(var):
            missing_recommended.append(var)
    
    return len(missing) == 0, missing, missing_recommended


async def validate_database_connection():
    """Test database connectivity"""
    try:
        from core.database import get_async_supabase
        db = await get_async_supabase()
        
        # Try a simple query
        result = await db.execute_query(
            table="user_profiles",
            operation="select",
            select="provider_id",
            filters={"provider_id": "test_validation"}
        )
        
        return result["error"] is None or "not found" in str(result["error"]).lower()
    except Exception as e:
        return False, str(e)


async def validate_imports():
    """Check if all required modules can be imported"""
    modules = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "supabase",
        "httpx",
        "redis",
        "groq",
        "openai",
        "google.oauth2",
    ]
    
    failed_imports = []
    for module in modules:
        try:
            __import__(module)
        except ImportError:
            failed_imports.append(module)
    
    return len(failed_imports) == 0, failed_imports


async def validate_directory_structure():
    """Check if required directories and files exist"""
    required_paths = [
        "core/",
        "core/database.py",
        "core/cache.py",
        "core/rate_limiter.py",
        "config/",
        "config/settings.py",
        "config/env_config.py",
        "config/oauth_config.py",
        "routers/",
        "instagram_routers/",
        "models/",
        "utils/",
        "credentials/",
        "app_production.py",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml"
    ]
    
    missing = []
    for path in required_paths:
        if not os.path.exists(path):
            missing.append(path)
    
    return len(missing) == 0, missing


async def validate_credential_files():
    """Check if OAuth credential files exist"""
    credential_files = [
        "credentials/gmail.json",
        "credentials/google_sheets.json",
        "credentials/google_forms.json",
        "credentials/google_docs.json",
        "credentials/youtube.json"
    ]
    
    missing = []
    for file in credential_files:
        if not os.path.exists(file):
            missing.append(file)
    
    return len(missing) == 0, missing


async def validate_security_settings():
    """Check security configuration"""
    issues = []
    
    # Check SECRET_KEY
    secret_key = os.getenv("SECRET_KEY", "")
    if len(secret_key) < 32:
        issues.append("SECRET_KEY is too short (minimum 32 characters)")
    if secret_key == "super-secret-session-key":
        issues.append("SECRET_KEY is using default value (SECURITY RISK!)")
    
    # Check ENVIRONMENT
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        # Check DEBUG is disabled
        debug = os.getenv("DEBUG", "False").lower()
        if debug == "true":
            issues.append("DEBUG should be False in production")
    
    # Check CORS
    cors = os.getenv("CORS_ORIGINS", "")
    if "*" in cors:
        issues.append("CORS allows all origins (*) - security risk!")
    
    return len(issues) == 0, issues


async def validate_app_startup():
    """Test if the application can start"""
    try:
        # Try importing the app
        from app_production import app
        return True, None
    except Exception as e:
        return False, str(e)


async def main():
    validator = ProductionValidator()
    
    validator.print_header("PRODUCTION READINESS VALIDATION")
    
    # 1. Environment Variables
    validator.print_header("1. Environment Variables")
    passed, missing, missing_recommended = await validate_environment_variables()
    
    if passed:
        validator.print_success("All required environment variables are set")
    else:
        validator.print_error(f"Missing required variables: {', '.join(missing)}")
    
    if missing_recommended:
        validator.print_warning(f"Missing recommended variables: {', '.join(missing_recommended)}")
    
    # 2. Python Modules
    validator.print_header("2. Python Dependencies")
    passed, failed = await validate_imports()
    
    if passed:
        validator.print_success("All required Python modules are installed")
    else:
        validator.print_error(f"Missing modules: {', '.join(failed)}")
        validator.print_warning("Run: pip install -r requirements.txt")
    
    # 3. Directory Structure
    validator.print_header("3. Directory Structure")
    passed, missing = await validate_directory_structure()
    
    if passed:
        validator.print_success("All required directories and files exist")
    else:
        validator.print_error(f"Missing paths: {', '.join(missing)}")
    
    # 4. Credential Files
    validator.print_header("4. OAuth Credentials")
    passed, missing = await validate_credential_files()
    
    if passed:
        validator.print_success("All OAuth credential files exist")
    else:
        validator.print_warning(f"Missing credential files: {', '.join(missing)}")
        validator.print_warning("These are needed for OAuth features")
    
    # 5. Security Settings
    validator.print_header("5. Security Configuration")
    passed, issues = await validate_security_settings()
    
    if passed:
        validator.print_success("Security configuration looks good")
    else:
        for issue in issues:
            validator.print_error(issue)
    
    # 6. Database Connection
    validator.print_header("6. Database Connectivity")
    try:
        result = await validate_database_connection()
        if isinstance(result, tuple):
            passed, error = result
        else:
            passed = result
            error = None
        
        if passed:
            validator.print_success("Database connection successful")
        else:
            validator.print_error(f"Database connection failed: {error}")
    except Exception as e:
        validator.print_error(f"Database validation error: {str(e)}")
    
    # 7. App Startup
    validator.print_header("7. Application Startup")
    passed, error = await validate_app_startup()
    
    if passed:
        validator.print_success("Application can be imported successfully")
    else:
        validator.print_error(f"Application import failed: {error}")
    
    # Summary
    is_ready = validator.print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if is_ready else 1)


if __name__ == "__main__":
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.join(script_dir, ".."))
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run validation
    asyncio.run(main())
