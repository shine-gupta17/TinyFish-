from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from supabase_client_async import async_supabase
from models.api_models import UserProfile, CreateUserProfilePayload
from utils.api_responses import APIResponse
from services.email_triggers import EmailTriggerByProvider
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["User Profiles"]
)

async def insert_with_billing(profile_data: dict):
    """
    Insert into user_profiles and initialize billing_usage asynchronously.
    """
    # Insert user profile
    response = await async_supabase.insert("user_profiles", profile_data)

    if response["error"]:
        # Check if it's a duplicate key error (409)
        if response.get("status_code") == 409 or "23505" in str(response["error"]):
            logger.warning(f"Duplicate user profile detected: {response['error']}")
            # Raise exception to be handled by caller
            raise Exception(f"Duplicate user profile: {response['error']}")
        else:
            logger.error(f"Error inserting user profile: {response['error']}")
            return None

    if not response["data"]:
        logger.error("No data returned after inserting user profile")
        return None

    provider_id = response["data"][0]["provider_id"]

    # Initialize billing usage row for the new user
    billing_data = {
        "provider_id": provider_id,
        "chat_token": 0,
        "chat_cost": 0.0,
        "current_credits": 20000,
        "platform_automation_count": 0,
        "platform_automation_token": 0
    }
    
    billing_response = await async_supabase.insert("billing_usage", billing_data)
    
    if billing_response["error"]:
        logger.error(f"Error inserting billing data: {billing_response['error']}")
        # Don't fail the whole operation if billing insert fails
        # The user profile is already created

    return response["data"][0]


# ---------------- CREDIT ROUTES ----------------

@router.post("/add-credit")
async def add_credit(provider_id: str = Body(...), amount: float = Body(...)) -> JSONResponse:
    """
    Add credits to a user's account (recharge).
    Increments current_credits (acts as wallet balance).
    """
    # try:
    # Get existing balance
    existing = await async_supabase.select(
        "billing_usage",
        select="current_credits",
        filters={"provider_id": provider_id},
        limit=1
    )

    if not existing["data"] or existing["error"]:
        return APIResponse.error(404, "User billing record not found.")

    new_balance = float(existing["data"][0]["current_credits"]) + amount

    # Update balance
    response = await async_supabase.update(
        "billing_usage",
        {"current_credits": new_balance},
        {"provider_id": provider_id}
    )

    if response["error"]:
        return APIResponse.error(500, response["error"])

    return APIResponse.success(
        data=response["data"][0],
        message=f"Added {amount} credits successfully"
    )
    # except Exception as e:
    #     import traceback
    #     print(f"ERROR in add_credit: {str(e)}")
    #     print(f"Traceback: {traceback.format_exc()}")
    #     return APIResponse.error(500, str(e))


@router.get("/get-credit/{provider_id}")
async def get_credit(provider_id: str) -> JSONResponse:
    """
    Fetch available credits (current_credits).
    """
    # try:
    response = await async_supabase.select(
        "billing_usage",
        select="current_credits",
        filters={"provider_id": provider_id},
        limit=1
    )

    if not response["data"] or response["error"]:
        return APIResponse.error(404, "User billing record not found.")

    return APIResponse.success(
        data=response["data"][0],
        message="Credit balance fetched successfully"
    )
    # except Exception as e:
    #     import traceback
    #     print(f"ERROR in get_credit: {str(e)}")
    #     print(f"Traceback: {traceback.format_exc()}")
    #     print(f"Response data: {response if 'response' in locals() else 'No response'}")
    #     return APIResponse.error(500, str(e))

# --- Routes ---
@router.post("/profile", status_code=201)
async def create_user_profile(payload: UserProfile) -> JSONResponse:
    try:
        # Check if user already exists by provider_id first (primary key)
        if payload.provider_id:
            existing_by_provider = await async_supabase.select(
                "user_profiles",
                select="*",
                filters={"provider_id": payload.provider_id}
            )
            if existing_by_provider["data"] and len(existing_by_provider["data"]) > 0:
                logger.info(f"User already exists with provider_id: {payload.provider_id}")
                # User already exists, return existing profile
                return APIResponse.success(
                    data=existing_by_provider["data"][0],
                    message="User profile already exists"
                )
        
        # Check if user already exists by email
        if payload.email:
            existing_by_email = await async_supabase.select(
                "user_profiles",
                select="*",
                filters={"email": payload.email}
            )
            if existing_by_email["data"] and len(existing_by_email["data"]) > 0:
                logger.info(f"User already exists with email: {payload.email}")
                # User already exists, return existing profile
                return APIResponse.success(
                    data=existing_by_email["data"][0],
                    message="User profile already exists"
                )
        
        if payload.username:
            existing_by_username = await async_supabase.select(
                "user_profiles",
                select="*",
                filters={"username": payload.username}
            )
            if existing_by_username["data"] and len(existing_by_username["data"]) > 0:
                logger.info(f"User already exists with username: {payload.username}")
                # User already exists, return existing profile
                return APIResponse.success(
                    data=existing_by_username["data"][0],
                    message="User profile already exists"
                )
        
        # No existing user found, create new profile
        profile_data = payload.model_dump()
        result = await insert_with_billing(profile_data)

        if not result:
            logger.error("Failed to create user profile")
            return APIResponse.error(500, "Failed to create user profile")

        logger.info(f"User profile created successfully for {payload.email or payload.username}")

        # Send welcome email after successful user creation
        try:
            if payload.provider_id:
                logger.info(f"Attempting to send welcome email to provider_id: {payload.provider_id}")
                await EmailTriggerByProvider.send_welcome_email_by_provider(payload.provider_id)
            else:
                logger.warning(f"No provider_id available to send welcome email")
        except Exception as email_error:
            # Log email error but don't fail the registration
            logger.error(f"Failed to send welcome email: {str(email_error)}")

        return APIResponse.success(
            data=result,
            message="User profile created successfully"
        )

    except Exception as e:
        logger.error(f"Error in create_user_profile: {str(e)}")
        # Check if it's a unique violation (409 conflict)
        if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
            # If duplicate, try to fetch and return existing profile
            if payload.provider_id:
                existing = await async_supabase.select(
                    "user_profiles",
                    select="*",
                    filters={"provider_id": payload.provider_id}
                )
                if existing["data"]:
                    return APIResponse.success(
                        data=existing["data"][0],
                        message="User profile already exists"
                    )
            return APIResponse.error(409, "User profile already exists.")
        return APIResponse.error(500, str(e))


