"""Convert openai-codex Notification types to DevBoard ConversationEvents."""

from __future__ import annotations

import datetime
from typing import Any

import logfire
from openai_codex.generated.v2_all import (
    AgentMessageThreadItem,
    CommandExecutionThreadItem,
    ContextCompactedNotification,
    ContextCompactionThreadItem,
    FileChangeThreadItem,
    ItemCompletedNotification,
    McpToolCallThreadItem,
    PatchApplyStatus,
    ReasoningThreadItem,
    ThreadTokenUsageUpdatedNotification,
)
from openai_codex.models import Notification

from devboard.agents.events import (
    ContextUsage,
    LocalCommand,
    LocalCommandType,
    MessageRole,
    SystemEvent,
    SystemEventType,
    TextMessage,
    ThinkingEvent,
    ToolCall,
    ToolResult,
)

ConversationEvents = list[TextMessage | LocalCommand | ToolCall | ToolResult | ThinkingEvent | SystemEvent]


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.UTC)


def _convert_item(
    item_root: Any,
) -> ConversationEvents:
    """Convert a completed ThreadItem to ConversationEvents."""
    if isinstance(item_root, AgentMessageThreadItem):
        return [TextMessage(role=MessageRole.AGENT, text_content=item_root.text, timestamp=_now())]

    if isinstance(item_root, CommandExecutionThreadItem):
        exit_code = item_root.exit_code
        return [
            LocalCommand(
                command_type=LocalCommandType.SHELL,
                command=item_root.command,
                output=item_root.aggregated_output or "",
                is_error=(exit_code is not None and exit_code != 0),
                timestamp=_now(),
            )
        ]

    if isinstance(item_root, McpToolCallThreadItem):
        item_id = item_root.id
        server = item_root.server
        tool = item_root.tool
        tool_name = f"{server}.{tool}" if server else tool
        args = item_root.arguments
        tool_args: dict[str, Any] | None = args if isinstance(args, dict) else None

        if item_root.error is not None:
            result_content = item_root.error.message or "Tool call failed"
            is_error = True
        elif item_root.result is not None:
            content_items = item_root.result.content or []
            texts = [c.get("text", "") for c in content_items if isinstance(c, dict) and c.get("type") == "text"]
            result_content = "\n".join(texts) if texts else str(item_root.result)
            is_error = False
        else:
            result_content = ""
            is_error = False

        return [
            ToolCall(tool_call_id=item_id, tool_name=tool_name, tool_args=tool_args, timestamp=_now()),
            ToolResult(tool_call_id=item_id, result_content=result_content, is_error=is_error, timestamp=_now()),
        ]

    if isinstance(item_root, FileChangeThreadItem):
        item_id = item_root.id
        changes = item_root.changes
        status = item_root.status
        return [
            ToolCall(
                tool_call_id=item_id,
                tool_name="file_change",
                tool_args={"changes": [{"path": c.path, "kind": c.kind.root.type} for c in changes]},
                timestamp=_now(),
            ),
            ToolResult(
                tool_call_id=item_id,
                result_content=f"File change {status.value}",
                is_error=(status == PatchApplyStatus.failed),
                timestamp=_now(),
            ),
        ]

    if isinstance(item_root, ReasoningThreadItem):
        content = item_root.content
        text = "\n".join(content) if content else ""
        return [ThinkingEvent(thinking_text=text, timestamp=_now())]

    if isinstance(item_root, ContextCompactionThreadItem):
        return [SystemEvent(sub_type=SystemEventType.COMPACTING_CONVERSATION, data={}, timestamp=_now())]

    logfire.debug("Skipping unsupported ThreadItem type: {type_name}", type_name=type(item_root).__name__)
    return []


def convert_notification_to_events(
    notification: Notification,
) -> tuple[ConversationEvents, ContextUsage | None]:
    """Convert a Codex Notification to (ConversationEvents, optional ContextUsage)."""
    payload = notification.payload

    if isinstance(payload, ItemCompletedNotification):
        return _convert_item(payload.item.root), None

    if isinstance(payload, ThreadTokenUsageUpdatedNotification):
        usage_breakdown = payload.token_usage.last
        usage = ContextUsage(
            input_tokens=usage_breakdown.input_tokens,
            output_tokens=usage_breakdown.output_tokens,
            cache_read_tokens=usage_breakdown.cached_input_tokens,
            cache_write_tokens=0,
            cost_usd=None,
        )
        return [], usage

    if isinstance(payload, ContextCompactedNotification):
        return [SystemEvent(sub_type=SystemEventType.COMPACTING_CONVERSATION, data={}, timestamp=_now())], None

    # TurnCompletedNotification signals end of stream — handled by AsyncTurnHandle.stream()
    # All other notification types are ignored
    return [], None


def convert_turn_result_to_text_message(final_response: str | None) -> TextMessage:
    """Convert a TurnResult's final_response to a TextMessage."""
    return TextMessage(role=MessageRole.AGENT, text_content=final_response or "", timestamp=_now())
