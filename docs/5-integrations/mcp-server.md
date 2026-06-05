# MCP Integration

**Navigation**: [Documentation Home](../INDEX.md) > [Integrations](./INDEX.md) > MCP Integration

## Overview

DevBoard has two distinct MCP roles:

1. **MCP Client** (primary): DevBoard connects to external MCP servers and makes their tools available to its AI agents. This is the main user-facing feature — configure servers, assign tools to agent roles, and agents gain access to those tools at runtime.

2. **MCP Server** (secondary): DevBoard exposes a basic MCP endpoint so external AI clients can query projects and tasks.

---

## MCP Client Integration

### Configuring External MCP Servers

Navigate to **Settings → MCP Servers** to manage external servers.

Each server configuration specifies:

| Field | Description |
|-------|-------------|
| `name` | Display name |
| `server_type` | `STDIO` or `HTTP` |
| Connection config | `StdioMCPConfig` (command + args) or `HttpMCPConfig` (URL) |
| Authentication | None, Bearer Token, or OAuth 2.0 |

After saving, click **Verify** to open a live connection, discover available tools, and cache them as `MCPTool` records. The verification status and last-checked timestamp are stored on the server record.

### Authentication

External MCP servers support three authentication methods:

| Method | Description |
|--------|-------------|
| **None** | No authentication (default) |
| **Bearer Token** | Static bearer token in `Authorization` header |
| **OAuth 2.0** | Full OAuth 2.1 flow with auto-discovery, Dynamic Client Registration, and PKCE |

#### OAuth 2.0 Flow

OAuth authentication uses the MCP SDK's built-in `OAuthClientProvider`:

1. **Auto-discovery** (RFC 9728 Protected Resource Metadata)
2. **Dynamic Client Registration** (RFC 7591) — automatically registers DevBoard as an OAuth client
3. **PKCE Authorization** — opens the browser for user consent
4. **Token Exchange & Refresh** — manages access/refresh tokens automatically

**Basic setup (recommended)**: select "OAuth 2.0" and provide only the server URL; the SDK handles discovery and registration automatically.

**Manual credentials**: if the server doesn't support Dynamic Client Registration, provide a pre-configured Client ID and Secret to skip registration.

**Scopes** can optionally be specified as a space-separated string (e.g., `read write admin`).

When you click **Verify** on an OAuth-configured server, DevBoard opens the server's authorization page in your browser. After consent, tokens are exchanged and stored. Subsequent connections reuse stored tokens; the SDK automatically refreshes expired access tokens using the refresh token.

#### OAuth Status

The server detail view shows the current OAuth state:

- **Authenticated** (green) — valid tokens stored
- **Token expired** (amber) — re-verification needed
- **Not authenticated** (gray) — initial authorization pending

If the refresh token itself expires, re-verification (re-authorization) is required.

### Assigning MCP Tools to Agent Roles

1. Navigate to **Settings → Agents**
2. Select an agent role (e.g., Task Planning, Task Implementation)
3. In the **Assigned MCP Tools** section, click **Add Tools**
4. Select tools from the available MCP servers
5. Save configuration

Background agents support the same assignment via **Settings → Background Agents → [agent] → Assigned MCP Tools**.

### Runtime Integration

When an agent with assigned MCP tools executes:

1. `MCPToolFactory` creates PydanticAI tool instances from the assigned `MCPTool` records
2. MCP server connections are established as an async context
3. Tools are available alongside the role's built-in tools
4. Connections are cleaned up after execution

**Note**: MCP tool assignment is only available for agents using the **INTERNAL** (PydanticAI) engine. Claude Code manages its own MCP configuration separately (via its own config file).

### Implementation Details

**Key classes**:
- `MCPToolFactory` (`backend/devboard/mcp/mcp_tool_factory.py`): creates PydanticAI tools from `MCPTool` records
- `MCPServerConfig` (`backend/devboard/db/models/mcp_server.py`): server configuration model
- `MCPTool` (`backend/devboard/db/models/mcp_server.py`): discovered tool record (name, description, input schema)
- `MCPLifecycleManager`: manages async client/session lifecycle with event-based setup/teardown
- `MCPService`: CRUD, verification, and OAuth status management

---

## DevBoard as an MCP Server

DevBoard exposes its own MCP endpoint so external AI clients (e.g., Claude Desktop) can query projects, tasks, and codebases.

**Endpoint**: `http://localhost:8000/mcp` (Streamable HTTP transport)

### Available Tools

| Tool | Description |
|------|-------------|
| `get_projects()` | List all projects |
| `get_tasks(project_id?)` | List tasks, optionally filtered by project |
| `create_task(title, description, project_id?)` | Create a new task |
| `get_codebase_info(codebase_id)` | Get codebase details |

### Resources

| URI Pattern | Description |
|-------------|-------------|
| `devboard://project/{project_id}` | Project resource |
| `devboard://task/{task_id}` | Task resource |

### Connecting

Add DevBoard to any MCP-compatible client using the Streamable HTTP transport URL:

```
http://localhost:8000/mcp
```

---

## Related Sections

- **[AI Agents - Configuration](../4-ai-agents/configuration.md)**: Agent MCP tool assignment
- **[AI Agents - Background Agents](../4-ai-agents/background-agents.md)**: MCP tools in background agents
- **[AI Agents - Tools](../4-ai-agents/tools-and-capabilities.md)**: Tool system overview
- **[Features - Configuration System](../2-features/configuration-system.md)**: Integration configuration UI

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
