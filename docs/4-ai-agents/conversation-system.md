# Conversation System

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Conversation System

**Purpose**: Event-based conversation system with complete transparency, real-time streaming, polymorphic persistence

## Architecture

**Design**: Structured event streams (not simple text), complete workflow visibility, real-time streaming, tool visibility, debugging support

**Event Stream**: Agents generate ConversationEvent objects, converting from native message formats

## ConversationEvent Types

**Location**: `backend/devboard/agents/events.py`

**Discriminator**: `event_type` enables automatic type resolution

**Types**:
- **ConversationMessage**: `event_type="message"`, `role` (USER/AGENT), `text_content`, `timestamp`. Display: chat bubbles
- **ToolCall** (InternalAgent only): `event_type="tool_call"`, `tool_call_id`, `tool_name`, `tool_args`, `timestamp`. Display: expandable panel. Paired with ToolResult by tool_call_id
- **ToolResult** (InternalAgent only): `event_type="tool_result"`, `tool_call_id`, `result_content`, `is_error`, `timestamp`. Display: result section. Frontend searches forward for matching ToolResult
- **ToolCallRequest** (ClaudeCodeAgent only): `event_type="tool_call_request"`, `tool_call_id`, `tool_name`, `tool_args`, `timestamp`. Triggers approval UI. tool_name used as tool_call_id
- **SystemEvent**: `event_type="system"`, `type` (SystemEventType enum), `data` (dict), `timestamp`. System-level notifications for entity changes and workflow events. Not displayed in chat UI - processed by registered event handlers for side effects (data refetching, UI updates). Types include:
  - `TASK_UPDATED`: Task state/field changes. Data includes `task_id` and `updated_fields` (e.g., `status`, `conversation_id`, `implementation_plan_id`)
  - `CONVERSATION_UPDATED`: Conversation changes. Data includes `conversation_id` and `updated_fields`

## Event Generation

**ClaudeCodeAgent** (`engines/claude_code/agent.py`):
- `_parse_claude_result()` converts ResultMessage → events list
- TextResponse → ConversationMessage
- VirtualToolCall with preamble → ConversationMessage (preamble) + ToolCallRequest
- VirtualToolCall without preamble → ToolCallRequest

**InternalAgent** (`engines/internal/agent.py`):
- Uses PydanticAI messages directly
- TextPart → ConversationMessage
- ToolUseBlock → ToolCall
- ToolResultBlock → ToolResult

## Persistence

**Conversation Model** (`backend/devboard/db/models/conversation.py`):
- **Polymorphic**: `parent_entity_type` (PROJECT/TASK/CODEBASE), `parent_entity_id`
- **Unique Constraint**: One conversation per entity
- **Agent Config**: `agent_role`, `engine`, `model_id` (nullable)
- **Nested**: `parent_conversation_id` for future agent-to-agent
- **Lazy Creation**: `get_or_create_for_entity()` when accessing details

**ConversationMessage Model** (`backend/devboard/db/models/messages.py`):
- `message_type`: USER_PROMPT, TEXT_RESPONSE, TOOL_CALL, TOOL_RESULT, STRUCTURED_RESPONSE
- `pydantic_content`: JSON for complete structure
- `text_content`: Quick text access
- Chronological ordering
- PydanticAI format support

## Streaming

**BaseAgent Interface**:
- `run()`: Synchronous, returns complete event list
- `stream_events()`: Async generator, yields events as generated

**ConversationService Interface**:
- `send_message_or_approval()`: Synchronous
- `stream_events_for_message_or_approval()`: Streaming

**Benefits**: Immediate feedback, progress tracking, responsive UI, incremental events

**API** (`backend/devboard/api/routers/conversations.py`):
- `GET /conversations/{id}/messages`: Complete event list
- `GET /conversations/{id}/messages/stream`: NDJSON stream
- `POST /conversations/{id}/approve-tools/stream`: Tool approval stream

## Message Persistence

**ConversationRepository** (`backend/devboard/db/repositories/conversation.py`):
- `get_or_create_for_entity(entity_type, entity_id)`: Lazy init
- `create_message(conversation_id, pydantic_message)`: Persist
- `get_messages(conversation_id, exclude_tool_calls=False)`: Retrieve with filtering
- `delete_messages(conversation_id)`: Clear history
- `convert_messages_to_pydantic(message_records)`: Reconstruct

**Entity Integration**: Called by entity GET endpoints for auto conversation setup

## Benefits

**Transparency**: Complete workflow visibility

**Debugging**: Tool arguments and results aid understanding

**Progress**: Real-time operation visibility

**Immediate Feedback**: No waiting for completion

**Context**: Tool interactions provide context

**Responsive**: Progressive event display

## Files

**Core**: `backend/devboard/agents/{events.py, base_agent.py, base_agent_conversation.py}`

**Database**: `backend/devboard/db/models/{conversation.py, messages.py}`, `backend/devboard/db/repositories/conversation.py`

**API**: `backend/devboard/api/routers/conversations.py`, `backend/devboard/api/schemas/conversation.py`
