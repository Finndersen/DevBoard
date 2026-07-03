import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    AGENT = "agent"


class ConversationEventType(StrEnum):
    """Type of event in a conversation stream."""

    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_CALL_REQUEST = "tool_call_request"
    SYSTEM = "system"
    META_MESSAGE = "meta_message"
    LOCAL_COMMAND = "local_command"
    THINKING = "thinking"


class MetaMessageType(StrEnum):
    """Type of meta message."""

    COMPACT_SUMMARY = "compact_summary"
    SKILL_CONTENT = "skill_content"
    INITIAL_CONTEXT = "initial_context"
    EVENT_CONTEXT = "event_context"
    GIT_STATUS = "git_status"
    EXECUTION_CONTEXT = "execution_context"
    REBASE_RESULT = "rebase_result"


class LocalCommandType(StrEnum):
    """Type of local command."""

    SHELL = "shell"
    SLASH_COMMAND = "slash_command"


class SystemEventType(StrEnum):
    """Type of system event."""

    TASK_UPDATED = "task_updated"
    CONVERSATION_UPDATED = "conversation_updated"
    WORKSPACE_ALLOCATE = "workspace_allocate"
    WORKSPACE_BRANCH_CHECKOUT = "workspace_branch_checkout"
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_SETUP = "workspace_setup"
    STREAM_ERROR = "stream_error"
    STREAM_INTERRUPTED = "stream_interrupted"
    BRANCH_REBASED = "branch_rebased"
    STASH_APPLY_CONFLICT = "stash_apply_conflict"
    SESSION_EXPIRED = "session_expired"
    API_ERROR_RETRY = "api_error_retry"
    COMPACTING_CONVERSATION = "compacting_conversation"
    RATE_LIMIT = "rate_limit"
    IMPLEMENTATION_STEP_STARTED = "implementation_step_started"


class TextMessage(BaseModel):
    """Model for a project or task agent conversation message (only contains final response for agent)."""

    event_type: Literal["message"] = "message"
    role: MessageRole
    text_content: str
    timestamp: datetime.datetime
    uuid: str | None = None
    model: str | None = None


class ToolCall(BaseModel):
    """Represents a tool call made by the agent."""

    event_type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any] | None = None
    timestamp: datetime.datetime
    uuid: str | None = None


class ToolResult(BaseModel):
    """Result from a tool call execution."""

    event_type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    result_content: str
    is_error: bool = False
    timestamp: datetime.datetime
    uuid: str | None = None


class ToolCallRequest(BaseModel):
    """Tool call requiring user approval."""

    event_type: Literal["tool_call_request"] = "tool_call_request"
    tool_call_id: str
    tool_name: str
    tool_args: str | dict[str, Any] | None = None
    timestamp: datetime.datetime
    uuid: str | None = None
    model: str | None = None


class MetaMessage(BaseModel):
    """Special-case user message rendered as a collapsed indicator in the frontend."""

    event_type: Literal["meta_message"] = "meta_message"
    meta_type: MetaMessageType
    text_content: str
    timestamp: datetime.datetime
    uuid: str | None = None


class LocalCommand(BaseModel):
    """Local command executed during a Claude Code session."""

    event_type: Literal["local_command"] = "local_command"
    command_type: LocalCommandType
    command: str
    output: str = ""
    is_error: bool = False
    timestamp: datetime.datetime
    uuid: str | None = None


class ThinkingEvent(BaseModel):
    """Agent thinking activity indicator."""

    event_type: Literal["thinking"] = "thinking"
    thinking_text: str | None = None
    timestamp: datetime.datetime
    uuid: str | None = None


class SystemEvent(BaseModel):
    """System-level event for entity changes and workflow notifications.

    System events notify about entity changes without requiring conversation context.
    The data structure varies by sub_type.

    Example (TASK_UPDATED):
        {
            "task_id": 123,
            "updated_fields": {"status": "planning", "implementation_plan_id": 789}
        }

    Example (CONVERSATION_UPDATED):
        {
            "conversation_id": 100,
            "updated_fields": {"external_session_id": "abc123"}
        }

    Example (IMPLEMENTATION_STEP_STARTED):
        {
            "task_id": 123,
            "step_number": 2,
            "conversation_id": 456
        }
        Broadcast on the parent conversation once the step has been assigned a sub-agent
        conversation and is ready to execute.
    """

    event_type: Literal["system"] = "system"
    sub_type: SystemEventType
    data: dict[str, Any] | None = None
    timestamp: datetime.datetime
    uuid: str | None = None


class ContextUsage(BaseModel):
    """Token context usage from an agent execution."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float | None = None


class AgentRunStartedEvent(BaseModel):
    """Signals that an agent execution has begun."""

    event_type: Literal["agent_run_started"] = "agent_run_started"
    conversation_id: int
    timestamp: datetime.datetime
    uuid: str | None = None


class AgentRunCompletedEvent(BaseModel):
    """Signals that an agent execution has finished."""

    event_type: Literal["agent_run_completed"] = "agent_run_completed"
    status: Literal["completed", "interrupted", "failed"]
    error: str | None = None
    usage: ContextUsage | None = None
    timestamp: datetime.datetime
    uuid: str | None = None


def describe_event(event: "ConversationEvent") -> str:
    """Generate a concise single-line description of a conversation event."""
    if isinstance(event, TextMessage):
        preview = event.text_content[:80].replace("\n", " ")
        if len(event.text_content) > 80:
            preview += "…"
        return f"TextMessage(role={event.role}, {len(event.text_content)} chars): {preview!r}"
    elif isinstance(event, ToolCall):
        args_desc = ""
        if event.tool_args:
            first_key, first_val = next(iter(event.tool_args.items()))
            val_str = str(first_val)
            if len(val_str) > 40:
                val_str = val_str[:40] + "…"
            args_desc = f", {first_key}={val_str!r}"
        return f"ToolCall(tool={event.tool_name}{args_desc})"
    elif isinstance(event, ToolResult):
        status = "error" if event.is_error else "ok"
        return f"ToolResult(tool_call_id={event.tool_call_id[-8:]}, {status}, {len(event.result_content)} chars)"
    elif isinstance(event, ToolCallRequest):
        return f"ToolCallRequest(tool={event.tool_name})"
    elif isinstance(event, LocalCommand):
        return f"LocalCommand(type={event.command_type}, command={event.command!r})"
    elif isinstance(event, MetaMessage):
        return f"MetaMessage(type={event.meta_type})"
    elif isinstance(event, ThinkingEvent):
        return "ThinkingEvent()"
    elif isinstance(event, AgentRunStartedEvent):
        return f"AgentRunStartedEvent(conversation_id={event.conversation_id})"
    elif isinstance(event, AgentRunCompletedEvent):
        if event.usage:
            total_ctx = event.usage.cache_read_tokens + event.usage.cache_write_tokens + event.usage.input_tokens
            return f"AgentRunCompletedEvent(status={event.status}, ctx={total_ctx:,} tokens)"
        return f"AgentRunCompletedEvent(status={event.status})"
    else:
        return f"SystemEvent(sub_type={event.sub_type})"


# Union type for all conversation events
type ConversationEvent = Annotated[
    TextMessage
    | ToolCallRequest
    | ToolCall
    | ToolResult
    | SystemEvent
    | MetaMessage
    | LocalCommand
    | ThinkingEvent
    | AgentRunStartedEvent
    | AgentRunCompletedEvent,
    Field(discriminator="event_type"),
]
