import re
from dataclasses import dataclass


def wrap_system_message(content: str, message_type: str) -> str:
    """Wrap content in <system_message type="...">...</system_message> tags."""
    return f'<system_message type="{message_type}">\n{content}\n</system_message>'


@dataclass
class SystemMessageBlock:
    message_type: str
    content: str


_SYSTEM_MESSAGE_PATTERN = re.compile(
    r'\A<system_message type="([^"]+)">(.*?)</system_message>',
    re.DOTALL,
)


def extract_system_messages(text: str) -> tuple[list[SystemMessageBlock], str]:
    """Parse leading <system_message> blocks from text.

    Returns (extracted blocks, remaining text with blocks removed).
    """
    blocks: list[SystemMessageBlock] = []
    while match := _SYSTEM_MESSAGE_PATTERN.match(text):
        blocks.append(SystemMessageBlock(message_type=match.group(1), content=match.group(2).strip()))
        text = text[match.end() :].lstrip("\n")
    return blocks, text.strip()
