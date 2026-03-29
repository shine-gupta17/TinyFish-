from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal, Optional
from supabase_client import supabase
import datetime
import razorpay
import hmac
import hashlib
import os
from utils.api_responses import APIResponse

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_SECRET:
    raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_SECRET must be set as environment variables")

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_SECRET))

router = APIRouter(
    prefix="/plans",
    tags=["plans"]
)

class CreateOrderPayload(BaseModel):
    plan_id: str
    user_id: str
    billing_cycle: Literal['monthly', 'yearly'] = 'monthly'

class PaymentCallbackPayload(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    plan_id: Optional[str] = None
    user_id: Optional[str] = None

@router.get("/")
def index():
    return JSONResponse(content={"message": "Payment API is working"})

@router.get("/billing-plans")
def get_billing_plans() -> JSONResponse:
    plans = supabase.table("plans").select("*").execute()
    if not plans.data:
        return APIResponse.error(404, "No billing plans found.")
    return APIResponse.success(plans.data)

@router.post("/create-order")
async def create_order(payload: CreateOrderPayload) -> JSONResponse:
    if not payload.user_id:
        return APIResponse.error(400, "User ID is required to create an order")

    try:
        plan_query = supabase.table("plans").select("monthly_price, yearly_price").eq("id", payload.plan_id).single().execute()
        if not plan_query.data:
            return APIResponse.error(404, f"Invalid plan ID: {payload.plan_id}")
        plan_data = plan_query.data
    except Exception as e:
        return APIResponse.error(500, f"Could not fetch plan details: {e}")

    price_to_charge = 0
    if payload.billing_cycle == 'yearly':
        price_to_charge = plan_data.get("yearly_price")
        if not price_to_charge:
            return APIResponse.error(400, f"Yearly pricing is not available for plan ID: {payload.plan_id}")
    else:
        price_to_charge = plan_data.get("monthly_price")

    if not price_to_charge or price_to_charge <= 0:
        return APIResponse.error(400, "Invalid price for the selected plan and billing cycle.")

    amount_in_paise = int(price_to_charge * 100)
    currency = 'INR'

    order_data = {
        "amount": amount_in_paise,
        "currency": currency,
        "payment_capture": 1,
        "notes": {
            "plan_id": payload.plan_id,
            "user_id": payload.user_id,
            "billing_cycle": payload.billing_cycle
        }
    }

    try:
        order = razorpay_client.order.create(data=order_data)
    except Exception as e:
        return APIResponse.error(500, f"Failed to create Razorpay order: {e}")

    return APIResponse.success({
        "status": "success",
        "razorpay_key_id": RAZORPAY_KEY_ID,
        "order_id": order['id'],
        "amount": order['amount'],
        "currency": order['currency'],
        "order": order
    })

@router.post("/payment-callback")
async def payment_callback(payload: PaymentCallbackPayload):
    try:
        message = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
        generated_signature = hmac.new(
            bytes(RAZORPAY_SECRET, 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
            return APIResponse.error(400, "Invalid payment signature")

        order_details = razorpay_client.order.fetch(payload.razorpay_order_id)
        notes = order_details.get('notes', {})
        user_id = notes.get('user_id')
        plan_id = notes.get('plan_id')
        billing_cycle = notes.get('billing_cycle', 'monthly')

        if not user_id or not plan_id:
            return APIResponse.error(400, "User ID or Plan ID missing in order notes")

        payment_record = {
            "id": payload.razorpay_payment_id,
            "order_id": payload.razorpay_order_id,
            "provider_id": user_id,
            "amount": order_details.get('amount') / 100,
            "currency": order_details.get('currency'),
            "platform": "razorpay",
            "status": "paid",
            "billing_cycle": billing_cycle,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        db_response = supabase.table("transactions").insert(payment_record).execute()
        
        if not db_response.data:
             return APIResponse.error(500, "Failed to save transaction.")

        plan_query = supabase.table("plans").select("monthly_credits, yearly_credits").eq("id", plan_id).single().execute()
        if not plan_query.data:
            return APIResponse.error(500, "Payment recorded, but could not fetch plan credits. Contact support.")

        plan_data = plan_query.data
        credits_to_add = plan_data.get('yearly_credits') if billing_cycle == 'yearly' else plan_data.get('monthly_credits')

        if credits_to_add is None:
            return APIResponse.error(400, "Credits not defined for the selected plan and billing cycle.")

        usage_query = supabase.table("billing_usage").select("current_credits").eq("provider_id", user_id).single().execute()

        current_credits = 0
        user_exists = usage_query.data is not None and usage_query.data != []
        if user_exists:
            current_credits = usage_query.data.get('current_credits', 0)
        
        new_total_credits = float(current_credits) + credits_to_add

        if user_exists:
            billing_update = supabase.table("billing_usage").update({
                "current_credits": new_total_credits,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }).eq("provider_id", user_id).execute()
        else:
            billing_update = supabase.table("billing_usage").insert({
                "provider_id": user_id,
                "current_credits": new_total_credits
            }).execute()

        if not billing_update.data:
            return APIResponse.error(500, "Payment recorded, but failed to update credit balance. Contact support.")

        return APIResponse.success(
            data={
                "payment_id": payload.razorpay_payment_id,
                "credits_added": credits_to_add,
                "new_credit_balance": new_total_credits
            },
            message="Payment successful and credits updated"
        )

    except Exception as e:
        return APIResponse.error(500, f"An unexpected error occurred: {str(e)}")