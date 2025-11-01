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

**ProjectQARole**: edit_project_specification, search_codebase, read_codebase_files

**TaskSpecificationRole**: edit_task_specification, set_task_specification_content, search_codebase, read_codebase_files

**TaskPlanningRole**: edit_implementation_plan, set_implementation_plan_content, search_codebase, read_codebase_files, execute_shell_command

**TaskImplementationRole**: search_codebase, read_codebase_files, execute_shell_command

## Files

**Definitions**: `backend/devboard/agents/tools.py`

**Virtual System**: `backend/devboard/agents/engines/claude_code/{virtual_tools.py, message_parser.py}`

**Services**: `backend/devboard/services/{document_editor.py, codebase_search.py, resource_service.py}`
