# Agent Configuration

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Configuration

## Overview

Agent configuration in DevBoard is managed through a dedicated database-backed system that supports:
- Per-role engine and model selection
- Custom user instructions appended to base system prompts
- MCP (Model Context Protocol) tool assignments per agent role

**Location**: `backend/devboard/agents/agent_config_service.py`, `backend/devboard/db/models/agent_role_config.py`

## Core Architecture

### Agent Roles

**Enum**: `AgentRoleType` (in `backend/devboard/agents/roles/role_types.py`)

| Role | Purpose |
|------|---------|
| PROJECT | Project-level Q&A and management |
| TASK_PLANNING | Task specification and implementation planning |
| TASK_IMPLEMENTATION | Code implementation with Claude Code |
| TASK_PR_REVIEW | Pull request review and feedback |
| INVESTIGATION | Research and analysis tasks |

### Agent Engines

**Enum**: `AgentEngine` (in `backend/devboard/agents/engines/__init__.py`)

| Engine | Description | Model Selection |
|--------|-------------|-----------------|
| INTERNAL | PydanticAI-based with tool approval workflow | Required |
| CLAUDE_CODE | Claude CLI with external session management | Optional (uses CLI default) |
| GEMINI_CLI | Google Gemini CLI integration | Optional (uses CLI default) |

### Role-Engine Restrictions

Not all engines are available for all roles:

| Role | Allowed Engines |
|------|-----------------|
| PROJECT | INTERNAL only |
| TASK_PLANNING | INTERNAL, CLAUDE_CODE |
| TASK_IMPLEMENTATION | CLAUDE_CODE, GEMINI_CLI |
| TASK_PR_REVIEW | CLAUDE_CODE |
| INVESTIGATION | INTERNAL only |

## Database Model

### AgentRoleConfig

**Location**: `backend/devboard/db/models/agent_role_config.py`

Stores per-role configuration with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `role` | AgentRoleType | Unique - one config per role |
| `engine` | AgentEngine (nullable) | Selected engine (null = use default) |
| `model_id` | str (nullable) | Selected model identifier (e.g., "anthropic:claude-sonnet-4.5") |
| `custom_instructions` | text (nullable) | User-defined instructions appended to base system prompt |
| `enabled_mcp_tools` | relationship | Many-to-many with MCPTool |

### Junction Table: agent_role_config_mcp_tools

Associates MCP tools with agent roles:

| Field | Type | Description |
|-------|------|-------------|
| `agent_role_config_id` | FK | References AgentRoleConfig.id |
| `mcp_tool_id` | FK | References MCPTool.id |

- Cascade delete from both sides
- Unique constraint on (agent_role_config_id, mcp_tool_id)

## Configuration Service

**Location**: `backend/devboard/agents/agent_config_service.py`

### AgentConfigService

The central service for agent configuration with the following key methods:

#### Configuration Resolution

**`get_effective_config(role: AgentRoleType) -> AgentEngineModelConfig`**

Resolution hierarchy:
1. Database config (AgentRoleConfig)
2. Default engine for role
3. Default model for role+engine combination

**`get_or_create(role: AgentRoleType) -> AgentRoleConfig`**

Get-or-create pattern ensures configuration is always available on first access.

#### Configuration Updates

**`update_agent_configuration(role, engine, model_id) -> AgentRoleConfig`**

