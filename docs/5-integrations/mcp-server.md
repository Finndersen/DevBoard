# MCP Server

**Navigation**: [Documentation Home](../INDEX.md) > [Integrations](./INDEX.md) > MCP Server

## Purpose

The MCP (Model Context Protocol) server allows DevBoard to act as a tool and resource provider for AI clients, enabling external AI assistants to interact with DevBoard's project management, task tracking, and codebase features through a standardized protocol.

## Overview

DevBoard implements an MCP server using the FastMCP framework, providing HTTP-based access via Server-Sent Events (SSE) and Streamable HTTP transports. This allows AI clients (such as Claude Desktop, custom AI agents, or other MCP-compatible applications) to:

- Query projects and tasks
- Create and manage tasks
- Access codebase information
- Retrieve project resources
- Use AI prompts for project planning and task management

**Location**: `backend/devboard/mcp/`

## Architecture

### FastMCP Integration

The MCP server is built using the official [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk) with FastMCP integration. It integrates seamlessly with our FastAPI backend, providing:

- **Streamable HTTP Transport**: Uses the current MCP standard transport (SSE is legacy and not supported)
- **Type Safety**: Leverages Python type hints for automatic schema generation
- **Easy Tool Definition**: Decorator-based API for defining tools, resources, and prompts
- **Production Ready**: Official Anthropic implementation with robust error handling

### HTTP Endpoints

The MCP server is mounted at `/mcp` using Streamable HTTP transport:

| Endpoint | Transport | Description |
|----------|-----------|-------------|
| `/mcp` | Streamable HTTP | Current MCP standard transport |

## MCP Capabilities

### Tools

Tools are functions that AI clients can invoke to perform actions in DevBoard. The server provides scaffolding for the following tools:

#### `get_projects()`
Get a list of all projects in DevBoard.

```python
@mcp.tool()
async def get_projects() -> dict[str, Any]:
    """Get a list of all projects in DevBoard."""
```

#### `get_tasks(project_id: str | None = None)`
Get a list of tasks, optionally filtered by project.

```python
@mcp.tool()
async def get_tasks(project_id: str | None = None) -> dict[str, Any]:
    """Get a list of tasks, optionally filtered by project."""
```

#### `create_task(title: str, description: str, project_id: str | None = None)`
Create a new task in DevBoard.

```python
@mcp.tool()
async def create_task(
    title: str,
    description: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Create a new task in DevBoard."""
```

#### `get_codebase_info(codebase_id: str)`
Get information about a codebase.

```python
@mcp.tool()
async def get_codebase_info(codebase_id: str) -> dict[str, Any]:
    """Get information about a codebase."""
```

### Resources

Resources provide AI clients with access to DevBoard entities using URI-based addressing.

#### Project Resource
URI pattern: `devboard://project/{project_id}`

```python
@mcp.resource("devboard://project/{project_id}")
async def get_project_resource(project_id: str) -> str:
    """Get a project as an MCP resource."""
```

#### Task Resource
URI pattern: `devboard://task/{task_id}`

```python
@mcp.resource("devboard://task/{task_id}")
async def get_task_resource(task_id: str) -> str:
    """Get a task as an MCP resource."""
```

### Prompts

Prompts are templates that help AI clients interact with DevBoard in contextually appropriate ways.

#### `project_overview_prompt(project_id: str)`
Generate a prompt for getting a project overview.

```python
@mcp.prompt()
async def project_overview_prompt(project_id: str) -> str:
    """Generate a prompt for getting a project overview."""
```

#### `task_planning_prompt(task_description: str)`
Generate a prompt for planning a new task.

```python
@mcp.prompt()
async def task_planning_prompt(task_description: str) -> str:
    """Generate a prompt for planning a new task."""
```

## Adding New Tools

To add a new tool to the MCP server:

1. **Define the tool function** in `backend/devboard/mcp/server.py`:

```python
@mcp.tool()
async def your_tool_name(param1: str, param2: int = 0) -> dict[str, Any]:
    """Description of what your tool does.

    Args:
        param1: Description of param1.
        param2: Description of param2 (optional).

    Returns:
        A dictionary containing the tool result.
    """
    # TODO: Implement your tool logic here
    return {"result": "your data"}
```

2. **Type annotations are required** - FastMCP uses them to generate the tool schema
3. **Docstrings are important** - They become the tool description for AI clients
4. **Return structured data** - Use dictionaries or Pydantic models for responses

