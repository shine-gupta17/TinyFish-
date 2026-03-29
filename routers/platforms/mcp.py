"""
MCP Platform Router
Handles MCP server registration and management
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

from supabase_client_async import async_supabase

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/platforms/mcp",
    tags=["MCP Platforms"]
)


# Helper to clear graph cache when MCP agents change
def clear_user_graph_cache(provider_id: str):
    """Clear the graph builder cache for a user when their MCP agents change"""
    try:
        import sys
        import os
        # Add AI development path to import chatagent modules
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from chatagent.graph_builder import clear_graph_cache
        clear_graph_cache(provider_id)
    except ImportError:
        # If chatagent is not available (backend-only mode), skip cache clearing
        logger.warning("Could not import chatagent.graph_builder - cache clearing skipped")
    except Exception as e:
        logger.error(f"Error clearing graph cache: {e}")


# Request/Response Models
class MCPPlatformCreate(BaseModel):
    """Request model for creating a new MCP platform"""
    agent_name: str = Field(..., description="Unique name for the MCP agent", min_length=3, max_length=100)
    server_url: str = Field(..., description="MCP server URL (e.g., http://localhost:8002/sse)")
    description: str = Field(..., description="Description of what this MCP agent does", min_length=10)
    metadata: Optional[dict] = Field(default={}, description="Additional metadata (prompt, config, etc.)")
    headers: Optional[dict] = Field(default={}, description="HTTP headers for authentication (e.g., Authorization, x-api-key)")


class MCPPlatformUpdate(BaseModel):
    """Request model for updating an MCP platform"""
    server_url: Optional[str] = Field(None, description="MCP server URL")
    description: Optional[str] = Field(None, description="Description of the MCP agent")
    status: Optional[str] = Field(None, description="Status: active, inactive, error")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    headers: Optional[dict] = Field(None, description="HTTP headers for authentication")


class MCPPlatformResponse(BaseModel):
    """Response model for MCP platform"""
    id: int
    provider_id: str
    agent_name: str
    server_url: str
    description: str
    status: str
    metadata: dict
    headers: dict
    tools_cache: List[dict]
    last_synced: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@router.post("/register", response_model=dict)
async def register_mcp_platform(
    payload: MCPPlatformCreate,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Register a new MCP server as a platform agent.
    
    This endpoint:
    1. Validates the MCP server URL
    2. Stores the configuration in the database
    3. Returns the registered agent details
    
    The MCP agent will be available for chat operations immediately.
    """
    try:
        db = await async_supabase.get_instance()
        
        # Check if agent name already exists for this user
        existing = await db.select(
            "mcp_agents",
            select="*",
            filters={
                "provider_id": provider_id,
                "agent_name": payload.agent_name
            }
        )
        
        if existing.get("data") and len(existing["data"]) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"MCP agent '{payload.agent_name}' already exists for this user"
            )
        
        # Create the MCP agent record
        insert_data = {
            "provider_id": provider_id,
            "agent_name": payload.agent_name,
            "server_url": payload.server_url,
            "description": payload.description,
            "status": "active",
            "metadata": payload.metadata or {},
            "headers": payload.headers or {},
            "tools_cache": [],
            "last_synced": None
        }
        
        result = await db.insert("mcp_agents", insert_data)
        
        if result.get("error"):
            logger.error(f"Failed to create MCP agent: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create MCP agent: {result['error']}"
            )
        
        created_agent = result["data"][0] if result.get("data") else None
        
        # Clear graph cache since new MCP agent added
        clear_user_graph_cache(provider_id)
        
        logger.info(f"✅ MCP agent '{payload.agent_name}' registered for user {provider_id}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"MCP agent '{payload.agent_name}' registered successfully",
                "agent": created_agent
            },
            status_code=status.HTTP_201_CREATED
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error registering MCP platform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register MCP platform: {str(e)}"
        )


@router.get("/list", response_model=dict)
async def list_mcp_platforms(
    provider_id: str = Query(..., description="User's provider ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status: active, inactive, error")
):
    """
    List all MCP platforms registered by the user.
    """
    try:
        db = await async_supabase.get_instance()
        
        filters = {"provider_id": provider_id}
        if status_filter:
            filters["status"] = status_filter
        
        result = await db.select(
            "mcp_agents",
            select="*",
            filters=filters
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch MCP platforms: {result['error']}"
            )
        
        agents = result.get("data", [])
        
        return JSONResponse(
            content={
                "success": True,
                "count": len(agents),
                "agents": agents
            },
            status_code=status.HTTP_200_OK
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing MCP platforms: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP platforms: {str(e)}"
        )