Validates:
1. Engine is allowed for the role
2. Model requirements (None only if engine doesn't require selection)
3. Model is available for the selected engine
4. INTERNAL engine requires explicit model_id

**`update_custom_instructions(role, instructions) -> AgentRoleConfig`**

Updates the custom instructions for a role.

#### MCP Tool Management

**`add_mcp_tool(role, tool_id) -> AgentRoleConfig`**

Assigns an MCP tool to an agent role.

**`remove_mcp_tool(role, tool_id) -> AgentRoleConfig`**

Removes an MCP tool from an agent role.

**`get_enabled_mcp_tools(role) -> list[MCPTool]`**

Returns all MCP tools enabled for the given role.

**`get_custom_instructions(role) -> str | None`**

Returns custom instructions for the role, or None if not set.

## Custom Instructions

Custom instructions allow users to augment agent behavior without modifying core system prompts.

### How It Works

1. Base system prompts remain as code constants (e.g., `PLANNING_ROLE_PROMPT`)
2. Custom instructions are appended with a separator: `"\n\n## Additional Instructions\n\n"`
3. The combined prompt is used during agent execution

### Use Cases

- Project-specific coding standards
- Team conventions and preferences
- Domain-specific terminology or constraints
- Additional safety or review requirements

## MCP Tool Integration

Agents can be configured to use external MCP (Model Context Protocol) tools from configured MCP servers.

### Configuration Flow

1. Configure MCP servers in Settings → Integrations → MCP Servers
2. Verify server connection to discover available tools
3. Assign specific tools to agent roles in Settings → Agents

### Runtime Integration

When an agent executes:
1. The execution service loads enabled MCP tools for the role
2. `MCPToolFactory` creates PydanticAI tool instances from MCPTool records
3. MCP server connections are established as an async context
4. Tools are available alongside role-defined tools during execution
5. Connections are cleaned up after execution completes

### Engine Support

| Engine | MCP Tool Support |
|--------|------------------|
| INTERNAL | ✅ Full support via MCPToolFactory |
| CLAUDE_CODE | ❌ Not supported (manages own MCP config) |
| GEMINI_CLI | ❌ Not supported |

**Note**: Claude Code manages its own MCP server configuration externally. The MCP tools configured in DevBoard are only available to agents using the INTERNAL engine.

## API Endpoints

**Base**: `/api/agents`

### Configuration Endpoints

```
GET    /api/agents/{role}/configuration     Get full config including tools
PUT    /api/agents/{role}/configuration     Update engine, model, custom_instructions
```

### MCP Tool Endpoints

```
GET    /api/agents/{role}/tools             List assigned MCP tools for role
POST   /api/agents/{role}/tools             Add MCP tool to role
DELETE /api/agents/{role}/tools/{tool_id}   Remove MCP tool from role
```

### Response Schemas

**AgentConfigurationResponse**:
```json
{
  "current_config": {
    "engine": "INTERNAL",
    "model_id": "anthropic:claude-sonnet-4.5"
  },
  "custom_instructions": "Always use TypeScript for frontend code.",
  "available_engines": [...],
  "available_models": [...]
}
```

**MCPToolSummary**:
```json
{
  "tool_id": 1,
  "server_name": "github-mcp",
  "tool_name": "search_code",
  "description": "Search for code patterns in repositories"
}
```

## Model Selection

### Model Catalog

**Location**: `backend/devboard/agents/language_models.py`

Available models by provider:

| Provider | Models |
|----------|--------|
| Anthropic | Claude Sonnet 4.5, Claude Opus 4.1, Claude Haiku 3.7 |
| OpenAI | GPT-5, GPT-4o, o1-preview, o1-mini |
| Google | Gemini 2.5 Pro, Gemini 2.5 Flash |

### Recommended Model Types by Role

| Role | Recommended Type | Reason |
|------|-----------------|--------|
| PROJECT | REASONING | Complex project analysis |
| TASK_PLANNING | REASONING | Detailed planning decisions |
| TASK_IMPLEMENTATION | (uses CLI default) | Engine manages selection |
| INVESTIGATION | FAST | Quick research queries |

### Model Filtering

For INTERNAL engine, available models are filtered by configured API keys. External engines (CLAUDE_CODE, GEMINI_CLI) show all provider models since they manage credentials externally.

## Files

**Core**:
- `backend/devboard/agents/agent_config_service.py` - Configuration service
- `backend/devboard/db/models/agent_role_config.py` - Database model
- `backend/devboard/db/repositories/agent_role_config.py` - Repository

**Supporting**:
- `backend/devboard/agents/agent_engines.py` - Engine definitions
- `backend/devboard/agents/language_models.py` - Model catalog
- `backend/devboard/mcp/mcp_tool_factory.py` - MCP tool integration

**API**:
- `backend/devboard/api/routers/agents.py` - API endpoints
- `backend/devboard/api/schemas/agents.py` - Request/response schemas
