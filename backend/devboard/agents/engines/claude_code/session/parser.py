"""Parsing functions for Claude Code session JSONL files."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import logfire

from devboard.agents.engines.claude_code.session.models import (
    AssistantSessionMessage,
    LocalCommandSessionMessage,
    MetaSessionMessage,
    SessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.session.types import (
    MessageEntry,
    SystemLocalCommandEntry,
    TextBlockDict,
    ToolResultBlockDict,
    UserEntry,
)
from devboard.agents.events import LocalCommandType, MetaMessageType


def _parse_xml_tag(text: str, tag: str) -> str | None:
    """Extract content between <tag> and </tag>, returns None if tag not found."""
    match = re.search(rf"<{re.escape(tag)}>(.*?)</{re.escape(tag)}>", text, re.DOTALL)
    return match.group(1) if match else None


def is_message_entry(entry: dict[str, Any]) -> bool:
    """Check if a raw JSONL entry is a user, assistant, or system local_command message."""
    if entry.get("type") in ("user", "assistant"):
        return True
    if entry.get("type") == "system" and entry.get("subtype") == "local_command":
        return True
    return False


def _extract_text_from_content(content_raw: str | list[Any]) -> str:
    """Extract text from message content (string or list of text blocks)."""
    if isinstance(content_raw, str):
        return content_raw
    return "\n".join(b.get("text", "") for b in content_raw if isinstance(b, dict) and b.get("type") == "text")


def _parse_local_command_from_text(
    text: str, uuid: str, timestamp: datetime, line_num: int, is_sidechain: bool
) -> LocalCommandSessionMessage | None:
    """Try to parse a local command from user message text content. Returns None if not a command."""
    bash_input = _parse_xml_tag(text, "bash-input")
    if bash_input is not None:
        return LocalCommandSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            command_type=LocalCommandType.SHELL,
            command=bash_input,
        )

    command_name = _parse_xml_tag(text, "command-name")
    if command_name is not None:
        command_args = _parse_xml_tag(text, "command-args")
        command = f"{command_name} {command_args}".strip() if command_args else command_name
        return LocalCommandSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            command_type=LocalCommandType.SLASH_COMMAND,
            command=command,
        )

    bash_stdout = _parse_xml_tag(text, "bash-stdout")
    if bash_stdout is not None:
        bash_stderr = _parse_xml_tag(text, "bash-stderr")
        return LocalCommandSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            command_type=LocalCommandType.SHELL,
            output=bash_stdout,
            is_error=bool(bash_stderr),
        )

    local_cmd_stdout = _parse_xml_tag(text, "local-command-stdout")
    if local_cmd_stdout is not None:
        return LocalCommandSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            command_type=LocalCommandType.SLASH_COMMAND,
            output=local_cmd_stdout,
        )

    return None


def parse_session_message(entry: MessageEntry, line_num: int) -> SessionMessage | None:
    """Parse a message entry into the appropriate session message type.

    Callers must verify the entry is a message type using is_message_entry()
    before calling this method.

    Raises:
        KeyError: If required fields are missing
        ValueError: If message data has unexpected format
    """
    uuid = entry["uuid"]
    timestamp = datetime.fromisoformat(entry["timestamp"])

    # Handle system local_command entries (different structure from user/assistant)
    if entry.get("type") == "system" and entry.get("subtype") == "local_command":
        system_entry = cast(SystemLocalCommandEntry, entry)
        content = system_entry["content"]
        is_sidechain = system_entry.get("isSidechain", False)

        command_name = _parse_xml_tag(content, "command-name")
        command_args = _parse_xml_tag(content, "command-args")
        local_cmd_stdout = _parse_xml_tag(content, "local-command-stdout")

        command = ""
        if command_name:
            command = f"{command_name} {command_args}".strip() if command_args else command_name

        # Skip entries that carry no useful information (no command and no output)
        if not command and not local_cmd_stdout:
            return None

        return LocalCommandSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            command_type=LocalCommandType.SLASH_COMMAND,
            command=command,
            output=local_cmd_stdout or "",
        )

    # At this point, the entry is a user or assistant message (system entries returned above)
    user_or_assistant = cast(UserEntry, entry)
    is_sidechain = user_or_assistant["isSidechain"]
    content_raw = user_or_assistant["message"]["content"]

    if user_or_assistant["type"] == "user":
        # Handle compact summary
        if user_or_assistant.get("isCompactSummary"):
            text = _extract_text_from_content(content_raw)
            return MetaSessionMessage(
                uuid=uuid,
                timestamp=timestamp,
                line_num=line_num,
                is_sidechain=is_sidechain,
                meta_type=MetaMessageType.COMPACT_SUMMARY,
                text_content=text,
            )

        # Handle isMeta messages
        if user_or_assistant.get("isMeta"):
            text = _extract_text_from_content(content_raw)
            # Only classify as SKILL_CONTENT when sourceToolUseID is present or content
            # starts with the skill base directory marker (fallback for older sessions)
            if user_or_assistant.get("sourceToolUseID") or text.startswith("Base directory for this skill:"):
                return MetaSessionMessage(
                    uuid=uuid,
                    timestamp=timestamp,
                    line_num=line_num,
                    is_sidechain=is_sidechain,
                    meta_type=MetaMessageType.SKILL_CONTENT,
                    text_content=text,
                )
            # All other isMeta messages (e.g. "Continue where you left off", hooks) are skipped
            return None

        # Check for local command patterns in non-meta user messages
        text = _extract_text_from_content(content_raw)
        local_cmd = _parse_local_command_from_text(text, uuid, timestamp, line_num, is_sidechain)
        if local_cmd is not None:
            return local_cmd

        if isinstance(content_raw, str):
            user_content: list[TextBlockDict | ToolResultBlockDict] = [TextBlockDict(type="text", text=content_raw)]
        else:
            user_content = content_raw  # type: ignore[assignment]
        return UserSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            content=user_content,  # ty:ignore[invalid-argument-type]
        )

    else:
        model = user_or_assistant["message"].get("model")  # type: ignore[typeddict-item]
        usage = user_or_assistant["message"].get("usage")  # type: ignore[typeddict-item]
        return AssistantSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            content=content_raw,  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
            model=model,
            usage=usage,
        )


def _merge_local_command_messages(messages: list[SessionMessage]) -> list[SessionMessage]:
    """Merge consecutive command+output LocalCommandSessionMessage pairs.

    If an output-only message (command="") immediately follows a command-only message
    (output="") of the same command_type, merge them into a single message.
    """
    if len(messages) < 2:
        return messages

    merged: list[SessionMessage] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if isinstance(msg, LocalCommandSessionMessage) and msg.command and not msg.output and i + 1 < len(messages):
            next_msg = messages[i + 1]
            if (
                isinstance(next_msg, LocalCommandSessionMessage)
                and not next_msg.command
                and next_msg.output
                and next_msg.command_type == msg.command_type
            ):
                merged.append(
                    LocalCommandSessionMessage(
                        uuid=msg.uuid,
                        timestamp=msg.timestamp,
                        line_num=msg.line_num,
                        is_sidechain=msg.is_sidechain,
                        command_type=msg.command_type,
                        command=msg.command,
                        output=next_msg.output,
                        is_error=next_msg.is_error,
                    )
                )
                i += 2
                continue
        merged.append(msg)
        i += 1
    return merged


def load_session_messages_from_file(session_file: Path) -> list[SessionMessage]:
    """Load all session messages from a JSONL session file.

    Malformed JSONL entries are logged and skipped.
    """
    messages: list[SessionMessage] = []
    with session_file.open("r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if is_message_entry(entry):
                    msg = parse_session_message(entry, line_num=line_num)
                    if msg is not None:
                        messages.append(msg)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logfire.warning(f"Skipping malformed JSONL entry at line {line_num}: {e}")
                continue
    return _merge_local_command_messages(messages)


def get_last_session_message_from_file(session_file: Path) -> SessionMessage | None:
    """Get the last message from a session JSONL file, skipping non-message and output-only local command entries."""
    with session_file.open("r") as f:
        content = f.read()

    lines = content.strip().split("\n")
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        entry = json.loads(line)
        if is_message_entry(entry):
            msg = parse_session_message(entry, line_num=i + 1)
            if msg is None:
                continue
            # Skip output-only local command messages
            if isinstance(msg, LocalCommandSessionMessage) and not msg.command:
                continue
            return msg

    return None
