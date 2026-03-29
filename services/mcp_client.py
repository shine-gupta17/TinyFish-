"""
MCP Client Wrapper (Backend Version)
Reusable client for connecting to MCP servers
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from mcp import ClientSession
from mcp.client.sse import sse_client
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPClientWrapper:
    """
    Wrapper for MCP client that handles:
    - Connection to MCP server
    - Tool discovery and caching
    - Tool execution
    - Error handling
    """

    def __init__(self, server_url: str, agent_name: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize MCP client wrapper
        
        Args:
            server_url: URL of the MCP server (e.g., http://localhost:8002/sse)
            agent_name: Unique name for this MCP agent
            headers: Optional HTTP headers for MCP server connection (e.g., authorization, api keys)
        """
        self.server_url = server_url
        self.agent_name = agent_name
        self.headers = headers or {}
        self._tools_cache: List[Dict[str, Any]] = []
        self._last_error: Optional[str] = None

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Test connection to the MCP server
        
        Args:
            timeout: Connection timeout in seconds
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            async with asyncio.timeout(timeout):
                async with sse_client(self.server_url, headers=self.headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._last_error = None
                        return True
        except Exception as e:
            error_msg = str(e)
            self._last_error = error_msg
            logger.error(f"MCP server {self.server_url} unreachable: {e}")
            return False

    async def fetch_tools(self) -> List[Dict[str, Any]]:
        """
        Fetch available tools from the MCP server
        
        Returns:
            List of tool metadata dictionaries
        """
        try:
            async with sse_client(self.server_url, headers=self.headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # List tools from MCP server
                    tools_response = await session.list_tools()
                    
                    # Convert to our format
                    tools = []
                    for tool in tools_response.tools:
                        tool_dict = {
                            'name': tool.name,
                            'description': tool.description or f"Execute {tool.name}",
                            'inputSchema': tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                            'fetched_at': datetime.now().isoformat()
                        }
                        tools.append(tool_dict)
                    
                    self._tools_cache = tools
                    logger.info(f"Fetched {len(tools)} tools from MCP server {self.agent_name}")
                    return tools
                    
        except Exception as e:
            logger.error(f"Failed to fetch tools from {self.agent_name}: {e}")
            return []

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Execute a specific MCP tool
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            timeout: Execution timeout in seconds
        
        Returns:
            Tool execution result
        """
        try:
            async with asyncio.timeout(timeout):
                async with sse_client(self.server_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        result = await session.call_tool(tool_name, arguments=arguments)
                        
                        # Extract content
                        if result.content:
                            content = result.content[0]
                            result_text = content.text if hasattr(content, "text") else str(content)
                            
                            return {
                                'success': True,
                                'tool_name': tool_name,
                                'result': result_text,
                                'executed_at': datetime.now().isoformat()
                            }
                        
                        return {
                            'success': True,
                            'tool_name': tool_name,
                            'result': str(result),
                            'executed_at': datetime.now().isoformat()
                        }
                        
        except asyncio.TimeoutError:
            return {
                'success': False,
                'tool_name': tool_name,
                'error': f'Tool execution timed out after {timeout}s'
            }
        except Exception as e:
            return {
                'success': False,
                'tool_name': tool_name,
                'error': str(e)
            }

    def get_tools_metadata(self) -> List[Dict[str, Any]]:
        """Get cached tools metadata"""
        return self._tools_cache

    async def sync_tools(self) -> List[Dict[str, Any]]:
        """
        Sync tools from server (refresh cache)
        
        Returns:
            Updated list of tools
        """
        return await self.fetch_tools()

    def get_last_error(self) -> Optional[str]:
        """Get the last error message from connection attempts"""
        return self._last_error
