"""
MCP Connection Diagnostic Script
Test MCP server connectivity and tool discovery
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.mcp_client import MCPClientWrapper


async def test_mcp_server(server_url: str, agent_name: str = "test", headers: dict = None):
    """
    Test connection to an MCP server and fetch its tools
    
    Args:
        server_url: URL of the MCP server (e.g., http://localhost:8002/sse)
        agent_name: Name for the agent
        headers: Optional HTTP headers for authentication
    """
    print(f"\n{'='*60}")
    print(f"Testing MCP Server: {server_url}")
    print(f"Agent Name: {agent_name}")
    print(f"{'='*60}\n")
    
    try:
        client = MCPClientWrapper(server_url, agent_name, headers=headers)
        
        # Test connection
        print("🔍 Testing connection...")
        is_connected = await client.connect(timeout=10.0)
        
        if not is_connected:
            print("❌ Failed to connect to MCP server")
            print(f"   Server may be down or URL is incorrect: {server_url}")
            return False
        
        print("✅ Connection successful!\n")
        
        # Fetch tools
        print("🔍 Fetching available tools...")
        tools = await client.fetch_tools()
        
        if not tools:
            print("⚠️  No tools returned from server")
            print("   The server is reachable but has no tools configured")
            return False
        
        print(f"✅ Found {len(tools)} tools:\n")
        
        # Display tools
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool['name']}")
            print(f"   Description: {tool['description']}")
            if tool.get('inputSchema'):
                required = tool['inputSchema'].get('required', [])
                if required:
                    print(f"   Required params: {', '.join(required)}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_mcp_connection.py <server_url> [agent_name]")
        print("\nExample:")
        print("  python test_mcp_connection.py http://localhost:8002/sse grassdoor")
        print("\nCommon MCP servers:")
        print("  - http://localhost:8002/sse  (typical SSE endpoint)")
        print("  - http://localhost:3000/mcp  (alternative)")
        sys.exit(1)
    
    server_url = sys.argv[1]
    agent_name = sys.argv[2] if len(sys.argv) > 2 else "test"
    
    # Optional: Add headers for authentication
    headers = {}
    # headers = {"Authorization": "Bearer YOUR_TOKEN"}
    
    success = await test_mcp_server(server_url, agent_name, headers)
    
    if success:
        print("✅ MCP server test completed successfully")
        sys.exit(0)
    else:
        print("❌ MCP server test failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
