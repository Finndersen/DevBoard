"""Tests for the Codex event converter."""

from __future__ import annotations

from unittest.mock import MagicMock

from openai_codex.generated.v2_all import (
    AddPatchChangeKind,
    AgentMessageThreadItem,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    ContextCompactedNotification,
    ContextCompactionThreadItem,
    FileChangeThreadItem,
    FileUpdateChange,
    ItemCompletedNotification,
    McpToolCallError,
    McpToolCallResult,
    McpToolCallStatus,
    McpToolCallThreadItem,
    PatchApplyStatus,
    PatchChangeKind,
    ReasoningThreadItem,
    ThreadItem,
    ThreadTokenUsage,
    ThreadTokenUsageUpdatedNotification,
    Turn,
    TurnCompletedNotification,
    TurnStatus,
    UpdatePatchChangeKind,
    WebSearchThreadItem,
)
from openai_codex.models import Notification, UnknownNotification

from devboard.agents.engines.codex.event_converter import (
    convert_notification_to_events,
    convert_turn_result_to_text_message,
)
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


def _item_completed(item_root: object) -> Notification:
    """Build an item/completed Notification wrapping the given ThreadItem root."""
    payload = ItemCompletedNotification(
        item=ThreadItem(root=item_root),  # type: ignore[arg-type]
        thread_id="t1",
        turn_id="turn1",
        completed_at_ms=0,
    )
    return Notification(method="item/completed", payload=payload)


def _token_usage_notification(input_tokens: int, output_tokens: int, cached_input_tokens: int) -> Notification:
    mock_breakdown = MagicMock()
    mock_breakdown.input_tokens = input_tokens
    mock_breakdown.output_tokens = output_tokens
    mock_breakdown.cached_input_tokens = cached_input_tokens
    mock_usage = MagicMock(spec=ThreadTokenUsage)
    mock_usage.last = mock_breakdown
    payload = ThreadTokenUsageUpdatedNotification(
        token_usage=mock_usage,
        thread_id="t1",
        turn_id="turn1",
    )
    return Notification(method="thread/tokenUsage/updated", payload=payload)


