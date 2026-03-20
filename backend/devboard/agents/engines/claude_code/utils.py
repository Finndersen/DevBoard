import json
from pathlib import Path

import logfire
from claude_agent_sdk import (
    AssistantMessage,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

# MCP server name for internal PydanticAI tools
BUILTIN_TOOLS_MCP_NAME = "devboard"

_LEGACY_MCP_PREFIXES = ("mcp__devboard__", "mcp__builtin_tools__")


def load_env_from_settings() -> dict[str, str]:
    """Load environment variables from ~/.claude/settings.json.

    Returns:
        Dictionary of environment variables, or empty dict if not found
    """
    settings_path = Path.home() / ".claude" / "settings.json"

    if not settings_path.exists():
        return {}

    try:
        with settings_path.open() as f:
            settings = json.load(f)
            return settings.get("env", {})
    except (json.JSONDecodeError, OSError) as e:
        logfire.warn(f"Failed to load Claude settings from {settings_path}: {e}")
        return {}


def describe_message(message: Message) -> str:
    """Generate a concise description of a Claude SDK message.

    Args:
        message: The message to describe

    Returns:
        A string describing the message type and its key content
    """
    if isinstance(message, UserMessage):
        # Check if content is a list of blocks or a simple string
        if isinstance(message.content, str):
            return f"UserMessage(text, {len(message.content)} chars)"

        # Analyze content blocks
        text_blocks = sum(1 for block in message.content if isinstance(block, TextBlock))
        tool_results = [block for block in message.content if isinstance(block, ToolResultBlock)]

        parts = []
        if text_blocks:
            parts.append(f"{text_blocks} text")
        if tool_results:
            parts.append(f"{len(tool_results)} tool_result(s)")

        content_desc = ", ".join(parts) if parts else "empty"
        return f"UserMessage({content_desc})"

    elif isinstance(message, AssistantMessage):
        # Analyze content blocks
        text_blocks = sum(1 for block in message.content if isinstance(block, TextBlock))
        thinking_blocks = sum(1 for block in message.content if isinstance(block, ThinkingBlock))
        tool_uses = [block for block in message.content if isinstance(block, ToolUseBlock)]

        parts = []
        if text_blocks:
            parts.append(f"{text_blocks} text")
        if thinking_blocks:
            parts.append(f"{thinking_blocks} thinking")
        if tool_uses:
            tool_names = [tool.name for tool in tool_uses]
            parts.append(f"tools: {', '.join(tool_names)}")

        content_desc = ", ".join(parts) if parts else "empty"
        return f"AssistantMessage({content_desc}, model={message.model})"

    elif isinstance(message, SystemMessage):
        return f"SystemMessage(subtype={message.subtype})"

    elif isinstance(message, ResultMessage):
        status = "error" if message.is_error else "success"
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "N/A"
        return f"ResultMessage({status}, cost={cost}, turns={message.num_turns})"

    else:
        # StreamEvent
        event_type = message.event.get("type", "unknown")
        return f"StreamEvent(type={event_type})"


def normalize_tool_name(tool_name: str) -> str:
    """Normalize tool name by stripping MCP prefix for internal tools only.

    Only internal PydanticAI tools (prefixed with mcp__devboard__ or the legacy
    mcp__builtin_tools__) are normalized. External MCP server tools keep their full
    prefixed names since the application may not have built-in handling for them.

    Examples:
        >>> normalize_tool_name("mcp__devboard__render_html")
        "render_html"
        >>> normalize_tool_name("mcp__builtin_tools__edit_task")  # legacy prefix
        "edit_task"
        >>> normalize_tool_name("mcp__github__create_issue")
        "mcp__github__create_issue"  # External tools keep prefix
        >>> normalize_tool_name("render_html")
        "render_html"
    """
    for prefix in _LEGACY_MCP_PREFIXES:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix) :]
    return tool_name
