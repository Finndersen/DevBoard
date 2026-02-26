# Claude Code Integration

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Claude Code Integration

**Purpose**: Integrate Anthropic's Claude Code CLI as agent execution engine with virtual tool calling for user approval

## ClaudeCodeAgent

**Location**: `backend/devboard/agents/engines/claude_code/agent.py`

**Construction**:
```python
agent = ClaudeCodeAgent(
    role=TaskPlanningRole(task),  # Defines behavior, tools, context
    model=language_model,          # Optional (None = engine default)
    session_id=session_id          # For conversation continuity
)
```

**System Prompt Building**: Combines role's system prompt + virtual tool schemas + context

**Virtual Tool Conversion**: PydanticAI tools with `requires_approval=True` → VirtualTools

**Response Parsing**: `_parse_claude_result()` converts ResultMessage → `list[ConversationEvent]`

**Retry Logic**: Auto-retry on validation errors (max 3) with detailed feedback

## Session Management

**Storage**: `~/.claude/projects/<normalized-path>/<session-id>.jsonl`

**Path Normalization**: `/Users/name/project` → `-Users-name-project`

**Format**: One JSON per line (message metadata, content, tool interactions)

**Service** (`backend/devboard/agents/engines/claude_code/session.py`):
- `find_session_file(session_id)`: Search all project directories
- `load_session_messages(session_id)`: Complete list of SessionMessage
- `get_last_session_message(session_id)`: Most recent
- `load_todo_list(session_id, include_subagents)`: JSON todos from `~/.claude/todos/`
- `migrate_session_to_directory(session_id, old_working_dir, new_working_dir)`: Migrate session files to new working directory

**SessionMessage**: `uuid`, `timestamp`, `role`, `content`, `tool_calls`, `tool_results`. `text_content` property extracts displayable text

**Content Blocks**: TextBlock, ToolUseBlock, ToolResultBlock

### Session Migration

When a task moves to a different working directory (e.g., from a worktree to the main repository), Claude Code sessions must be migrated to maintain conversation continuity.

**Migration Process** (`migrate_session_to_directory()`):
1. Locate the session JSONL file in the old project directory
2. Create new project directory (path-encoded from new working directory)
3. Move session file and associated session directory (tool results)
4. Perform in-place path replacement using `sed` to update all path references

**Automatic Migration**: `WorkspaceAllocationService` automatically migrates Claude Code sessions when:
- `checkout_task_to_main_repo()`: Moving task from worktree to main repo
- `run_task_agent_in_workspace()`: Slot changes between runs

**Conditions**: Migration only occurs when:
- Task has an active conversation
- Conversation engine is `AgentEngine.CLAUDE_CODE`
- Conversation has an `external_session_id`
- Working directory actually changes (slot differs)

## Message Parsing

**Location**: `backend/devboard/agents/engines/claude_code/message_parser.py`

**ClaudeResponseParser.parse_message_content()** → `TextResponse | VirtualToolCall | VirtualToolResult`:
- Detects XML: `<tool_call_result tool_name="..." outcome="...">`
- Parses JSON with `TOOL_CALL_PATTERN` (captures optional preamble before JSON)
- Returns TextResponse for regular text

**Invalid Tool Calls**: Returns VirtualToolCall with `valid=False` + `validation_error`

**Types**:
- TextResponse: `content`
- VirtualToolCall: `tool_name`, `arguments`, `valid`, `validation_error`, `preamble`
- VirtualToolResult: `tool_name`, `content`, `outcome` enum

## Virtual Tool Calling

**Base** (`backend/devboard/agents/engines/claude_code/virtual_tools.py`): `tool_name`, `description`, `args_model` (Pydantic), `execute(args)`

**Schema Generation**: `build_tool_schemas_section()` generates formatted docs for system prompt

**Flow**:
1. Agent responds with JSON (`tool_name`, `arguments`)
2. Parse & validate against VirtualTool's args_model
3. User approval with optional arg modifications
4. Execute via `VirtualTool.execute(args)`
5. Results wrapped in XML `<tool_call_result>`
6. Agent continues

**Validation**:
- Structure: JSON matches VirtualToolCall schema
- Tool: Exists in registered virtual tools
- Arguments: Pass tool's Pydantic schema

**Retry**: Invalid → retry with `<validation_error>` feedback (max 3)

**Preamble Support**: Text before JSON creates separate ConversationMessage before ToolCallRequest

## Concurrent MCP Tool Execution

**Location**: `backend/devboard/agents/engines/claude_code/client.py`

**Purpose**: Execute multiple MCP tool calls concurrently to improve agent performance when Claude requests multiple tools simultaneously.

**Architecture**:
- **Dual Wrapper System**: ClaudeClient creates different wrappers based on `enable_concurrent_execution`:
  - `_create_tool_execution_wrapper()`: Executes tools directly (normal mode)
  - `_create_tool_result_retrieval_wrapper()`: Returns cached results (concurrent mode)
- **Order-Based Correlation**: FIFO queue matches tool calls with their pre-executed results
- **MCP-Only**: Only applies to custom MCP tools (e.g., `mcp__builtin_tools__*`), not built-in Claude Code tools

**Flow**:
1. **Message Reception**: `stream()` receives `AssistantMessage` with `ToolUseBlock`s
2. **Immediate Execution**: `_start_running_any_mcp_tools()` checks each block:
   - If MCP tool (`_is_mcp_tool()`) → launch async task via `_execute_concurrent_mcp_tool()`
   - If built-in tool → skip (handled by CLI)
