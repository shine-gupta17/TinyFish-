# MCP SSE Protocol Error - Wrong Content-Type

## Error Details

```
ERROR:mcp.client.sse:Encountered SSE exception
httpx_sse._exceptions.SSEError: Expected response header Content-Type to contain 'text/event-stream', got 'application/json'
```

## Root Cause

The URL `https://mcp.rapidapi.com` is **NOT an SSE-compatible MCP server**. It returns:
- ✅ HTTP 200 OK (server is accessible)
- ❌ Content-Type: `application/json` (wrong protocol)
- ✅ Expected: Content-Type: `text/event-stream` (SSE protocol)

**This is a REST API endpoint, not an MCP SSE server.**

## Understanding MCP Protocol

The Model Context Protocol (MCP) requires **Server-Sent Events (SSE)** for real-time, bidirectional communication between the client and server. SSE uses:
- HTTP connection that stays open
- Server pushes data to client
- Content-Type: `text/event-stream`
- Event-based message format

### Valid MCP Server Examples:
```
✅ http://localhost:8002/sse
✅ http://localhost:3000/mcp/sse
✅ ws://localhost:8080/mcp (WebSocket alternative)
```

### Invalid MCP Server Examples:
```
❌ https://mcp.rapidapi.com (REST API, returns JSON)
❌ https://api.example.com/tools (REST endpoint)
❌ http://localhost:8000/api/tools (Non-SSE endpoint)
```

## Solutions

### Option 1: Use a Proper MCP Server

You need to **deploy or connect to an actual MCP server** that implements the SSE protocol.

#### Popular MCP Server Implementations:

1. **Official MCP Python Server**
   ```bash
   pip install mcp
   
   # Create server.py
   from mcp.server import Server
   from mcp.server.sse import SseServerTransport
   
   app = Server("my-mcp-server")
   
   @app.list_tools()
   async def list_tools():
       return [...]
   
   # Run with SSE transport
   ```

2. **MCP TypeScript Server**
   ```bash
   npm install @modelcontextprotocol/sdk
   ```

3. **Custom Python SSE Server**
   See: `/demo-mcp/tweeter_mcp.py` for an example

### Option 2: Set Up Local MCP Server

If you want to use Glassdoor or similar services, you need to:

1. **Create a wrapper MCP server** that:
   - Exposes SSE endpoint
   - Internally calls the REST API (RapidAPI)
   - Transforms responses to MCP format

Example structure:
```python
# glassdoor_mcp_server.py
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import httpx

app = Server("glassdoor")

@app.list_tools()
async def list_tools():
    return [
        {
            "name": "search_jobs",
            "description": "Search for jobs on Glassdoor",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "location": {"type": "string"}
                }
            }
        }
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_jobs":
        # Call RapidAPI here
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://mcp.rapidapi.com/search",
                headers={"X-RapidAPI-Key": "YOUR_KEY"},
                params=arguments
            )
            return response.json()
    
# Run with: uvicorn glassdoor_mcp_server:app --host 0.0.0.0 --port 8002
```

Then update your ChatVerse configuration:
```
Server URL: http://localhost:8002/sse
```

### Option 3: Check If Service Offers SSE Endpoint

Contact the service provider (RapidAPI, Glassdoor) to see if they offer:
- SSE endpoint for real-time data
- WebSocket endpoint (alternative)
- MCP-compatible server

### Option 4: Use Direct API Integration (Non-MCP)

If the service doesn't support MCP/SSE, integrate it directly:
- Create a custom router in ChatVerse
- Call the REST API directly
- Don't use MCP for this service

## How to Fix Your Current Setup

### Step 1: Remove Invalid MCP Agent
```bash
curl -X DELETE "http://localhost:8000/platforms/mcp/Glassdoor?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7"
```

### Step 2: Create a Local MCP Wrapper Server

Create `/demo-mcp/glassdoor_mcp.py`:

```python
"""
Glassdoor MCP Server
Wraps RapidAPI Glassdoor endpoint in MCP protocol
"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import httpx
import os

app = FastAPI()
mcp_server = Server("glassdoor")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "your-key-here")
RAPIDAPI_HOST = "glassdoor1.p.rapidapi.com"

@mcp_server.list_tools()
async def list_tools():
    return [
        {
            "name": "search_jobs",
            "description": "Search for job listings on Glassdoor",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Job search query"},
                    "location": {"type": "string", "description": "Location"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_company_reviews",
            "description": "Get company reviews from Glassdoor",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"}
                },
                "required": ["company"]
            }
        }
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient() as client:
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        
        if name == "search_jobs":
            response = await client.get(
                f"https://{RAPIDAPI_HOST}/jobs",
                headers=headers,
                params=arguments
            )
            return {"result": response.json()}
        
        elif name == "get_company_reviews":
            response = await client.get(
                f"https://{RAPIDAPI_HOST}/reviews",
                headers=headers,
                params=arguments
            )
            return {"result": response.json()}

# SSE endpoint for MCP
@app.get("/sse")
async def sse_endpoint():
    transport = SseServerTransport()
    
    async def event_generator():
        async with mcp_server.run(transport):
            async for event in transport:
                yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
```

### Step 3: Run the Wrapper Server
```bash
cd /home/bittu/Desktop/chatverse/ChatVerse-AI-Development/demo-mcp

# Set your RapidAPI key
export RAPIDAPI_KEY="your-rapidapi-key-here"

# Run the server
python glassdoor_mcp.py
```

### Step 4: Register with Correct URL
```bash
curl -X POST "http://localhost:8000/platforms/mcp/register?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Glassdoor",
    "server_url": "http://localhost:8003/sse",
    "description": "Search jobs and get company reviews from Glassdoor"
  }'
```

### Step 5: Sync Tools
```bash
curl -X POST "http://localhost:8000/platforms/mcp/Glassdoor/sync-tools?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7"
```

## Testing Your MCP Server

Use the diagnostic script:
```bash
python scripts/test_mcp_connection.py http://localhost:8003/sse Glassdoor
```

Expected output:
```
✅ Connection successful!
✅ Found 2 tools:
1. search_jobs
   Description: Search for job listings on Glassdoor
2. get_company_reviews
   Description: Get company reviews from Glassdoor
```

## Verify SSE Endpoint Manually

```bash
# This should stream events, not return JSON
curl -N -H "Accept: text/event-stream" http://localhost:8003/sse

# Expected: SSE stream (keeps connection open)
# Wrong: JSON response (closes immediately)
```

## Summary

**The Problem:**
- `https://mcp.rapidapi.com` is a REST API (JSON)
- MCP requires SSE protocol (text/event-stream)
- These are incompatible

**The Solution:**
1. Create a wrapper MCP server that implements SSE
2. Wrapper calls RapidAPI internally
3. Register the wrapper's SSE endpoint in ChatVerse
4. Now you have MCP-compatible access to RapidAPI services

**Alternative:**
- Use the service's direct API without MCP
- Integrate it as a regular API endpoint in ChatVerse
