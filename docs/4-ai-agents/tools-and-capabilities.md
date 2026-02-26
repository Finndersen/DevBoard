# Tools and Capabilities

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Tools and Capabilities

**Purpose**: Specialized tools (document editing, codebase analysis, shell commands) defined once, auto-converted per engine

**Location**: `backend/devboard/agents/tools.py`

**Pattern**: PydanticAI `Tool` → INTERNAL (native) or CLAUDE_CODE (VirtualTools if `requires_approval=True`)

## Tools

### Document Editing

**edit_task_specification**: Find-and-replace in task spec. Approval required. Params: `old_string`, `new_string`. Used by: TaskSpecificationRole

**set_task_specification_content**: Full replacement. Approval required. Params: `content`. Used by: TaskSpecificationRole

**edit_implementation_plan**: Find-and-replace in plan. Approval required. Params: `old_string`, `new_string`. Used by: TaskPlanningRole

**set_implementation_plan_content**: Full replacement. Approval required. Params: `content`. Used by: TaskPlanningRole

**edit_project_specification**: Find-and-replace in project spec. Approval required. Params: `old_string`, `new_string`. Used by: ProjectQARole

### Visualization

**render_html**: Render HTML content in a sandboxed iframe modal. No approval (display-only). Params: `title` (string), `html` (complete HTML document). Used by: ProjectQARole

Enables agents to generate rich visualizations like dashboards, charts, styled tables, and interactive diagrams. The HTML is rendered in a sandboxed iframe that can execute JavaScript and load external CDN libraries (e.g., Chart.js, D3.js, Plotly) but cannot access the parent page (no `allow-same-origin` sandbox policy).

### Task Query Tools

**list_tasks**: List tasks belonging to the current project with optional filtering. No approval (read-only). Params: `status_filter` (list of status values), `created_after` (ISO date), `created_before` (ISO date), `codebase_name`. Used by: ProjectQARole

**view_task_details**: View detailed information about a specific task including metadata and optional document contents. No approval (read-only). Params: `task_id`, `include_documents` (list: specification, implementation_plan, change_summary). Used by: ProjectQARole

**create_task**: Create a new task within the current project. No approval. Params: `title`, `codebase_name`, `specification_content`, `base_branch`, `branch_name`, `custom_fields`. Used by: ProjectQARole, TaskPlanningRole, TaskImplementationRole, TaskPRReviewRole

### Codebase Analysis

**search_codebase**: Semantic search via embeddings. No approval (read-only). Params: `query`, `codebase_id`. Used by: All roles

**read_codebase_files**: Read by path. No approval (read-only). Params: `file_paths`, `codebase_id`. Used by: All roles

### Shell Commands

**execute_shell_command**: Execute with approval. Approval required. Params: `command`. Used by: TaskPlanningRole, TaskImplementationRole

## Approval Workflow

**Trigger**: Tools with `requires_approval=True`

**Flow**:
1. Agent proposes tool use
2. User reviews (tool + arguments + context)
3. User approves/denies/modifies
4. Execute approved tools
5. Return results to agent

**Engine-Specific**:
- **InternalAgent**: Defers execution → ToolCall events → approval → ToolResult events
- **ClaudeCodeAgent**: Converts to VirtualTools → JSON requests → validation → approval → execution → XML results

## Virtual Tool Calling (Claude Code)

**Location**: `backend/devboard/agents/engines/claude_code/virtual_tools.py`

**VirtualTool Base**: `tool_name`, `description`, `args_model` (Pydantic), `execute(args)`

**Schema Generation**: `build_tool_schemas_section()` for system prompt

**Request Format**:
```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "old_string": "existing text",
    "new_string": "replacement text"
  }
}
```

**Validation**:
- Structure: JSON matches VirtualToolCall schema
- Tool: Exists in registered virtual tools
- Arguments: Pass tool's Pydantic schema

**Auto-Retry**: Invalid → retry with error feedback (max 3)

## Tool Execution

**Document Editing** (`backend/devboard/services/document_editor.py`):
- Content hashing for conflict detection
- Atomic edits
- Rollback capabilities
- Edit history

**Codebase Search** (`backend/devboard/services/codebase_search.py`):
- Vector embeddings for semantic search
- File content retrieval
- Path-based access
- Git integration

**Shell Commands**: Validation, output capture, error handling, timeout protection, user approval required

## Tool Registration by Role

**ProjectQARole**: edit_project_specification, render_html, list_tasks, view_task_details, create_task, search_codebase, read_codebase_files

**TaskSpecificationRole**: edit_task_specification, set_task_specification_content, search_codebase, read_codebase_files

**TaskPlanningRole**: edit_implementation_plan, set_implementation_plan_content, create_task, search_codebase, read_codebase_files, execute_shell_command

**TaskImplementationRole**: create_task, search_codebase, read_codebase_files, execute_shell_command

**TaskPRReviewRole**: create_task, get_pr_feedback, merge_pr_and_complete_task

## MCP Tool Integration

In addition to built-in tools, agents can use external tools from configured MCP (Model Context Protocol) servers.

### Overview

MCP tools are discovered from configured MCP servers and can be assigned to specific agent roles. This allows extending agent capabilities with external services like GitHub, Jira, Datadog, and custom tools.

### Configuration

1. Configure MCP servers in Settings → Integrations → MCP Servers
2. Verify server connection to discover available tools
3. Assign specific tools to agent roles in Settings → Agents

### Runtime Behavior

When an agent using the INTERNAL engine executes:

1. `AgentConfigService.get_enabled_mcp_tools()` retrieves assigned tools
2. `MCPToolFactory` creates PydanticAI tool instances from MCPTool records
3. MCP server connections are established as an async context manager
4. Tools are combined with role-defined tools during execution
5. Connections are cleaned up after execution completes

### MCPToolFactory

**Location**: `backend/devboard/mcp/mcp_tool_factory.py`

The factory handles:
- Deduplication of server connections (one connection per unique server)
- Tool name filtering (only initialize tools that are actually assigned)
- Async context management for server lifecycle
- PydanticAI tool wrapper creation with proper schema conversion

### Engine Support

| Engine | MCP Tool Support |
|--------|------------------|
| INTERNAL | ✅ Full support |
| CLAUDE_CODE | ❌ Manages own MCP config |
| GEMINI_CLI | ❌ Not supported |

### Error Handling

MCP tool errors are converted to `ModelRetry` exceptions, allowing the agent to retry with feedback about what went wrong.

## Files

**Built-in Tools**: `backend/devboard/agents/tools.py`

**Virtual System**: `backend/devboard/agents/engines/claude_code/{virtual_tools.py, message_parser.py}`

**MCP Integration**: `backend/devboard/mcp/mcp_tool_factory.py`

**Services**: `backend/devboard/services/{document_editor.py, codebase_search.py, resource_service.py}`