## Adding New Resources

To add a new resource:

```python
@mcp.resource("devboard://your-resource/{resource_id}")
async def get_your_resource(resource_id: str) -> str:
    """Get a resource as an MCP resource.

    Args:
        resource_id: The ID of the resource to retrieve.

    Returns:
        A string representation of the resource.
    """
    # TODO: Implement resource retrieval
    return f"Resource {resource_id} data"
```

## Adding New Prompts

To add a new prompt template:

```python
@mcp.prompt()
async def your_prompt_name(param: str) -> str:
    """Generate a prompt for a specific task.

    Args:
        param: The parameter for the prompt.

    Returns:
        A formatted prompt for AI assistants.
    """
    return f"""Your prompt template here with {param}

    Include instructions and context for the AI assistant.
    """
```

## Implementation Status

The MCP server scaffolding is complete with the following implementation status:

- ✅ Official MCP SDK integration with FastAPI
- ✅ Streamable HTTP transport endpoint
- ✅ Tool, resource, and prompt scaffolding
- 🚧 Database integration for tools (TODO)
- 🚧 Authentication/authorization (TODO)
- 🚧 Rate limiting (TODO)

## Testing the MCP Server

### Check Server Status

You can verify the server is running by checking the main API health endpoint:

```bash
curl http://localhost:8000/health
```

### Connect with MCP Client

The server can be accessed by any MCP-compatible client using the Streamable HTTP transport at:

```
http://localhost:8000/mcp
```

## Dependencies

- **mcp** (>=1.0.0): Official Model Context Protocol Python SDK
- **fastapi** (>=0.118.0): Web framework for HTTP endpoints
- **uvicorn** (>=0.24.0): ASGI server for running FastAPI

## Configuration

The MCP server uses the same FastAPI configuration as the rest of DevBoard:

- **CORS**: Configured to allow connections from frontend origins
- **Logging**: Integrated with DevBoard's Logfire logging
- **Port**: Runs on the same port as the main FastAPI application (default: 8000)

## Security Considerations

### Authentication (To Be Implemented)

Future enhancements should include:
- API key authentication for MCP clients
- Token-based authentication
- Rate limiting per client
- Access control for sensitive operations

### Authorization (To Be Implemented)

- Tool-level permissions
- Resource access control
- Audit logging of MCP operations

## MCP Client Integration

In addition to acting as an MCP server, DevBoard can also connect to external MCP servers as a client, allowing its AI agents to use tools provided by those servers.

### Configuring External MCP Servers

1. Navigate to Settings → Integrations → MCP Servers
2. Add server configuration (name, server type, connection details)
3. Click "Verify" to test connection and discover available tools
4. Tools are stored in the database for assignment to agent roles

### Assigning MCP Tools to Agents

1. Navigate to Settings → Agents
2. Select an agent role (e.g., Project, Task Planning)
3. In the "Assigned MCP Tools" section, click "Add Tools"
4. Select tools from available MCP servers
5. Save configuration

### Runtime Integration

When an agent with assigned MCP tools executes:
1. `MCPToolFactory` creates tool instances from the assigned `MCPTool` records
2. Server connections are established as an async context
3. Tools are available alongside built-in role tools
4. Connections are cleaned up after execution

**Note**: MCP client integration is only supported for agents using the INTERNAL (PydanticAI) engine. Claude Code manages its own MCP configuration externally.

### Implementation Details

**Location**: `backend/devboard/mcp/mcp_tool_factory.py`

**Key Classes**:
- `MCPToolFactory`: Creates PydanticAI tools from MCPTool database records
- `MCPServerConfig`: Database model for server configuration
- `MCPTool`: Database model for discovered tools

## Related Sections

- **[Features - Configuration System](../2-features/configuration-system.md)**: Integration configuration
- **[AI Agents - Configuration](../4-ai-agents/configuration.md)**: Agent MCP tool assignment
- **[AI Agents - Tools](../4-ai-agents/tools-and-capabilities.md)**: Tool system overview
- **[Architecture - API Structure](../3-architecture/backend/api-structure.md)**: API design patterns
- **[Development - Testing](../6-development/testing.md)**: Testing strategies

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [FastMCP GitHub Repository](https://github.com/jlowin/fastmcp)
