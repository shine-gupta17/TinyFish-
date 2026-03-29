# MCP 503 Service Unavailable Error - Troubleshooting Guide

## Error Overview
```
INFO: 127.0.0.1:52474 - "POST /platforms/mcp/grassdoor/sync-tools?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7 HTTP/1.1" 503 Service Unavailable
```

## Root Cause
The 503 error occurs when the MCP sync-tools endpoint cannot successfully fetch tools from the configured MCP server. This happens in one of these scenarios:

1. **MCP server is not running** (most common)
2. **MCP server URL is incorrect or unreachable**
3. **MCP server is running but returns no tools**
4. **Network/firewall blocking the connection**
5. **Authentication/header issues**

## Diagnostic Steps

### Step 1: Check if MCP Server is Running
```bash
# Check for grassdoor process
ps aux | grep grassdoor

# Check all MCP server processes
ps aux | grep -i mcp

# Check if any process is listening on the expected port
netstat -tlnp | grep <PORT>
# or
lsof -i :<PORT>
```

### Step 2: Test MCP Server Connection
Use the diagnostic script we've created:

```bash
cd /home/bittu/Desktop/chatverse/ChatVerse-AI-Development/ChatVerse-Backend-Dev

# Test with your server URL
python scripts/test_mcp_connection.py http://localhost:8002/sse grassdoor
```

Expected output if successful:
```
✅ Connection successful!
✅ Found X tools:
1. tool_name
   Description: ...
```

### Step 3: Check Database Configuration
Query the database to see the stored configuration:

```sql
SELECT agent_name, server_url, status, metadata, last_synced
FROM mcp_agents
WHERE agent_name = 'grassdoor'
AND provider_id = '7e86f535-546e-4139-a72a-1ea5736a07f7';
```

### Step 4: Check Application Logs
Look for detailed error messages:

```bash
# If running with systemd
journalctl -u chatverse-api -n 100 --no-pager

# If running in terminal
# Check the terminal where the FastAPI app is running

# Check for Python tracebacks
tail -f /var/log/chatverse/*.log
```

## Solutions

### Solution 1: Start the MCP Server
If the grassdoor MCP server is not running, you need to start it first.

```bash
# Navigate to the MCP server directory
cd /path/to/grassdoor/mcp/server

# Start the server (adjust command based on your setup)
python grassdoor_mcp.py
# or
npm start
# or
node server.js
```

### Solution 2: Update Server URL
If the server is running on a different port or host:

```bash
# Use the update endpoint
curl -X PUT "http://localhost:8000/platforms/mcp/grassdoor?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7" \
  -H "Content-Type: application/json" \
  -d '{
    "server_url": "http://localhost:CORRECT_PORT/sse"
  }'
```

### Solution 3: Add Authentication Headers
If the MCP server requires authentication:

```bash
curl -X PUT "http://localhost:8000/platforms/mcp/grassdoor?provider_id=7e86f535-546e-4139-a72a-1ea5736a07f7" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN",
      "X-API-Key": "YOUR_API_KEY"
    }
  }'
```

### Solution 4: Verify MCP Server Health
Test the MCP server directly:

```bash
# Test SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8002/sse

# Expected: Should establish an SSE connection
```

### Solution 5: Check Firewall/Network
```bash
# Check if port is accessible
telnet localhost 8002

# Check firewall rules
sudo iptables -L -n | grep 8002
sudo ufw status | grep 8002
```

## Enhanced Error Messages

I've improved the error handling to provide more detailed messages:

**Before:**
```
"MCP server returned no tools"
```

**After:**
```
"Cannot connect to MCP server at http://localhost:8002/sse. Please ensure the server is running and accessible."

"MCP server at http://localhost:8002/sse is reachable but returned no tools. The server may be starting up or misconfigured."
```

## Code Changes Made

### File: `ChatVerse-Backend-Dev/routers/platforms/mcp.py`

1. **Added connection test before fetching tools:**
   - Tests connection with 10-second timeout
   - Provides clear error message if connection fails

2. **Added header support:**
   - Retrieves headers from agent configuration
   - Passes headers to MCP client for authentication

3. **Improved error messages:**
   - Distinguishes between connection failures and empty tool responses
   - Logs detailed error information for debugging

4. **Better exception handling:**
   - Separates HTTPExceptions from unexpected errors
   - Updates agent status with error details

### New File: `ChatVerse-Backend-Dev/scripts/test_mcp_connection.py`

Diagnostic script to test MCP server connectivity:
```bash
python scripts/test_mcp_connection.py <server_url> [agent_name]
```

## Quick Fix Checklist

- [ ] MCP server is running
- [ ] Server URL is correct in database
- [ ] Port is accessible (check firewall)
- [ ] Authentication headers are configured (if required)
- [ ] Server returns tools when queried directly
- [ ] Network connectivity is stable
- [ ] No DNS resolution issues

## Getting More Help

If the issue persists after trying these solutions:

1. Run the diagnostic script and share the output
2. Check application logs for detailed stack traces
3. Verify MCP server logs for errors
4. Test the MCP server independently of ChatVerse
5. Check if other MCP agents work (isolate the issue)

## Prevention

To avoid this issue in the future:

1. **Health Monitoring:** Set up monitoring for MCP server availability
2. **Auto-restart:** Configure systemd or supervisor to auto-restart crashed MCP servers
3. **Validation:** Use the `/verify` endpoint before syncing tools
4. **Error Alerts:** Set up alerts for 503 errors in your monitoring system
