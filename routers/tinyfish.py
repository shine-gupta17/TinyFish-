from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.tinyfish_client import tinyfish_client


router = APIRouter(prefix="/tinyfish", tags=["TinyFish"])


class TinyFishTaskRequest(BaseModel):
    url: Optional[str] = Field(default=None, description="URL where the automation should run")
    goal: Optional[str] = Field(default=None, min_length=5, description="Goal for TinyFish automation")
    task: Optional[str] = Field(default=None, min_length=5, description="Backward-compatible alias for goal")
    start_url: Optional[str] = Field(default=None, description="Backward-compatible alias for url")
    session_id: Optional[str] = Field(default=None, description="Optional TinyFish session identifier")
    max_steps: Optional[int] = Field(default=20, ge=1, le=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


@router.get("/health")
async def tinyfish_health() -> Dict[str, Any]:
    return {
        "configured": tinyfish_client.is_configured,
        "base_url": tinyfish_client.base_url,
        "execute_path": tinyfish_client.execute_path,
    }


@router.post("/run")
async def run_tinyfish_task(body: TinyFishTaskRequest) -> Dict[str, Any]:
    if not tinyfish_client.is_configured:
        raise HTTPException(status_code=500, detail="TinyFish is not configured. Set TINYFISH_API_KEY.")

    target_url = body.url or body.start_url
    target_goal = body.goal or body.task

    if not target_url or not target_goal:
        raise HTTPException(status_code=422, detail="Both url and goal are required.")

    payload: Dict[str, Any] = {
        "url": target_url,
        "goal": target_goal,
    }

    if body.max_steps is not None:
        payload["max_steps"] = body.max_steps
    if body.session_id:
        payload["session_id"] = body.session_id
    if body.metadata:
        payload["metadata"] = body.metadata

    result = await tinyfish_client.execute_web_task(payload)

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "TinyFish request failed",
                "tinyfish_status_code": result.get("status_code"),
                "error": result.get("error"),
            },
        )

    return {
        "success": True,
        "message": "TinyFish task submitted",
        "tinyfish": result,
    }
