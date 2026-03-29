from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from supabase_client_async import async_supabase
from utils.api_responses import APIResponse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


@router.get("/user/{provider_id}")
async def get_user_transactions(
    provider_id: str,
    limit: Optional[int] = Query(default=50, ge=1, le=100),
    offset: Optional[int] = Query(default=0, ge=0)
):
    """
    Get all transactions for a specific user by provider_id.
    
    Args:
        provider_id: User's provider ID
        limit: Number of records to return (default: 50, max: 100)
        offset: Number of records to skip (default: 0)
    
    Returns:
        List of transactions with pagination info
    """
    try:
        # Query transactions for the user - using correct API format
        response = await async_supabase.select(
            table="transactions",
            select="*",
            filters={"provider_id": provider_id},
            order="created_at.desc",
            limit=limit
        )
        
        if response.get("error"):
            logger.error(f"Error fetching transactions: {response['error']}")
            return APIResponse.error(
                message="Failed to fetch transactions",
                error=str(response["error"]),
                status_code=500
            )
        
        all_transactions = response.get("data") or []
        
        # Apply offset manually since the API doesn't support it directly
        transactions = all_transactions[offset:offset + limit] if offset > 0 else all_transactions[:limit]
        total_count = len(all_transactions)
        
        # Calculate summary statistics
        total_spent = sum(float(t.get("amount", 0)) for t in all_transactions if t.get("status") == "paid")
        
        return APIResponse.success(
            data={
                "transactions": transactions,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": total_count,
                    "has_more": (offset + limit) < total_count
                },
                "summary": {
                    "total_spent": round(total_spent, 2),
                    "total_transactions": len(transactions),
                    "currency": transactions[0].get("currency", "USD") if transactions else "USD"
                }
            },
            message="Transactions fetched successfully"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error fetching transactions: {str(e)}")
        return APIResponse.error(
            message="An unexpected error occurred",
            error=str(e),
            status_code=500
        )


@router.get("/user/{provider_id}/summary")
async def get_transaction_summary(provider_id: str):
    """
    Get transaction summary for a user.
    
    Args:
        provider_id: User's provider ID
    
    Returns:
        Summary of transactions including total spent, count, etc.
    """
    try:
        # Get all transactions for summary - using correct API format
        response = await async_supabase.select(
            table="transactions",
            select="*",
            filters={"provider_id": provider_id},
            order="created_at.desc"
        )
        
        if response.get("error"):
            logger.error(f"Error fetching transaction summary: {response['error']}")
            return APIResponse.error(
                message="Failed to fetch transaction summary",
                error=str(response["error"]),
                status_code=500
            )
        
        transactions = response.get("data") or []
        
        # Calculate statistics
        paid_transactions = [t for t in transactions if t.get("status") == "paid"]
        total_spent = sum(float(t.get("amount", 0)) for t in paid_transactions)
        
        # Group by billing cycle
        monthly_count = len([t for t in paid_transactions if t.get("billing_cycle") == "monthly"])
        yearly_count = len([t for t in paid_transactions if t.get("billing_cycle") == "yearly"])
        
        # Get latest transaction
        latest_transaction = transactions[0] if transactions else None
        
        return APIResponse.success(
            data={
                "total_spent": round(total_spent, 2),
                "total_transactions": len(transactions),
                "paid_transactions": len(paid_transactions),
                "monthly_subscriptions": monthly_count,
                "yearly_subscriptions": yearly_count,
                "currency": latest_transaction.get("currency", "USD") if latest_transaction else "USD",
                "latest_transaction": latest_transaction
            },
            message="Transaction summary fetched successfully"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error fetching transaction summary: {str(e)}")
        return APIResponse.error(
            message="An unexpected error occurred",
            error=str(e),
            status_code=500
        )


@router.get("/{transaction_id}")
async def get_transaction_by_id(transaction_id: str):
    """
    Get a specific transaction by ID.
    
    Args:
        transaction_id: Transaction ID
    
    Returns:
        Transaction details
    """
    try:
        response = await async_supabase.select(
            table="transactions",
            select="*",
            filters={"id": transaction_id}
        )
        
        if response.get("error"):
            logger.error(f"Error fetching transaction: {response['error']}")
            return APIResponse.error(
                message="Failed to fetch transaction",
                error=str(response["error"]),
                status_code=500
            )
        
        if not response.get("data"):
            return APIResponse.error(
                message="Transaction not found",
                status_code=404
            )
        
        return APIResponse.success(
            data=response["data"][0],
            message="Transaction fetched successfully"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error fetching transaction: {str(e)}")
        return APIResponse.error(
            message="An unexpected error occurred",
            error=str(e),
            status_code=500
        )