@router.post("/profile/custom", status_code=201)
async def create_custom_user_profile(payload: CreateUserProfilePayload) -> JSONResponse:
    try:
        # Check if profile exists
        existing_profile = await async_supabase.select(
            "user_profiles",
            select="*",
            filters={"provider_id": payload.provider_id}
        )
        
        if existing_profile["data"] and len(existing_profile["data"]) > 0:
            logger.info(f"Custom user profile already exists for provider_id: {payload.provider_id}")
            return APIResponse.success(
                data=existing_profile["data"][0],
                message="User profile already exists"
            )

        # Derive username
        base_username = payload.email.split("@")[0] if payload.email else "user"
        username = f"{base_username}_{payload.provider_id[:6]}"

        profile_data = payload.model_dump()
        profile_data.update({
            "username": username,
            "auth_provider": "custom"
        })

        result = await insert_with_billing(profile_data)

        if not result:
            logger.error("Failed to create custom user profile")
            return APIResponse.error(500, "Failed to create custom user profile.")

        logger.info(f"Custom user profile created successfully for {payload.email}")

        # Send welcome email after successful user creation
        try:
            logger.info(f"Attempting to send welcome email to provider_id: {payload.provider_id}")
            await EmailTriggerByProvider.send_welcome_email_by_provider(payload.provider_id)
        except Exception as email_error:
            # Log email error but don't fail the registration
            logger.error(f"Failed to send welcome email: {str(email_error)}")

        return APIResponse.success(
            data=result,
            message="Custom user profile created successfully"
        )

    except Exception as e:
        import traceback
        logger.error(f"ERROR in create_custom_user_profile: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
            # If duplicate, try to fetch and return existing profile
            existing = await async_supabase.select(
                "user_profiles",
                select="*",
                filters={"provider_id": payload.provider_id}
            )
            if existing["data"]:
                return APIResponse.success(
                    data=existing["data"][0],
                    message="User profile already exists"
                )
            return APIResponse.error(409, "User profile already exists.")
        return APIResponse.error(500, str(e))
    
@router.get("/profile/{provider_id}")
async def get_user_profile(provider_id: str) -> JSONResponse:
    # try:
    response = await async_supabase.select(
        "user_profiles",
        select="*",
        filters={"provider_id": provider_id},
        limit=1
    )

    if not response["data"] or response["error"]:
        return APIResponse.error(404, "User profile not found.")

    return APIResponse.success(
        data=response["data"][0],
        message="User profile fetched successfully"
    )
    # except Exception as e:
    #     import traceback
    #     print(f"ERROR in get_user_profile: {str(e)}")
    #     print(f"Traceback: {traceback.format_exc()}")
    #     return APIResponse.error(500, str(e))

@router.get("/profile/{provider_id}/connected-accounts")
async def get_user_connected_accounts(provider_id: str) -> JSONResponse:
    try:
        response = await async_supabase.select(
            "connected_accounts",
            select="*",
            filters={"provider_id": provider_id}
        )

        return APIResponse.success(
            data=response["data"] or [],
            message="Connected accounts fetched successfully"
        )
    except Exception as e:
        import traceback
        print(f"ERROR in get_user_connected_accounts: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return APIResponse.error(500, str(e))

@router.delete("/profile/connected-accounts/{account_id}")
async def disconnect_platform_account(account_id: int) -> JSONResponse:
    """
    Disconnect a platform account by deleting it from connected_accounts table.
    """
    try:
        # First check if the account exists
        existing = await async_supabase.select(
            "connected_accounts",
            select="id, platform, platform_username",
            filters={"id": account_id}
        )

        if not existing["data"] or existing["error"]:
            return APIResponse.error(404, "Connected account not found.")

        account_info = existing["data"][0]
        
        # Delete the account
        response = await async_supabase.delete(
            "connected_accounts",
            {"id": account_id}
        )

        if response["data"]:
            return APIResponse.success(
                data={"account_id": account_id},
                message=f"Successfully disconnected {account_info['platform']} account (@{account_info['platform_username']})"
            )
        else:
            return APIResponse.error(500, "Failed to disconnect account.")

    except Exception as e:
        import traceback
        print(f"ERROR in disconnect_platform_account: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return APIResponse.error(500, str(e))

@router.patch("/profile/{provider_id}")
async def update_user_profile(provider_id: str, payload: UserProfile) -> JSONResponse:
    # try:
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return APIResponse.error(400, "No update data provided.")

        response = await async_supabase.update(
            "user_profiles",
            update_data,
            {"provider_id": provider_id}
        )

        if not response["data"] or response["error"]:
            return APIResponse.error(404, "Failed to update profile. User not found.")
            
        return APIResponse.success(
            data=response["data"][0],
            message="User profile updated successfully"
        )
    # except Exception as e:
    #     import traceback
    #     print(f"ERROR in update_user_profile: {str(e)}")
    #     print(f"Traceback: {traceback.format_exc()}")
    #     return APIResponse.error(500, str(e))