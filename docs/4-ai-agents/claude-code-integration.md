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

**SessionMessage**: `uuid`, `timestamp`, `role`, `content`, `tool_calls`, `tool_results`. `text_content` property extracts displayable text

**Content Blocks**: TextBlock, ToolUseBlock, ToolResultBlock

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
- `backend/devboard/agents/engines/claude_code/client.py`: Claude Code CLI client
- `backend/devboard/agents/engines/claude_code/message_parser.py`: Message parsing
- `backend/devboard/agents/engines/claude_code/session.py`: Session management
- `backend/devboard/agents/engines/claude_code/tool_approval_manager.py`: Tool approval workflow
- `backend/devboard/agents/engines/claude_code/virtual_tools.py`: Virtual tool definitions

## See Also

[Agent Architecture](./agent-architecture.md) | [Tools and Capabilities](./tools-and-capabilities.md) | [Conversation System](./conversation-system.md) | [Configuration](./configuration.md)
