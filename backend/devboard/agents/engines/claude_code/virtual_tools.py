"""Virtual tool calling for Claude Code agents.

This module provides a pattern for having Claude respond with structured JSON
tool calls for DOCUMENT EDITING operations only. This allows these tools to
go through the human-in-the-loop approval workflow.

Read-only tools (file search, codebase search, etc.) use Claude Code's built-in
tool system and do not require virtual tool calling.
"""

import json
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field
from pydantic_core import ValidationError

from devboard.agents.prompts import DOCUMENT_EDIT_PROMPT
from devboard.api.schemas import DocumentEdit
from devboard.services.document_editor import DocumentEditorService


class ToolCallError(Exception):
    """Exception raised when a virtual tool execution fails.

    This exception should be raised by VirtualTool.execute() methods when
    tool execution fails for any reason (validation errors, operation failures,
    resource issues, etc.). The error message will be returned to the agent
    as a failed tool result.

    Example:
        raise ToolCallError("Failed to update document: file not found")
    """

    pass


class EditDocumentArgs(BaseModel):
    """Arguments for edit_* virtual tools."""

    edits: list[DocumentEdit] = Field(description="List of edits to apply to the document")
    reasoning: str | None = Field(default=None, description="Optional explanation of the edits")


class SetContentArgs(BaseModel):
    """Arguments for set_*_content virtual tools."""

    content: str = Field(description="The complete content to set for the document")
    reasoning: str | None = Field(default=None, description="Optional explanation of the content")


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
{
  "tool_name": "<tool_name>",
  "arguments": {
    ...
  }
}

## CORRECT Tool Call Example (ONLY JSON content) ✅:
User: 'Update the task specification with the details we have discussed'
Assistant: '
{
  "tool_name": "<tool_name>",
  "arguments": {
    ...
  }
}'

## INCORRECT Tool Call Example (containing other text) ❌:
User: 'Update the task specification with the details we have discussed. Also, fix the indentation.'
Assistant: 'I will update the task specification. Here's the updated content:
{
  "tool_name": "<tool_name>",
  "arguments": {
    ...
  }
}'

IMPORTANT:
- You can only make ONE virtual tool call at a time
- After the tool executes, you will receive the result wrapped in <tool_call_result> tags
- Standard build-in tools can be used freely without any special format
- When making virtual tool calls, your message must consist of JSON content ONLY (NO OTHER TEXT).
- For normal messages, respond naturally with plain text. No JSON format needed.
"""


# Virtual Tool Classes
# ---------------------
# Class-based system where each tool encapsulates name, schema, and execution logic


class VirtualTool(ABC):
    """Abstract base class for virtual tools that require approval.

    Concrete implementations should define their own __init__ with
    whatever dependencies they need (e.g., document instance, repository, editor).
    """

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Return the tool name (e.g., 'edit_task_specification')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description for system prompt."""
        pass

    @property
    @abstractmethod
    def args_model(self) -> type[BaseModel]:
        """Return the Pydantic model for argument validation."""
        pass

    @abstractmethod
    async def execute(self, arguments: dict) -> str:
        """Execute the tool with the provided arguments.

        Args:
            arguments: Raw arguments dict from tool call

        Returns:
            Result message string on success

        Raises:
            ToolCallError: If execution fails for any reason (validation, operation failure, etc.)
        """
        pass

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

