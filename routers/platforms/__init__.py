"""
Platform routers package.
Contains routers for different platform integrations including MCP agents.
"""

from .mcp import router as mcp_router

__all__ = ["mcp_router"]
