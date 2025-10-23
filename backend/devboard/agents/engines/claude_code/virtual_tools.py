"""Virtual tool calling for Claude Code agents.

This module provides a pattern for having Claude respond with structured JSON
tool calls for DOCUMENT EDITING operations only. This allows these tools to
go through the human-in-the-loop approval workflow.

Read-only tools (file search, codebase search, etc.) use Claude Code's built-in
tool system and do not require virtual tool calling.
"""

import json
from typing import Any

from pydantic_ai import Tool

# Tool response format instructions for system prompts
TOOL_RESPONSE_FORMAT = """
# TOOL USAGE INSTRUCTIONS:

1. STANDARD TOOLS (file search, codebase search, set empty document content, etc.):
   Use these tools NORMALLY via your built-in tool system.
   No special format required - just call them as you would any tool.

2. VIRTUAL TOOLS (edit_*, set_*_content (when non-empty), etc):
   These tools require approval and must use the VIRTUAL TOOL CALLING format below.

## VIRTUAL TOOL CALLING FORMAT (for tools that require approval only):

For virtual tool calls, respond with JSON content ONLY (no other text in your message):
{"tool_name": "<tool_name>", "arguments": {...}}

## CORRECT Tool Call Example (ONLY JSON content) ✅:
User: 'Update the task specification with the details we have discussed'
Assistant: '{"tool_name": "<tool_name>", "arguments": {...}}'

## INCORRECT Tool Call Example (containing other text) ❌:
User: 'Update the task specification with the details we have discussed. Also, fix the indentation.'
Assistant: 'I will update the task specification. Here's the updated content:
{"tool_name": "<tool_name>", "arguments": {...}}'

IMPORTANT:
- You can only make ONE virtual tool call at a time
- After the tool executes, you will receive the result wrapped in <tool_call_result> tags
- Standard build-in tools can be used freely without any special format
- When making virtual tool calls, your message must consist of JSON content ONLY (NO OTHER TEXT).
- For normal messages, respond naturally with plain text. No JSON format needed.
"""


# Virtual Tool Class
# ---------------------
# Wraps PydanticAI Tool instances for virtual tool calling with approval workflow


class VirtualTool:
    """Virtual tool wrapper for PydanticAI Tool instances that require approval.

    All virtual tools are constructed from PydanticAI Tool instances with requires_approval=True.
    """

    def __init__(self, pydantic_tool: Tool):
        """Initialize VirtualTool from a PydanticAI Tool.

        Args:
            pydantic_tool: PydanticAI Tool instance to wrap
        """
        self.pydantic_tool = pydantic_tool

    @property
    def tool_name(self) -> str:
        """Return the tool name."""
        return self.pydantic_tool.name

    @property
    def description(self) -> str:
        """Return the tool description."""
        return self.pydantic_tool.description

    def validate_args(self, arguments: dict) -> Any:
        """Validate and convert arguments using the PydanticAI tool's schema validator.

        Args:
            arguments: Raw arguments dict to validate

        Returns:
            Validated arguments data (converted to appropriate input types of the tool function)

        Raises:
            ValidationError: If validation fails
        """
        return self.pydantic_tool.function_schema.validator.validate_python(arguments)

    async def execute(self, arguments: dict) -> str:
        """Execute the PydanticAI tool with the provided arguments.

        Args:
            arguments: Arguments dict to pass to the tool

        Returns:
            Result string from the tool

        Raises:
            ToolCallError: If execution fails
        """
        validated_args = self.validate_args(arguments)
        result = await self.pydantic_tool.function_schema.call(validated_args, ctx=None)
        return str(result)

    def get_schema(self) -> str:
        """Generate the schema string for system prompt.

        Returns:
            Formatted tool schema string
        """
        return f"""
AVAILABLE VIRTUAL TOOL: {self.tool_name}

Description: {self.description}

Arguments:
{self._format_args_schema()}

Example tool call:
{{
  "tool_name": "{self.tool_name}",
  "arguments": {self._format_example_args()}
}}
"""

    def _format_args_schema(self) -> str:
        """Format the arguments schema section from the function schema's JSON schema.

        Returns:
            JSON schema as formatted string
        """
        json_schema = self.pydantic_tool.function_schema.json_schema
        return json.dumps(json_schema, indent=2)

    def _format_example_args(self) -> str:
        """Format example arguments for the schema."""
        # Use the JSON schema to generate example
        json_schema = self.pydantic_tool.function_schema.json_schema
        properties = json_schema.get("properties", {})

        if not properties:
            return "{}"

        # Generate simple example values based on types
        example = {}
        for field_name, field_schema in properties.items():
            field_type = field_schema.get("type", "string")
            if field_type == "string":
                example[field_name] = f"<{field_name}>"
            elif field_type == "integer":
                example[field_name] = 123
            elif field_type == "number":
                example[field_name] = 123.45
            elif field_type == "boolean":
                example[field_name] = True
            elif field_type == "array":
                example[field_name] = []
            elif field_type == "object":
                example[field_name] = {}

        return json.dumps(example, indent=2)


def build_virtual_tool_schemas_section(tools: list[VirtualTool]) -> str:
    """Build the complete tool schemas section for the system prompt.

    Args:
        tools: List of VirtualTool instances that should be available

    Returns:
        Complete formatted tool schemas section
    """
    if not tools:
        return ""

    schemas = [TOOL_RESPONSE_FORMAT]

    for tool in tools:
        schemas.append(tool.get_schema())

    return "\n".join(schemas)
