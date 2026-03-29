# MCP Headers Feature - Implementation Guide

## Overview
Added support for authentication headers in MCP agents, allowing users to securely store API keys and authentication tokens for MCP server connections.

## Changes Made

### 1. Database Migration
**File:** `SQL_database/migrations/add_headers_to_mcp_agents.sql`

Added `headers` column to `mcp_agents` table:
- Type: `JSONB`
- Default: `{}`
- Purpose: Store HTTP headers for MCP server authentication

```sql
ALTER TABLE mcp_agents ADD COLUMN headers JSONB DEFAULT '{}';
```

### 2. Backend Changes

#### File: `ChatVerse-Backend-Dev/routers/platforms/mcp.py`

**Updated Models:**
```python
class MCPPlatformCreate(BaseModel):
    headers: Optional[dict] = Field(default={}, description="HTTP headers for authentication")

class MCPPlatformUpdate(BaseModel):
    headers: Optional[dict] = Field(None, description="HTTP headers for authentication")

class MCPPlatformResponse(BaseModel):
    headers: dict  # Added to response
```

**Updated Endpoints:**

1. **POST /platforms/mcp/register**
   - Now accepts `headers` in request body
   - Stores headers in database

2. **PATCH /platforms/mcp/{agent_name}**
   - Now accepts `headers` in request body
   - Updates headers in database

3. **GET /platforms/mcp/{agent_name}**
   - Returns headers in response

4. **POST /platforms/mcp/{agent_name}/sync-tools**
   - Retrieves headers from database
   - Passes headers to MCP client for authentication

5. **POST /platforms/mcp/{agent_name}/verify**
   - Retrieves headers from database
   - Uses headers for server verification

### 3. Frontend Changes

#### File: `ChatVerse-Frontend-Development/src/pages/platform-selection/MCPPlatformCard.tsx`

**Add Form:**
- Added "Custom Headers" section
- Header names shown in text input
- Header values shown as password inputs (••••••••)
- Add/Remove header functionality

**Edit Form:**
- Added "Authentication Headers" section
- Same password protection for header values
- Edit existing headers or add new ones
- Delete headers functionality

**State Management:**
- Added `headers` state for add form
- Added `editHeaders` state for edit mode
- Headers passed to API on create/update

#### File: `ChatVerse-Frontend-Development/src/api/mcp_api.ts`

Interface already supports headers:
```typescript
export interface MCPAgentRequest {
  headers?: Record<string, string>;
}
```

## Usage Examples

### 1. Register MCP Agent with Headers

**Frontend:**
```typescript
await MCPApiService.registerMCPAgent(providerId, {
  agent_name: "glassdoor",
  server_url: "http://localhost:8003/sse",
  description: "Glassdoor API integration",
  headers: {
    "x-api-key": "your-api-key-here",
    "Authorization": "Bearer token-here"
  }
});
```

**Backend Request:**
```bash
curl -X POST "http://localhost:8000/platforms/mcp/register?provider_id=USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "glassdoor",
    "server_url": "http://localhost:8003/sse",
    "description": "Glassdoor integration",
    "headers": {
      "x-api-key": "your-key",
      "Authorization": "Bearer token"
    }
  }'
```

### 2. Update MCP Agent Headers

**Frontend:**
```typescript
await MCPApiService.updateMCPAgent(providerId, "glassdoor", {
  headers: {
    "x-api-key": "new-api-key",
    "x-custom-header": "value"
  }
});
```

**Backend Request:**
```bash
curl -X PATCH "http://localhost:8000/platforms/mcp/glassdoor?provider_id=USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {
      "x-api-key": "new-key"
    }
  }'
```

## Security Features

### 1. Password Protection
- Header values displayed as password fields (•••••)
- Prevents shoulder surfing
- Values still transmitted securely

### 2. Database Storage
- Stored as JSONB in PostgreSQL
- Consider encryption at rest for production
- Use Supabase RLS policies for access control

### 3. Transmission
- Sent over HTTPS
- No logging of sensitive header values
- Passed securely to MCP client

## Migration Steps

### Step 1: Run Database Migration
```bash
# Connect to your database
psql -U postgres -d chatverse

# Run the migration
\i SQL_database/migrations/add_headers_to_mcp_agents.sql
```

### Step 2: Restart Backend
```bash
cd ChatVerse-Backend-Dev
# Kill existing process
pkill -f "python.*app.py"

# Restart
python app.py
```

### Step 3: Clear Frontend Cache
```bash
cd ChatVerse-Frontend-Development
npm run build
# Or just reload the browser with cache clear (Ctrl+Shift+R)
```

## Testing

### 1. Test Add Agent with Headers
1. Go to Platform Selection page
2. Click "Add Agent" button
3. Fill in agent details
4. Click "+ Add Header"
5. Enter header name (e.g., `x-api-key`)
6. Enter header value (should show as password)
7. Submit form
8. Verify agent is created

### 2. Test Edit Agent Headers
1. Find existing MCP agent card
2. Click "Edit" button
3. Scroll to "Authentication Headers" section
4. Modify existing headers or add new ones
5. Click "Save"
6. Verify changes are persisted

### 3. Test Sync with Headers
1. Edit agent and add authentication headers
2. Click "Sync" button
3. Verify tools are fetched successfully
4. Check backend logs to confirm headers are used

## Common Header Examples

### API Key Authentication
```json
{
  "x-api-key": "your-api-key-here"
}
```

### Bearer Token
```json
{
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."
}
```

### Basic Auth
```json
{
  "Authorization": "Basic dXNlcm5hbWU6cGFzc3dvcmQ="
}
```

### Multiple Headers
```json
{
  "x-api-key": "key123",
  "x-client-id": "client456",
  "Authorization": "Bearer token789"
}
```

## Troubleshooting

### Headers Not Being Used
1. Check database: `SELECT headers FROM mcp_agents WHERE agent_name = 'your-agent';`
2. Verify backend logs show headers being retrieved
3. Check MCP client receives headers

### Authentication Still Failing
1. Verify header names are correct (case-sensitive)
2. Check header values are valid
3. Test MCP server directly with headers:
   ```bash
   curl -H "x-api-key: your-key" http://localhost:8003/sse
   ```

### Headers Not Saving
1. Check database migration was successful
2. Verify backend model includes headers field
3. Check for errors in browser console

## Future Enhancements

1. **Encryption at Rest:** Encrypt header values in database
2. **Header Templates:** Pre-defined templates for common services
3. **Validation:** Validate header format before saving
4. **Masked Display:** Show only last 4 characters (e.g., `••••••key123`)
5. **Header Management UI:** Dedicated page for managing all headers

## Notes

- Headers are stored as plain JSONB in database
- For production, consider using secrets management (Vault, AWS Secrets Manager)
- Always use HTTPS for API communication
- Regularly rotate API keys and tokens
- Use Supabase Row Level Security for additional protection
