"""
MCP Management API Router
Endpoints for managing user's MCP server configurations
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.mcp_db import MCPDatabase
from services.mcp_client import MCPClientWrapper

# You'll need to import your auth dependency
# from your_auth_module import get_current_user


router = APIRouter(prefix="/api/mcp", tags=["MCP Agents"])


# Request/Response Models
class MCPAgentCreate(BaseModel):
    """Request model for creating a new MCP agent"""
    agent_name: str = Field(..., min_length=3, max_length=50, description="Unique name for the MCP agent")
    server_url: str = Field(..., description="MCP server URL (e.g., http://localhost:8002/sse)")
    description: str = Field(..., min_length=10, max_length=500, description="What this MCP agent does")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for MCP server connection (e.g., authorization, api keys)")


class MCPAgentUpdate(BaseModel):
    """Request model for updating an MCP agent"""
    agent_name: Optional[str] = Field(None, min_length=3, max_length=50)
    server_url: Optional[str] = None
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    status: Optional[str] = Field(None, pattern="^(active|inactive|error)$")
    metadata: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for MCP server connection")


class MCPAgentResponse(BaseModel):
    """Response model for MCP agent"""
    id: int
    provider_id: str
    agent_name: str
    server_url: str
    description: str
    status: str
    metadata: Dict[str, Any]
    headers: Dict[str, str]
    tools_cache: List[Dict[str, Any]]
    last_synced: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class MCPAgentSyncResponse(BaseModel):
    """Response for tool sync operation"""
    success: bool
    agent_name: str
    tools_count: int
    message: str


class MCPTestConnectionRequest(BaseModel):
    """Request to test MCP server connection"""
    server_url: str


class MCPTestConnectionResponse(BaseModel):
    """Response for connection test"""
    success: bool
    server_url: str
    message: str
    tools_count: Optional[int] = None


# Dependency to get current user/provider
# Replace this with your actual auth dependency
async def get_current_provider_id() -> str:
    """
    Get the current authenticated user's provider_id
    TODO: Replace with actual auth dependency
    """
    # This is a placeholder - integrate with your actual auth system
    # Example: return current_user.id or current_user.provider_id
    return "test_provider_id"


@router.post("/add", response_model=MCPAgentResponse, status_code=status.HTTP_201_CREATED)
async def add_mcp_agent(
    agent_data: MCPAgentCreate,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Add a new MCP agent configuration for the authenticated user
    
    - **agent_name**: Unique identifier for this agent (used in task routing)
    - **server_url**: MCP server endpoint URL
    - **description**: Detailed description of what this agent does (used for task matching)
    - **metadata**: Optional additional configuration
    """
    mcp_db = MCPDatabase()
    
    try:
        # Test connection first
        client = MCPClientWrapper(agent_data.server_url, agent_data.agent_name, agent_data.headers)
        connected = await client.connect(timeout=10.0)
        
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot connect to MCP server at {agent_data.server_url}"
            )
        
        # Fetch tools
        tools = await client.fetch_tools()
        
        if not tools:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MCP server connected but no tools available"
            )
        
        # Add to database
        agent = await mcp_db.add_mcp_agent(
            provider_id=provider_id,
            agent_name=agent_data.agent_name,
            server_url=agent_data.server_url,
            description=agent_data.description,
            metadata=agent_data.metadata,
            headers=agent_data.headers
        )
        
        # Update tools cache
        await mcp_db.update_tools_cache(agent['id'], provider_id, tools)
        
        # Refresh agent data
        agent = await mcp_db.get_mcp_agent(agent['id'], provider_id)
        
        return MCPAgentResponse(**agent)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add MCP agent: {str(e)}"
        )


