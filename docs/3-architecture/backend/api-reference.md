# Backend API Reference

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Backend](./INDEX.md) > API Reference

## Overview

Complete API endpoint reference. Base URL: `http://localhost:8000/api`

Implementation: `backend/devboard/api/routes/`

## Health Check

- `GET /` - Root health check
- `GET /health` - Detailed health with database status

## Projects API

**Base**: `/api/projects`
**Router**: `backend/devboard/api/routes/projects.py`

```
GET    /api/projects/                    List all projects
POST   /api/projects/                    Create project
GET    /api/projects/{id}                Get project details
PATCH  /api/projects/{id}                Update project
DELETE /api/projects/{id}                Delete project (cascades to tasks)
GET    /api/projects/{id}/tasks          List project tasks
GET    /api/projects/{id}/resources      List linked context provider resources
POST   /api/projects/{id}/resources      Link resource to project
DELETE /api/projects/{id}/resources/{id} Unlink resource
```

**Key Schemas**: `ProjectResponse`, `ProjectCreate`, `ProjectUpdate` (`backend/devboard/schemas/`)

## Tasks API

**Base**: `/api/tasks`
**Router**: `backend/devboard/api/routes/tasks.py`

```
GET    /api/tasks/                       List all tasks
POST   /api/tasks/                       Create task
GET    /api/tasks/{id}                   Get task details
PATCH  /api/tasks/{id}                   Update task
DELETE /api/tasks/{id}                   Delete task
POST   /api/tasks/{id}/state-transition  Trigger state transition with optional AI
POST   /api/tasks/{id}/workflow-action   Execute workflow action (returns conversation_id or status)
GET    /api/tasks/{id}/diff              Get git diff of uncommitted changes
GET    /api/tasks/{id}/resources         List task-linked resources
POST   /api/tasks/{id}/resources         Link resource to task
DELETE /api/tasks/{id}/resources/{id}    Unlink resource from task
```

**State Flow**: `DEFINING -> DESIGNING -> PLANNING -> IMPLEMENTING -> IN_REVIEW -> COMPLETE`

**State Transition**: Can optionally use agent (`use_agent: true`) to execute transition logic automatically.

**Git Diff Endpoint**: Returns structured diff data for all uncommitted changes in the task's associated codebase:
- Requires task to have a linked codebase (`codebase_id`)
- Returns per-file diffs with syntax-highlightable content
- Includes statistics (additions/deletions per file and totals)
- Generated timestamp for tracking freshness

**Key Schemas**: `TaskResponse`, `TaskCreate`, `TaskUpdate`, `StateTransitionRequest`, `TaskDiffResponse`, `FileDiff`

## Conversations API

**Base**: `/api/conversations`
**Router**: `backend/devboard/api/routers/conversations.py`

**Unified Interface**: All entity conversations (projects, tasks, codebases) share these endpoints.

```
GET    /api/conversations/{id}                  Get conversation details
GET    /api/conversations/{id}/messages         Get message history as event list
POST   /api/conversations/{id}/messages         Send message — starts background execution, returns {"conversation_id": id}
POST   /api/conversations/{id}/approve-tools    Submit tool approvals — resumes background execution, returns {"conversation_id": id}
GET    /api/conversations/{id}/ws               WebSocket for event consumption (server→client only)
POST   /api/conversations/{id}/interrupt        Request graceful interruption of active execution
PUT    /api/conversations/{id}/model            Update conversation model
POST   /api/conversations/{id}/reset            Reset conversation (delete + recreate)
```

**Background Task Architecture**: `POST /messages` and `POST /approve-tools` start/resume a background asyncio task and return immediately. Clients consume events via WebSocket (`GET /ws`). See [Frontend Streaming Architecture](../frontend/streaming.md) for full details.

**409 Conflict**: If a background execution is already active for a conversation, `POST /messages` and `POST /approve-tools` return HTTP 409.

**Event-Based Architecture**: WebSocket delivers `ConversationEvent` objects. Types: `ConversationMessage`, `ToolCall`, `ToolResult`, `ToolCallRequest`, `SystemEvent`. Plus execution lifecycle events (`execution_started`, `execution_completed`).

**Tool Approval**: When tools require approval, agent pauses and returns `ToolCallRequest` events. Frontend approves/denies via `/approve-tools`.

