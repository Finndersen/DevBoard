# Tools and Capabilities

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Tools and Capabilities

**Purpose**: Specialized tools (document editing, codebase analysis, shell commands) defined once, auto-converted per engine

**Location**: `backend/devboard/agents/tools.py`

**Pattern**: PydanticAI `Tool` → INTERNAL (native) or CLAUDE_CODE (VirtualTools if `requires_approval=True`)

## Tools

### Document Editing

**edit_task_specification**: Find-and-replace in task spec. Approval required. Params: `old_string`, `new_string`. Used by: TaskSpecificationRole

**set_task_specification_content**: Full replacement. Approval required. Params: `content`. Used by: TaskSpecificationRole

### Implementation Plan Editing

**set_implementation_plan_steps**: Bulk creation/replacement of structured implementation plan steps. No approval. Params: `overview` (optional str), `steps` (ordered list of `{title, type, dependencies, details}`). Step numbers auto-assigned from array position (1-indexed). Validates dependency graph (no cycles, valid references). Replaces existing plan if called again. Used by: TaskPlanningRole

**add_implementation_step**: Add a single step to existing plan (step_number = max + 1). No approval. Params: `title`, `type`, `dependencies`, `details`. Used by: TaskPlanningRole

**edit_implementation_step**: Edit a single step's fields by step_number. No approval. Params: `step_number`, optional `title`, `type`, `dependencies`, `details`. Used by: TaskPlanningRole

**remove_implementation_step**: Remove a step by step_number. Validates no other steps depend on it. No approval. Params: `step_number`. Used by: TaskPlanningRole

**edit_implementation_plan_overview**: Edit the plan overview text. No approval. Params: `overview`. Used by: TaskPlanningRole

**read_implementation_step_details**: Read the full details/instructions of a specific implementation plan step. No approval (read-only). Params: `step_number` (int). Used by: TaskPlanningRole, TaskImplementationRole

**edit_project_specification**: Find-and-replace in project spec. Approval required. Params: `old_string`, `new_string`. Used by: ProjectQARole

### Visualization

**render_html**: Render HTML content in a sandboxed iframe modal. No approval (display-only). Params: `title` (string), `html` (complete HTML document). Used by: ProjectQARole

Enables agents to generate rich visualizations like dashboards, charts, styled tables, and interactive diagrams. The HTML is rendered in a sandboxed iframe that can execute JavaScript and load external CDN libraries (e.g., Chart.js, D3.js, Plotly) but cannot access the parent page (no `allow-same-origin` sandbox policy).

### Task Query Tools

