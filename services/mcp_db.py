"""
MCP Agents Database Operations (Backend Version)
Handles CRUD operations for MCP server configurations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from supabase_client_async import get_supabase_client
import asyncio


class MCPDatabase:
    """Database operations for MCP agents"""

    def __init__(self):
        self.supabase = None

    async def _get_client(self):
        """Get Supabase client"""
        if self.supabase is None:
            self.supabase = await get_supabase_client()
        return self.supabase

    async def add_mcp_agent(
        self,
        provider_id: str,
        agent_name: str,
        server_url: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Add a new MCP agent configuration"""
        client = await self._get_client()
        metadata = metadata or {}
        headers = headers or {}
        
        data = {
            'provider_id': provider_id,
            'agent_name': agent_name,
            'server_url': server_url,
            'description': description,
            'metadata': metadata,
            'headers': headers,
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        result = await client.table('mcp_agents').insert(data).execute()
        return result.data[0] if result.data else None

    async def update_mcp_agent(
        self,
        agent_id: int,
        provider_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update an existing MCP agent configuration"""
        client = await self._get_client()
        
        # Only update allowed fields
        allowed_fields = ['agent_name', 'server_url', 'description', 'metadata', 'headers', 'status']
        update_data = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not update_data:
            return None
        
        update_data['updated_at'] = datetime.now().isoformat()
        
        result = await client.table('mcp_agents').update(update_data).eq('id', agent_id).eq('provider_id', provider_id).execute()
        return result.data[0] if result.data else None

    async def delete_mcp_agent(self, agent_id: int, provider_id: str) -> bool:
        """Delete an MCP agent configuration"""
        client = await self._get_client()
        
        result = await client.table('mcp_agents').delete().eq('id', agent_id).eq('provider_id', provider_id).execute()
        return len(result.data) > 0 if result.data else False

    async def get_mcp_agent(self, agent_id: int, provider_id: str) -> Optional[Dict[str, Any]]:
        """Get a single MCP agent by ID"""
        client = await self._get_client()
        
        result = await client.table('mcp_agents').select('*').eq('id', agent_id).eq('provider_id', provider_id).execute()
        return result.data[0] if result.data else None

    async def list_mcp_agents(
        self, 
        provider_id: str, 
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all MCP agents for a provider"""
        client = await self._get_client()
        
        query = client.table('mcp_agents').select('*').eq('provider_id', provider_id)
        
        if status:
            query = query.eq('status', status)
        
        query = query.order('created_at', desc=True)
        result = await query.execute()
        
        return result.data if result.data else []

    async def get_active_mcp_agents(self, provider_id: str) -> List[Dict[str, Any]]:
        """Get all active MCP agents for task dispatcher"""
        return await self.list_mcp_agents(provider_id, status='active')

    async def update_tools_cache(
        self,
        agent_id: int,
        provider_id: str,
        tools: List[Dict[str, Any]]
    ) -> bool:
        """Update the tools cache for an MCP agent after syncing"""
        client = await self._get_client()
        
        update_data = {
            'tools_cache': tools,
            'last_synced': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        result = await client.table('mcp_agents').update(update_data).eq('id', agent_id).eq('provider_id', provider_id).execute()
        return len(result.data) > 0 if result.data else False

    async def update_agent_status(
        self,
        agent_id: int,
        provider_id: str,
        status: str,
        error_msg: Optional[str] = None
    ) -> bool:
        """Update agent status (e.g., when connection fails)"""
        client = await self._get_client()
        
        update_data = {
            'status': status,
            'updated_at': datetime.now().isoformat()
        }
        
        if error_msg:
            # Update metadata with error message
            agent = await self.get_mcp_agent(agent_id, provider_id)
            if agent:
                metadata = agent.get('metadata', {})
                metadata['last_error'] = error_msg
                update_data['metadata'] = metadata
        
        result = await client.table('mcp_agents').update(update_data).eq('id', agent_id).eq('provider_id', provider_id).execute()
        return len(result.data) > 0 if result.data else False