@router.get("/list", response_model=List[MCPAgentResponse])
async def list_mcp_agents(
    status_filter: Optional[str] = None,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    List all MCP agents for the authenticated user
    
    - **status_filter**: Optional filter by status (active, inactive, error)
    """
    mcp_db = MCPDatabase()
    
    try:
        agents = await mcp_db.list_mcp_agents(provider_id, status=status_filter)
        return [MCPAgentResponse(**agent) for agent in agents]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP agents: {str(e)}"
        )


@router.get("/{agent_id}", response_model=MCPAgentResponse)
async def get_mcp_agent(
    agent_id: int,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Get details of a specific MCP agent
    """
    mcp_db = MCPDatabase()
    
    try:
        agent = await mcp_db.get_mcp_agent(agent_id, provider_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent with id {agent_id} not found"
            )
        
        return MCPAgentResponse(**agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get MCP agent: {str(e)}"
        )


@router.put("/{agent_id}", response_model=MCPAgentResponse)
async def update_mcp_agent(
    agent_id: int,
    agent_data: MCPAgentUpdate,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Update an existing MCP agent configuration
    """
    mcp_db = MCPDatabase()
    
    try:
        # Get current agent
        current_agent = await mcp_db.get_mcp_agent(agent_id, provider_id)
        
        if not current_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent with id {agent_id} not found"
            )
        
        # Build update dict
        updates = agent_data.model_dump(exclude_unset=True)
        
        # If server_url changed, test connection
        if 'server_url' in updates and updates['server_url'] != current_agent['server_url']:
            client = MCPClientWrapper(
                updates['server_url'],
                updates.get('agent_name', current_agent['agent_name'])
            )
            connected = await client.connect(timeout=10.0)
            
            if not connected:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot connect to new MCP server URL"
                )
        
        # Update database
        updated_agent = await mcp_db.update_mcp_agent(agent_id, provider_id, **updates)
        
        if not updated_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Failed to update MCP agent"
            )
        
        return MCPAgentResponse(**updated_agent)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update MCP agent: {str(e)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_agent(
    agent_id: int,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Delete an MCP agent configuration
    """
    mcp_db = MCPDatabase()
    
    try:
        deleted = await mcp_db.delete_mcp_agent(agent_id, provider_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent with id {agent_id} not found"
            )
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MCP agent: {str(e)}"
        )


@router.post("/{agent_id}/sync-tools", response_model=MCPAgentSyncResponse)
async def sync_mcp_agent_tools(
    agent_id: int,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Manually sync tools from the MCP server for an agent
    """
    mcp_db = MCPDatabase()
    
    try:
        # Get agent config
        agent = await mcp_db.get_mcp_agent(agent_id, provider_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP agent with id {agent_id} not found"
            )
        
        # Create client and sync tools
        client = MCPClientWrapper(agent['server_url'], agent['agent_name'])
        tools = await client.fetch_tools()
        
        if not tools:
            await mcp_db.update_agent_status(
                agent_id,
                provider_id,
                'error',
                'No tools returned from server'
            )
            return MCPAgentSyncResponse(
                success=False,
                agent_name=agent['agent_name'],
                tools_count=0,
                message="Failed to sync tools from MCP server"
            )
        
        # Update database with synced tools
        await mcp_db.update_tools_cache(agent_id, provider_id, tools)
        await mcp_db.update_agent_status(agent_id, provider_id, 'active')
        
        return MCPAgentSyncResponse(
            success=True,
            agent_name=agent['agent_name'],
            tools_count=len(tools),
            message="Tools synced successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await mcp_db.update_agent_status(
            agent_id,
            provider_id,
            'error',
            str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync tools: {str(e)}"
        )


@router.post("/test-connection", response_model=MCPTestConnectionResponse)
async def test_mcp_connection(
    test_data: MCPTestConnectionRequest,
    provider_id: str = Depends(get_current_provider_id)
):
    """
    Test connection to an MCP server before adding it
    """
    try:
        client = MCPClientWrapper(test_data.server_url, "test_connection")
        connected = await client.connect(timeout=10.0)
        
        if not connected:
            return MCPTestConnectionResponse(
                success=False,
                server_url=test_data.server_url,
                message="Cannot connect to MCP server"
            )
        
        # Try fetching tools
        tools = await client.fetch_tools()
        
        return MCPTestConnectionResponse(
            success=True,
            server_url=test_data.server_url,
            message="Connection successful",
            tools_count=len(tools)
        )
        
    except Exception as e:
        return MCPTestConnectionResponse(
            success=False,
            server_url=test_data.server_url,
            message=f"Connection failed: {str(e)}"
        )