class TestConvertItemCompleted:
    def test_agent_message_item(self):
        item = AgentMessageThreadItem(id="msg_1", type="agentMessage", text="Hello world")
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 1
        msg = events[0]
        assert isinstance(msg, TextMessage)
        assert msg.role == MessageRole.AGENT
        assert msg.text_content == "Hello world"

    def test_command_execution_item_success(self):
        item = CommandExecutionThreadItem(
            id="cmd_1",
            type="commandExecution",
            command="ls -la",
            aggregated_output="total 8\ndrwxr-xr-x 2 user group 64 Jan 1 00:00 .",
            exit_code=0,
            status=CommandExecutionStatus.completed,
            command_actions=[],
            cwd="/tmp",
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 1
        cmd = events[0]
        assert isinstance(cmd, LocalCommand)
        assert cmd.command_type == LocalCommandType.SHELL
        assert cmd.command == "ls -la"
        assert "total 8" in cmd.output
        assert cmd.is_error is False

    def test_command_execution_item_failure(self):
        item = CommandExecutionThreadItem(
            id="cmd_2",
            type="commandExecution",
            command="cat /nonexistent",
            aggregated_output="cat: /nonexistent: No such file or directory",
            exit_code=1,
            status=CommandExecutionStatus.failed,
            command_actions=[],
            cwd="/tmp",
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert len(events) == 1
        cmd = events[0]
        assert isinstance(cmd, LocalCommand)
        assert cmd.is_error is True

    def test_command_execution_item_no_exit_code(self):
        item = CommandExecutionThreadItem(
            id="cmd_3",
            type="commandExecution",
            command="echo hello",
            aggregated_output="hello",
            exit_code=None,
            status=CommandExecutionStatus.completed,
            command_actions=[],
            cwd="/tmp",
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert len(events) == 1
        cmd = events[0]
        assert isinstance(cmd, LocalCommand)
        assert cmd.is_error is False

    def test_mcp_tool_call_success(self):
        result = McpToolCallResult(
            content=[{"type": "text", "text": '{"id": 42, "title": "Fix bug"}'}],
            structured_content=None,
        )
        item = McpToolCallThreadItem(
            id="mcp_1",
            type="mcpToolCall",
            server="devboard_tools",
            tool="get_task",
            arguments={"task_id": 42},
            result=result,
            error=None,
            status=McpToolCallStatus.completed,
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 2
        tool_call = events[0]
        tool_result = events[1]

        assert isinstance(tool_call, ToolCall)
        assert tool_call.tool_call_id == "mcp_1"
        assert tool_call.tool_name == "devboard_tools.get_task"
        assert tool_call.tool_args == {"task_id": 42}

        assert isinstance(tool_result, ToolResult)
        assert tool_result.tool_call_id == "mcp_1"
        assert '{"id": 42' in tool_result.result_content
        assert tool_result.is_error is False

    def test_mcp_tool_call_error(self):
        error = McpToolCallError(message="Task not found")
        item = McpToolCallThreadItem(
            id="mcp_2",
            type="mcpToolCall",
            server="devboard_tools",
            tool="get_task",
            arguments={"task_id": 999},
            result=None,
            error=error,
            status=McpToolCallStatus.failed,
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert len(events) == 2
        tool_call = events[0]
        tool_result = events[1]

        assert isinstance(tool_call, ToolCall)
        assert isinstance(tool_result, ToolResult)
        assert tool_result.is_error is True
        assert tool_result.result_content == "Task not found"

    def test_file_change_item(self):
        change1 = FileUpdateChange(
            path="src/main.py",
            kind=PatchChangeKind(root=UpdatePatchChangeKind(type="update")),
            diff="--- a/src/main.py\n+++ b/src/main.py\n",
        )
        change2 = FileUpdateChange(
            path="src/new_file.py",
            kind=PatchChangeKind(root=AddPatchChangeKind(type="add")),
            diff="--- /dev/null\n+++ b/src/new_file.py\n",
        )
        item = FileChangeThreadItem(
            id="fc_1",
            type="fileChange",
            changes=[change1, change2],
            status=PatchApplyStatus.completed,
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 2
        tool_call = events[0]
        tool_result = events[1]

        assert isinstance(tool_call, ToolCall)
        assert tool_call.tool_call_id == "fc_1"
        assert tool_call.tool_name == "file_change"
        assert "changes" in tool_call.tool_args  # type: ignore[operator]

        assert isinstance(tool_result, ToolResult)
        assert tool_result.is_error is False

    def test_file_change_item_failed(self):
        change = FileUpdateChange(
            path="missing.py",
            kind=PatchChangeKind(root=UpdatePatchChangeKind(type="update")),
            diff="",
        )
        item = FileChangeThreadItem(
            id="fc_2",
            type="fileChange",
            changes=[change],
            status=PatchApplyStatus.failed,
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert len(events) == 2
        tool_result = events[1]
        assert isinstance(tool_result, ToolResult)
        assert tool_result.is_error is True

    def test_reasoning_item(self):
        item = ReasoningThreadItem(
            id="r_1",
            type="reasoning",
            content=["I should check the task requirements first."],
        )
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 1
        thinking = events[0]
        assert isinstance(thinking, ThinkingEvent)
        assert "check the task requirements" in thinking.thinking_text

    def test_reasoning_item_no_content(self):
        item = ReasoningThreadItem(id="r_2", type="reasoning", content=None)
        events, usage = convert_notification_to_events(_item_completed(item))
        assert len(events) == 1
        thinking = events[0]
        assert isinstance(thinking, ThinkingEvent)
        assert thinking.thinking_text == ""

    def test_context_compaction_item(self):
        item = ContextCompactionThreadItem(id="cc_1", type="contextCompaction")
        events, usage = convert_notification_to_events(_item_completed(item))
        assert usage is None
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, SystemEvent)
        assert evt.sub_type == SystemEventType.COMPACTING_CONVERSATION

    def test_unknown_item_type_skipped(self):
        # WebSearchThreadItem is an unhandled type
        item = WebSearchThreadItem(id="ws_1", type="webSearch", query="python docs")
        events, usage = convert_notification_to_events(_item_completed(item))
        assert events == []
        assert usage is None


class TestTokenUsageNotification:
    def test_yields_context_usage(self):
        notification = _token_usage_notification(input_tokens=100, output_tokens=50, cached_input_tokens=20)
        events, usage = convert_notification_to_events(notification)
        assert events == []
        assert usage is not None
        assert isinstance(usage, ContextUsage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 20
        assert usage.cache_write_tokens == 0
        assert usage.cost_usd is None


class TestContextCompactedNotification:
    def test_yields_system_event(self):
        payload = ContextCompactedNotification(thread_id="t1", turn_id="turn1")
        notification = Notification(method="thread/compacted", payload=payload)
        events, usage = convert_notification_to_events(notification)
        assert usage is None
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, SystemEvent)
        assert evt.sub_type == SystemEventType.COMPACTING_CONVERSATION


class TestOtherNotifications:
    def test_turn_completed_returns_empty(self):
        turn = Turn(id="turn1", items=[], status=TurnStatus.completed)
        payload = TurnCompletedNotification(thread_id="t1", turn=turn)
        notification = Notification(method="turn/completed", payload=payload)
        events, usage = convert_notification_to_events(notification)
        assert events == []
        assert usage is None

    def test_unknown_notification_returns_empty(self):
        notification = Notification(
            method="some/future/event",
            payload=UnknownNotification(params={"data": "value"}),
        )
        events, usage = convert_notification_to_events(notification)
        assert events == []
        assert usage is None


class TestConvertTurnResultToTextMessage:
    def test_convert_final_response(self):
        msg = convert_turn_result_to_text_message("Task completed successfully.")
        assert isinstance(msg, TextMessage)
        assert msg.role == MessageRole.AGENT
        assert msg.text_content == "Task completed successfully."

    def test_empty_final_response(self):
        msg = convert_turn_result_to_text_message("")
        assert isinstance(msg, TextMessage)
        assert msg.text_content == ""

    def test_none_final_response(self):
        msg = convert_turn_result_to_text_message(None)
        assert isinstance(msg, TextMessage)
        assert msg.text_content == ""
