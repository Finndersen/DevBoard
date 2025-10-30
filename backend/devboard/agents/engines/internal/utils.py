import json
from typing import Any


def convert_tool_args(tool_args: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if isinstance(tool_args, dict):
        return tool_args
    if isinstance(tool_args, str):
        return json.loads(tool_args)
    else:
        return None