@router.get("/{agent_name}", response_model=dict)
async def get_mcp_platform(
    agent_name: str,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Get details of a specific MCP platform.
    """
    try:
        db = await async_supabase.get_instance()
        
        result = await db.select(
            "mcp_agents",
            select="*",
            filters={
                "provider_id": provider_id,
                "agent_name": agent_name
            }
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch MCP platform: {result['error']}"
            )
        
        agents = result.get("data", [])
        if not agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent '{agent_name}' not found"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "agent": agents[0]
            },
            status_code=status.HTTP_200_OK
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching MCP platform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch MCP platform: {str(e)}"
        )


@router.patch("/{agent_name}", response_model=dict)
async def update_mcp_platform(
    agent_name: str,
    payload: MCPPlatformUpdate,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Update an existing MCP platform configuration.
    """
    try:
        db = await async_supabase.get_instance()
        
        # Build update data
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        
        if payload.server_url is not None:
            update_data["server_url"] = payload.server_url
        if payload.description is not None:
            update_data["description"] = payload.description
        if payload.status is not None:
            if payload.status not in ["active", "inactive", "error"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Status must be one of: active, inactive, error"
                )
            update_data["status"] = payload.status
        if payload.metadata is not None:
            update_data["metadata"] = payload.metadata
        if payload.headers is not None:
            update_data["headers"] = payload.headers
        
        result = await db.update(
            "mcp_agents",
            update_data,
            filters={
                "provider_id": provider_id,
                "agent_name": agent_name
            }
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update MCP platform: {result['error']}"
            )
        
        updated_agents = result.get("data", [])
        if not updated_agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent '{agent_name}' not found"
            )
        
        # Clear graph cache since MCP agent updated
        clear_user_graph_cache(provider_id)
        
        logger.info(f"✅ MCP agent '{agent_name}' updated for user {provider_id}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"MCP agent '{agent_name}' updated successfully",
                "agent": updated_agents[0]
            },
            status_code=status.HTTP_200_OK
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating MCP platform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update MCP platform: {str(e)}"
        )