**Workflow Actions**: Reusable, named operations that perform optional procedural steps (state transitions, DB changes) and return either a prompt string to start an agent run or `None`. Executed via `/workflow-action` endpoint. Returns `{"conversation_id": N}` if agent started, `{"status": "completed"}` otherwise. Returns 400 if action validation fails. Examples: `task.create_implementation_plan`, `task.begin_implementation`, `task.finalise`.

**Key Schemas**: `ChatRequest`, `ConversationEvent`, `ToolApprovalRequest`, `ToolApprovalDecision`, `PromptActionRequest`, `UpdateConversationModelRequest`

## Codebases API

**Base**: `/api/codebases`
**Router**: `backend/devboard/api/routes/codebases.py`

```
GET    /api/codebases/                                      List codebases
POST   /api/codebases/                                      Register codebase
GET    /api/codebases/{id}                                  Get codebase details
PATCH  /api/codebases/{id}                                  Update codebase
DELETE /api/codebases/{id}                                  Delete codebase
GET    /api/codebases/{id}/architecture_document            Get architecture doc
PUT    /api/codebases/{id}/architecture_document            Update doc (conflict detection)
POST   /api/codebases/{id}/architecture_document/generate   Generate/update doc with AI
```

**Architecture Document**: Stored at `{local_path}/.devboard/architecture.md`. PUT endpoint uses `original_hash` for optimistic locking (returns 409 on conflict).

**Key Schemas**: `CodebaseResponse`, `CodebaseCreate`, `ArchitectureDocumentResponse`, `ArchitectureUpdateRequest`

## Configurations API

**Base**: `/api/configurations`
**Router**: `backend/devboard/api/routes/configurations.py`

```
GET    /api/configurations/                  List configs (optional ?prefix filter)
GET    /api/configurations/{key}             Get config
GET    /api/configurations/{key}/detail      Get config with field sources
POST   /api/configurations/                  Create/update config
PATCH  /api/configurations/{key}             Update config
PATCH  /api/configurations/{key}/fields      Update specific fields
DELETE /api/configurations/{key}             Delete config
```

**Three-Layer System**: Environment variables override database values, which override defaults. `/detail` shows source per field.

**Key Pattern**: Dot notation keys (e.g., `agents.task_planner.provider`). See [Configuration System](../../2-features/configuration-system.md).

**Key Schemas**: `ConfigurationResponse`, `ConfigurationDetailResponse`, `ConfigurationFieldInfo`

## Agents API

**Base**: `/api/agents`
**Router**: `backend/devboard/api/routers/agents.py`

```
GET    /api/agents/{role}/configuration          Get full config including custom instructions and tools
PUT    /api/agents/{role}/configuration          Update engine, model, and custom_instructions
GET    /api/agents/{role}/tools                  List assigned MCP tools for role
POST   /api/agents/{role}/tools                  Add MCP tool to role
DELETE /api/agents/{role}/tools/{tool_id}        Remove MCP tool from role
GET    /api/agents/available-models              Get models by engine
GET    /api/agents/available-mcp-tools           Get all MCP tools from verified servers
```

**Role Values**: `project`, `task_planning`, `task_implementation`, `task_pr_review`, `investigation`

**Configuration Response**: Returns current config (engine, model_id), custom_instructions, available engines with metadata, and enabled_mcp_tools list.

**MCP Tool Assignment**: Tools are assigned by tool_id (FK to MCPTool). Only tools from verified MCP servers can be assigned.

**Key Schemas**: `AgentConfigurationResponse`, `UpdateAgentConfigurationRequest`, `MCPToolSummary`, `AddMCPToolRequest`

## Error Handling

**Standard Format**:
```typescript
{
  error: string      // Error type
  message: string    // Description
  path: string       // Request path
}
```

**Common Status Codes**: 400 (invalid input), 404 (not found), 409 (conflict), 500 (server error)

## Implementation Notes

**CRUD Pattern**: Most endpoints follow standard CRUD with SQLAlchemy models (`backend/devboard/models/`).

**Dependency Injection**: Routes use FastAPI dependencies for database sessions (`get_db`) and services.

**Validation**: Pydantic schemas in `backend/devboard/schemas/` handle validation.
