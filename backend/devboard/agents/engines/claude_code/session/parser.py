"""Parsing functions for Claude Code session JSONL files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import logfire

from devboard.agents.engines.claude_code.session.models import (
    AssistantSessionMessage,
    MetaSessionMessage,
    SessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.session.types import MessageEntry, TextBlockDict, ToolResultBlockDict
from devboard.agents.events import MetaMessageType


def is_message_entry(entry: dict[str, Any]) -> bool:
    """Check if a raw JSONL entry is a user or assistant message."""
    # Note: the JSONL also contains system entries with "type": "system", "subtype": "compact_boundary"
    # that precede compact summary messages. These are currently skipped since we only match
    # "user" and "assistant" types, but could be detected via entry.get("subtype") == "compact_boundary"
    # for future use.
    return entry.get("type") in ("user", "assistant")


def parse_session_message(
    entry: MessageEntry, line_num: int
) -> UserSessionMessage | AssistantSessionMessage | MetaSessionMessage:
    """Parse a message entry into the appropriate session message type.

    Callers must verify the entry is a message type using is_message_entry()
    before calling this method.

    Raises:
        KeyError: If required fields are missing
        ValueError: If message data has unexpected format
    """

    uuid = entry["uuid"]
    timestamp = datetime.fromisoformat(entry["timestamp"])
    is_sidechain = entry["isSidechain"]
    content_raw = entry["message"]["content"]

    if entry["type"] == "user":
        if entry.get("isCompactSummary") or entry.get("isMeta"):
            meta_type = (
                MetaMessageType.COMPACT_SUMMARY if entry.get("isCompactSummary") else MetaMessageType.SKILL_CONTENT
            )
            if isinstance(content_raw, str):
                text = content_raw
            elif isinstance(content_raw, list):
                text = "\n".join(
                    b.get("text", "") for b in content_raw if isinstance(b, dict) and b.get("type") == "text"
                )
            else:
                text = ""
            return MetaSessionMessage(
                uuid=uuid,
                timestamp=timestamp,
                line_num=line_num,
                is_sidechain=is_sidechain,
                meta_type=meta_type,
                text_content=text,
            )

        if isinstance(content_raw, str):
            user_content: list[TextBlockDict | ToolResultBlockDict] = [TextBlockDict(type="text", text=content_raw)]
        else:
            user_content = content_raw  # type: ignore[assignment]
        return UserSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            content=user_content,
        )

    else:
        return AssistantSessionMessage(
            uuid=uuid,
            timestamp=timestamp,
            line_num=line_num,
            is_sidechain=is_sidechain,
            content=content_raw,  # type: ignore[arg-type]
        )


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
                    messages.append(parse_session_message(entry, line_num=line_num))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logfire.warning(f"Skipping malformed JSONL entry at line {line_num}: {e}")
                continue
    return messages


def get_last_session_message_from_file(session_file: Path) -> SessionMessage | None:
    """Get the last message from a session JSONL file, skipping non-message entries."""
    with session_file.open("r") as f:
        content = f.read()

    lines = content.strip().split("\n")
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        entry = json.loads(line)
        if is_message_entry(entry):
            return parse_session_message(entry, line_num=i + 1)

    return None