{self._format_additional_notes()}
"""

    def _format_args_schema(self) -> str:
        """Format the arguments schema section from the Pydantic model's JSON schema.

        Returns:
            JSON schema as formatted string
        """
        schema = self.args_model.model_json_schema()
        return json.dumps(schema, indent=2)

    @abstractmethod
    def _format_example_args(self) -> str:
        """Format example arguments for the schema."""
        pass

    @abstractmethod
    def _format_additional_notes(self) -> str:
        """Format additional notes/warnings for the schema."""
        pass


class EditDocumentTool(VirtualTool):
    """Tool for editing existing documents using find-replace operations."""

    def __init__(self, document, document_repo):
        """Initialize the edit document tool.

        Args:
            document: Document instance to edit (must have document_type attribute)
            document_repo: DocumentRepository for persisting updates
        """
        self.document = document
        self.document_repo = document_repo
        self.document_editor = DocumentEditorService()

    @property
    def tool_name(self) -> str:
        """Return the tool name using DocumentType enum value."""
        return f"edit_{self.document.document_type.value}"

    @property
    def description(self) -> str:
        """Return the tool description."""
        return f"Edit the {self.document.document_type.value} document using find-replace operations."

    @property
    def args_model(self) -> type[BaseModel]:
        """Return the Pydantic model for argument validation."""
        return EditDocumentArgs

    async def execute(self, arguments: dict) -> str:
        """Execute document edit with find-replace operations.

        Args:
            arguments: Raw tool arguments dict with 'edits' and optional 'reasoning'

        Returns:
            Success message

        Raises:
            ToolCallError: If arguments are invalid or edit operation fails
        """
        # Validate arguments using Pydantic model
        try:
            args = self.args_model.model_validate(arguments)
        except ValidationError as e:
            raise ToolCallError(f"Invalid arguments: {e}") from e

        # Apply edits
        edit_result = self.document_editor.apply_edits(self.document.content, args.edits)

        if not edit_result.success:
            raise ToolCallError(f"Failed to apply edits: {'; '.join(edit_result.errors)}")

        # Update document
        self.document_repo.update_content(self.document, edit_result.content)

        return f"Edits applied successfully to {self.document.document_type.value}."

    def _format_example_args(self) -> str:
        """Format example arguments for the schema."""
        return """{
    "edits": [
      {
        "find": "# Overview\\nOld content here",
        "replace": "# Overview\\nNew improved content"
      }
    ],
    "reasoning": "Updated overview section"
  }"""

    def _format_additional_notes(self) -> str:
        """Format additional notes/warnings for the schema."""
        return DOCUMENT_EDIT_PROMPT


class SetDocumentContentTool(VirtualTool):
    """Tool for setting content of documents.

    Used when the associated document is non-empty, so requires approval.
    """

    def __init__(self, document, document_repo):
        """Initialize the set document content tool.

        Args:
            document: Document instance to set content for (must have document_type attribute)
            document_repo: DocumentRepository for persisting updates
        """
        self.document = document
        self.document_repo = document_repo

    @property
    def tool_name(self) -> str:
        """Return the tool name using DocumentType enum value."""
        return f"set_{self.document.document_type.value}_content"

    @property
    def description(self) -> str:
        """Return the tool description."""
        return f"Set the content of the {self.document.document_type.value} document. "

    @property
    def args_model(self) -> type[BaseModel]:
        """Return the Pydantic model for argument validation."""
        return SetContentArgs

    async def execute(self, arguments: dict) -> str:
        """Execute set document content operation.

        Args:
            arguments: Raw tool arguments dict with 'content' and optional 'reasoning'

        Returns:
            Success message

        Raises:
            ToolCallError: If arguments are invalid or content is empty
        """
        # Validate arguments using Pydantic model
        try:
            args = self.args_model.model_validate(arguments)
        except Exception as e:
            raise ToolCallError(f"Invalid arguments: {e}") from e

        # Validate content not empty
        if not args.content.strip():
            raise ToolCallError("Content cannot be empty.")

        # Update document
        self.document_repo.update_content(self.document, args.content)

        return f"Content set successfully for {self.document.document_type.value}."

    def _format_example_args(self) -> str:
        """Format example arguments for the schema."""
        doc_type_title = self.document.document_type.value.replace("_", " ").title()
        return f"""{{
    "content": "# {doc_type_title}\\n\\nComplete content here...",
    "reasoning": "Initial {self.document.document_type.value} creation"
  }}"""

    def _format_additional_notes(self) -> str:
        """Format additional notes/warnings for the schema."""
        return """IMPORTANT:
- Provide complete, well-formatted content in a single call"""


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