**list_tasks**: List tasks belonging to the current project with optional filtering. No approval (read-only). Params: `status_filter` (list of status values), `created_after` (ISO date), `created_before` (ISO date), `codebase_name`. Returns TOON-encoded records with fields: `id`, `title`, `status`, `created_at`, `codebase`, `branch`, `agent_running` (bool — whether the task's planning agent is currently executing), `custom_fields`. Used by: ProjectQARole

**view_task_details**: View detailed information about a specific task including metadata and optional document contents. No approval (read-only). Params: `task_id`, `include_documents` (list: specification, implementation_plan, change_summary). Response metadata includes `Agent running: yes/no` line indicating whether the task's agent is currently executing. Used by: ProjectQARole

**create_task**: Create a new task within the current project. No approval. Params: `title`, `codebase_name`, `specification_content`, `base_branch`, `branch_name`, `custom_fields`, `initial_prompt` (optional — launches autonomous agent execution immediately). Response JSON includes `agent_running: true` when `initial_prompt` was provided and execution started successfully. Used by: ProjectQARole, TaskPlanningRole, TaskImplementationRole, TaskPRReviewRole

**edit_task**: Edit metadata fields (title, custom fields) and/or specification content of an existing task. Response JSON includes `agent_running` (bool) reflecting whether the task's agent is currently executing at the time of the edit. Used by: ProjectQARole

### GitHub PR Tools

**get_pr_status**: Fetch current PR status in a single GraphQL call. No approval (read-only). No params (PR number and repo URL come from task context). Returns PR state, mergeable status, CI rollup, review decision, and comment count hint. Used by: TaskPRReviewRole

**get_pr_feedback**: Fetch all PR reviews and code comments. No approval (read-only). No params. Returns comprehensive feedback including reviews with their associated code comment threads and standalone comments. Used by: TaskPRReviewRole

### Codebase Management

**view_codebase_details**: View full configuration details of a codebase. No approval (read-only). Params: `codebase_name` (required). Returns JSON with all fields: `id`, `name`, `description`, `repository_url`, `local_path`, `default_branch`, `merge_method`, `branch_handling`, `max_worktrees`, `setup_command`, `developer_context`. Used by: ProjectQARole, TaskPlanningRole, TaskImplementationRole, TaskPRReviewRole

**update_codebase**: Update configuration properties of a codebase. No approval. Params: `codebase_name` (required), `description`, `setup_command`, `developer_context` (at least one required). Only provided fields are updated. Returns JSON with `id`, `name`, and updated field values. Used by: ProjectQARole, TaskPlanningRole, TaskImplementationRole, TaskPRReviewRole

### Codebase Analysis

**search_codebase**: Semantic search via embeddings. No approval (read-only). Params: `query`, `codebase_id`. Used by: All roles

**read_codebase_files**: Read by path. No approval (read-only). Params: `file_paths`, `codebase_id`. Used by: All roles

### Sub-Agent Tools

**investigate_codebase**: Delegates codebase investigation queries to a specialised `CodebaseInvestigationAgentRole` sub-agent. No approval (read-only). Params: `codebase_name` (Literal of available codebases), `query` (specific question), `session_id` (optional, for session resumption). Used by: TaskImplementationRole. Returns JSON `{"result": ..., "session_id": ...}`.

**review_code_changes**: Performs a comprehensive code review of all task changes via a `CodeReviewAgentRole` sub-agent. No approval. No params (context assembled from captured task). Used by: TaskImplementationRole. Evaluates plan alignment, code quality, architecture, test coverage, edge cases, and cross-component impact. Returns JSON `{"result": ..., "session_id": null}`.

**execute_implementation_step**: Delegates execution of a single implementation plan step to a `StepExecutionAgentRole` sub-agent. No approval. Params: `step_number` (int), `force_run` (bool, optional), `notes` (str, optional). Validates step is `pending` or `failed` and all dependency steps are `complete`. Failed steps can be retried. Sets step status to `running`, invokes sub-agent with step details and dependency outcomes as context, then updates status to `complete`/`failed` with outcome. Use `force_run=True` to bypass status and dependency validation for recovery scenarios. Used by: TaskImplementationRole.

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

**ProjectQARole**: edit_project_specification, render_html, list_tasks, view_task_details, create_task, view_codebase_details, update_codebase, investigate_codebase, search_codebase, read_codebase_files (codebase tools only present when project has codebases)

**TaskSpecificationRole**: edit_task_specification, set_task_specification_content, search_codebase, read_codebase_files

**TaskPlanningRole**: set_implementation_plan_steps, add_implementation_step, edit_implementation_step, remove_implementation_step, edit_implementation_plan_overview, read_implementation_step_details, create_task, view_codebase_details, update_codebase, search_codebase, read_codebase_files, execute_shell_command

**TaskImplementationRole**: execute_implementation_step, read_implementation_step_details, create_task, view_codebase_details, update_codebase, search_codebase, read_codebase_files, execute_shell_command

**StepExecutionRole**: search_codebase, read_codebase_files (plus Claude Code engine builtins: Read, Edit, Write, Bash, Grep, Glob, etc.)

**TaskPRReviewRole**: create_task, get_pr_feedback, merge_pr_and_complete_task, view_codebase_details, update_codebase

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

### Tool Name Normalization

When internal PydanticAI tools are provided to the Claude Code engine, they are internally prefixed with `mcp__builtin_tools__` for namespace management within Claude Code CLI. This prefix is **stripped at the engine boundary** before creating tool call events. External MCP server tools keep their full prefixed names.

This means:
- Internal tool events (ToolCall, ToolCallRequest, ToolResult) use canonical tool names
- External MCP tool events keep their prefixed names (e.g., `mcp__github__create_issue`)
- Frontend components use canonical names for internal tools, prefixed names for external tools
- Internal tool names are consistent across all engines (Internal, Claude Code, Gemini)

Example:
```python
# Internal tool
Tool(function=render_html, name="render_html")
"mcp__builtin_tools__render_html"  # Claude Code CLI (internal)
ToolCall(tool_name="render_html")  # DevBoard event (normalized)

# External MCP tool
"mcp__github__create_issue"  # Claude Code CLI (internal)
ToolCall(tool_name="mcp__github__create_issue")  # DevBoard event (keeps prefix)
```

The normalization logic is implemented in `ClaudeClient.normalize_tool_name()` and only strips the `mcp__builtin_tools__` prefix for internal tools.

## Files

**Built-in Tools**: `backend/devboard/agents/tools.py`

**Virtual System**: `backend/devboard/agents/engines/claude_code/{virtual_tools.py, message_parser.py}`

**MCP Integration**: `backend/devboard/mcp/mcp_tool_factory.py`

**Services**: `backend/devboard/services/{document_editor.py, codebase_search.py, resource_service.py}`