3. **Task Creation**: `_execute_concurrent_mcp_tool()` creates `asyncio.Task`:
   - Executes tool via `_execute_tool_concurrently()`
   - Caches `Future` by `tool_use_id` in `_tool_execution_cache`
   - Adds `(tool_name, tool_use_id)` to `_tool_execution_queue`
4. **Result Retrieval**: When CLI calls MCP tool:
   - Retrieval wrapper pops from queue → gets `tool_use_id`
   - Validates tool name matches (fails fast on mismatch)
   - Awaits cached `Future` (may already be complete)
   - Returns result and cleans up cache entry

**Configuration**:
```python
client = ClaudeClient(
    tools=[...],
    enable_concurrent_execution=True  # Default: True
)
```

**Benefits**:
- **Performance**: Multiple tools execute in parallel instead of sequentially
- **Transparency**: No changes needed in agent code or tool definitions
- **Safety**: Queue-based correlation prevents result mismatches

**Limitations**:
- Only applies to custom MCP tools, not built-in Claude Code tools
- Requires all tool calls to arrive in single `AssistantMessage`
- Tools must be stateless and order-independent

## MCP Tool Name Prefixing and Normalization

When DevBoard registers internal PydanticAI tools with Claude Code CLI, they are prefixed with `mcp__builtin_tools__` to distinguish them from Claude Code's native tools (Read, Edit, Bash, etc.). External MCP server tools are prefixed with `mcp__<server_name>__`.

**Prefix Format**:
- Internal tools: `mcp__builtin_tools__<tool_name>` (e.g., `mcp__builtin_tools__render_html`)
- External tools: `mcp__<server_name>__<tool_name>` (e.g., `mcp__github__create_issue`)

**Why Prefixing Exists**:
- Namespace management: Separates custom MCP tools from Claude Code's built-in tools
- Multi-server support: Allows tools from multiple MCP servers with unique namespaces
- Concurrent execution: Enables detection and special handling of MCP tool calls

**Normalization at Engine Boundary**:

The `mcp__builtin_tools__` prefix for **internal tools only** is stripped before creating DevBoard events. External MCP server tools keep their full prefixed names since the application may not have built-in handling for them.

- **Tool Registration** (line 219 in `client.py`): Prefix added when building MCP server config
- **Tool Execution** (line 318 in `client.py`): Prefix stripped when looking up tool function
- **Event Creation** (in `agent.py` and `message_parser.py`): Prefix stripped when creating ToolCall/ToolCallRequest events

This ensures that internal tool events use **canonical tool names** matching the Internal (PydanticAI) engine, while external MCP tools remain prefixed for proper identification.

**Normalization Logic** (`ClaudeClient.normalize_tool_name()`):
- Only strips `mcp__builtin_tools__` prefix for internal PydanticAI tools
- External MCP tools keep full prefix: `mcp__<server>__<tool_name>` (unchanged)
- Preserves double underscores in tool names (e.g., `mcp__builtin_tools__my__tool__name` → `my__tool__name`)

**Impact**:
- Internal tools: Frontend receives canonical names without MCP prefix
- External tools: Frontend receives full prefixed names (e.g., `mcp__github__create_issue`)
- Tool renderer registry works for internal tools with canonical names
- External MCP tools identified by their full prefixed names

## Conversation Filtering

**Location**: `backend/devboard/agents/engines/claude_code/agent_conversation.py`

**Filtered from UI**:
- Validation errors (`<validation_error>`)
- Tool results (`<tool_call_result>`)
- Messages with only tool calls (no text)

**Implementation**: `_session_message_to_conversation()` uses `ClaudeResponseParser.parse_message()` + `isinstance()` checks

## Todo List

**Storage**: `~/.claude/todos/<session-id>-agent-<agent-session-id>.json`

**Format**: JSON array with `content` (imperative), `status` (pending/in_progress/completed), optional `active_form`, `priority`, `id`

**Loading**: `ClaudeCodeSessionService.load_todo_list(session_id, include_subagents)`

## Conversation Service

**Location**: `backend/devboard/agents/engines/claude_code/agent_conversation.py`

**Session ID Tracking**: `external_session_id` in conversation record

**Message Retrieval**: `get_conversation_messages()` loads from session files (not database)

**Unified Response**: `_run_agent_and_convert_response()`:
- Runs agent with current session_id
- Updates session_id if changed (first run creates new)
- Converts to PromptResponse (MESSAGE or TOOL_REQUEST)
- Tool requests: tool_name as tool_call_id

## Files

**Core**:
- `backend/devboard/agents/engines/claude_code/agent.py`: ClaudeCodeAgent implementation
- `backend/devboard/agents/engines/claude_code/agent_conversation.py`: Conversation service
- `backend/devboard/agents/engines/claude_code/client.py`: Claude Code CLI client (includes concurrent MCP tool execution)
- `backend/devboard/agents/engines/claude_code/message_parser.py`: Message parsing
- `backend/devboard/agents/engines/claude_code/session.py`: Session management
- `backend/devboard/agents/engines/claude_code/tool_approval_manager.py`: Tool approval workflow
- `backend/devboard/agents/engines/claude_code/virtual_tools.py`: Virtual tool definitions

**Tests**:
- `backend/tests/agents/claude_code/test_concurrent_execution.py`: Concurrent MCP tool execution tests