@router.delete("/{agent_name}", response_model=dict)
async def delete_mcp_platform(
    agent_name: str,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Delete an MCP platform configuration.
    """
    try:
        db = await async_supabase.get_instance()
        
        result = await db.delete(
            "mcp_agents",
            filters={
                "provider_id": provider_id,
                "agent_name": agent_name
            }
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete MCP platform: {result['error']}"
            )
        
        deleted = result.get("data", [])
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent '{agent_name}' not found"
            )
        
        # Clear graph cache since MCP agent deleted
        clear_user_graph_cache(provider_id)
        
        logger.info(f"✅ MCP agent '{agent_name}' deleted for user {provider_id}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"MCP agent '{agent_name}' deleted successfully"
            },
            status_code=status.HTTP_200_OK
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting MCP platform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MCP platform: {str(e)}"
        )


@router.post("/{agent_name}/sync-tools", response_model=dict)
async def sync_mcp_tools(
    agent_name: str,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Sync tools from the MCP server and update the agent's tools cache.
    
    This endpoint:
    1. Connects to the MCP server
    2. Fetches available tools
    3. Updates the tools_cache in the database
    4. Returns the synced tools
    """
    try:
        from services.mcp_client import MCPClientWrapper
        
        db = await async_supabase.get_instance()
        
        # Get agent config
        result = await db.select(
            "mcp_agents",
            select="*",
            filters={
                "provider_id": provider_id,
                "agent_name": agent_name
            }
        )
        
        if result.get("error") or not result.get("data"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent '{agent_name}' not found"
            )
        
        agent = result["data"][0]
        server_url = agent["server_url"]
        
        # Connect to MCP server and fetch tools
        logger.info(f"🔧 Fetching tools from MCP server: {server_url}")
        
        # Get headers from agent config if available
        headers = agent.get("headers") or {}
        client = MCPClientWrapper(server_url, agent_name, headers=headers)
        
        # First, test connection
        logger.info(f"Testing connection to MCP server: {server_url}")
        is_connected = await client.connect(timeout=10.0)
        
        if not is_connected:
            # Get detailed error information
            last_error = client.get_last_error() or ""
            error_msg = f"Cannot connect to MCP server at {server_url}."
            
            # Check if it's a protocol mismatch (common with REST APIs)
            if "text/event-stream" in last_error or "application/json" in last_error:
                error_msg += " ⚠️ Protocol Error: The server returned 'application/json' instead of 'text/event-stream'. This is not an SSE-compatible MCP server. MCP requires Server-Sent Events (SSE) protocol. Please use an SSE endpoint (e.g., http://localhost:8002/sse) or set up a proper MCP server."
            elif "SSEError" in last_error:
                error_msg += " ⚠️ SSE Protocol Error: The endpoint is not configured for Server-Sent Events. MCP servers must use SSE."
            elif "Connection refused" in last_error or "ConnectError" in last_error:
                error_msg += " ⚠️ Connection Refused: The server is not running or not accessible at this URL."
            elif "timeout" in last_error.lower():
                error_msg += " ⚠️ Timeout: The server did not respond within 10 seconds."
            else:
                error_msg += f" Please ensure the server is running, accessible, and uses the SSE protocol. Error: {last_error}"
            
            logger.error(f"❌ {error_msg}")
            await db.update(
                "mcp_agents",
                {"status": "error", "metadata": {"last_error": error_msg, "raw_error": last_error}},
                filters={
                    "provider_id": provider_id,
                    "agent_name": agent_name
                }
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        
        try:
            tools = await client.fetch_tools()
            
            if not tools:
                error_msg = f"MCP server at {server_url} is reachable but returned no tools. The server may be starting up or misconfigured."
                logger.warning(f"⚠️ {error_msg}")
                # Update status to error
                await db.update(
                    "mcp_agents",
                    {"status": "error", "metadata": {"last_error": error_msg}},
                    filters={
                        "provider_id": provider_id,
                        "agent_name": agent_name
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=error_msg
                )
            
            # Update database with tools cache
            update_result = await db.update(
                "mcp_agents",
                {
                    "tools_cache": tools,
                    "last_synced": datetime.utcnow().isoformat(),
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat()
                },
                filters={
                    "provider_id": provider_id,
                    "agent_name": agent_name
                }
            )
            
            if update_result.get("error"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update tools cache: {update_result['error']}"
                )
            
            # Clear graph cache since MCP tools updated
            clear_user_graph_cache(provider_id)
            
            logger.info(f"✅ Synced {len(tools)} tools for MCP agent '{agent_name}'")
            
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Synced {len(tools)} tools successfully",
                    "tools": tools,
                    "synced_at": datetime.utcnow().isoformat()
                },
                status_code=status.HTTP_200_OK
            )
            
        except HTTPException as http_exc:
            # Re-raise HTTPExceptions (like connection errors) as-is
            raise http_exc
        except Exception as e:
            # Update status to error for unexpected errors
            error_msg = f"Unexpected error while fetching tools: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            await db.update(
                "mcp_agents",
                {"status": "error", "metadata": {"last_error": error_msg}},
                filters={
                    "provider_id": provider_id,
                    "agent_name": agent_name
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error syncing MCP tools: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync MCP tools: {str(e)}"
        )


@router.post("/{agent_name}/verify", response_model=dict)
async def verify_mcp_platform(
    agent_name: str,
    provider_id: str = Query(..., description="User's provider ID")
):
    """
    Verify that an MCP server is accessible and working.
    """
    try:
        from services.mcp_client import MCPClientWrapper
        
        db = await async_supabase.get_instance()
        
        # Get agent config
        result = await db.select(
            "mcp_agents",
            select="*",
            filters={
                "provider_id": provider_id,
                "agent_name": agent_name
            }
        )
        
        if result.get("error") or not result.get("data"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent '{agent_name}' not found"
            )
        
        agent = result["data"][0]
        server_url = agent["server_url"]
        
        # Get headers from agent config if available
        headers = agent.get("headers") or {}
        
        # Try to connect and fetch tools
        client = MCPClientWrapper(server_url, agent_name, headers=headers)
        
        try:
            tools = await client.fetch_tools()
            verification = {
                "accessible": True,
                "tools_count": len(tools),
                "message": "MCP server is accessible and working"
            }
        except Exception as e:
            verification = {
                "accessible": False,
                "error": str(e),
                "message": "MCP server is not accessible"
            }
        
        return JSONResponse(
            content={
                "success": True,
                "agent_name": agent_name,
                "server_url": server_url,
                "verification": verification
            },
            status_code=status.HTTP_200_OK
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying MCP platform: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify MCP platform: {str(e)}"
        )
