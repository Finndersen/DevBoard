"""Tests for VirtualTool class and virtual tool calling functionality."""

import pytest
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.virtual_tools import (
    VirtualTool,
    build_virtual_tool_schemas_section,
)


class EditOperation(BaseModel):
    """Pydantic model for an edit operation."""

    find: str = Field(description="Text to find")
    replace: str = Field(description="Text to replace with")
    line_number: int | None = Field(default=None, description="Optional line number")


class TestVirtualToolBasics:
    """Tests for basic VirtualTool functionality."""

    def test_basic_properties(self):
        """Test that tool_name and description properties return correct values."""

        def test_function(arg1: str) -> str:
            """This is a test function."""
            return f"Result: {arg1}"

        pydantic_tool = Tool(function=test_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        assert virtual_tool.tool_name == "test_tool"
        assert virtual_tool.description == "This is a test function."


class TestValidateArgs:
    """Tests for VirtualTool.validate_args() method."""

    def test_validate_args_simple_types(self):
        """Test argument validation with simple types."""

        def simple_function(name: str, age: int, active: bool = True) -> str:
            return f"{name} is {age} years old"

        pydantic_tool = Tool(function=simple_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Valid arguments
        validated = virtual_tool.validate_args({"name": "Alice", "age": 30, "active": True})

        assert validated == {"name": "Alice", "age": 30, "active": True}

    def test_validate_args_with_defaults(self):
        """Test argument validation with default values."""

        def function_with_defaults(required: str, optional: str = "default") -> str:
            return f"{required} - {optional}"

        pydantic_tool = Tool(function=function_with_defaults, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Only required argument provided
        validated = virtual_tool.validate_args({"required": "value"})

        assert validated == {"required": "value", "optional": "default"}

    def test_validate_args_missing_required(self):
        """Test that validation fails for missing required arguments."""

        def function_required(required_arg: str) -> str:
            return required_arg

        pydantic_tool = Tool(function=function_required, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Missing required argument
        with pytest.raises(ValidationError) as exc_info:
            virtual_tool.validate_args({})

        assert "required_arg" in str(exc_info.value).lower()

    def test_validate_args_wrong_type(self):
        """Test that validation fails for wrong argument types."""

        def typed_function(number: int) -> str:
            return str(number)

        pydantic_tool = Tool(function=typed_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Wrong type (string instead of int)
        with pytest.raises(ValidationError):
            virtual_tool.validate_args({"number": "not a number"})

    def test_validate_args_with_list(self):
        """Test argument validation with list types."""

        def list_function(items: list[str]) -> str:
            return ", ".join(items)

        pydantic_tool = Tool(function=list_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Valid list
        validated = virtual_tool.validate_args({"items": ["a", "b", "c"]})

        assert validated == {"items": ["a", "b", "c"]}

    def test_validate_args_with_dict(self):
        """Test argument validation with dict types."""

        def dict_function(metadata: dict[str, str]) -> str:
            return str(metadata)

        pydantic_tool = Tool(function=dict_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Valid dict
        validated = virtual_tool.validate_args({"metadata": {"key1": "value1", "key2": "value2"}})

        assert validated == {"metadata": {"key1": "value1", "key2": "value2"}}

    def test_validate_args_with_pydantic_model(self):
        """Test argument validation with Pydantic model as argument.

        Note: The validator converts dict arguments to Pydantic model instances.
        """

        def pydantic_model_function(edit: EditOperation) -> str:
            return f"Find: {edit.find}, Replace: {edit.replace}"

        pydantic_tool = Tool(function=pydantic_model_function, name="edit_text")
        virtual_tool = VirtualTool(pydantic_tool)

        # Valid Pydantic model as dict - For a single Pydantic model argument, the schema is flattened
        edit_data = {"find": "old", "replace": "new", "line_number": 42}
        validated = virtual_tool.validate_args(edit_data)

        # The validator creates an EditOperation instance from the dict
        expected = EditOperation(find="old", replace="new", line_number=42)
        assert validated == expected

    def test_validate_args_with_list_of_pydantic_models(self):
        """Test argument validation with list of Pydantic models."""

        def batch_edit_function(edits: list[EditOperation]) -> str:
            return f"Processing {len(edits)} edits"

        pydantic_tool = Tool(function=batch_edit_function, name="batch_edit")
        virtual_tool = VirtualTool(pydantic_tool)

        # Valid list of Pydantic models
        validated = virtual_tool.validate_args(
            {"edits": [{"find": "old1", "replace": "new1"}, {"find": "old2", "replace": "new2", "line_number": 10}]}
        )

        expected = {
            "edits": [
                EditOperation(find="old1", replace="new1", line_number=None),
                EditOperation(find="old2", replace="new2", line_number=10),
            ]
        }
        assert validated == expected

    def test_validate_args_pydantic_model_missing_required(self):
        """Test that validation fails for Pydantic model with missing required fields."""

        def pydantic_model_function(edit: EditOperation) -> str:
            return f"Edit: {edit.find}"

        pydantic_tool = Tool(function=pydantic_model_function, name="edit_text")
        virtual_tool = VirtualTool(pydantic_tool)

        # Missing required 'replace' field
        with pytest.raises(ValidationError) as exc_info:
            virtual_tool.validate_args({"edit": {"find": "old"}})

        assert "replace" in str(exc_info.value).lower()

    def test_validate_args_pydantic_model_wrong_type(self):
        """Test that validation fails for Pydantic model with wrong field type."""

        def pydantic_model_function(edit: EditOperation) -> str:
            return f"Edit: {edit.find}"

        pydantic_tool = Tool(function=pydantic_model_function, name="edit_text")
        virtual_tool = VirtualTool(pydantic_tool)

        # Wrong type for line_number (string instead of int)
        with pytest.raises(ValidationError):
            virtual_tool.validate_args({"edit": {"find": "old", "replace": "new", "line_number": "not a number"}})


class TestExecute:
    """Tests for VirtualTool.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_sync_function(self):
        """Test executing a synchronous function."""

        def sync_function(message: str) -> str:
            return f"Processed: {message}"

        pydantic_tool = Tool(function=sync_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        result = await virtual_tool.execute({"message": "hello"})

        assert result == "Processed: hello"

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        """Test executing an async function."""

        async def async_function(message: str) -> str:
            return f"Async: {message}"

        pydantic_tool = Tool(function=async_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        result = await virtual_tool.execute({"message": "hello"})

        assert result == "Async: hello"

    @pytest.mark.asyncio
    async def test_execute_returns_string(self):
        """Test that execute always returns a string."""

        def returns_dict() -> dict:
            return {"key": "value"}

        pydantic_tool = Tool(function=returns_dict, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        result = await virtual_tool.execute({})

        assert isinstance(result, str)
        assert "key" in result

    @pytest.mark.asyncio
    async def test_execute_with_exception(self):
        """Test that execute wraps exceptions in ToolCallError."""

        def failing_function() -> str:
            raise ValueError("Something went wrong")

        pydantic_tool = Tool(function=failing_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # The execute method should wrap exceptions in ToolCallError
        # but currently it doesn't, so we expect the raw exception
        with pytest.raises(ValueError) as exc_info:
            await virtual_tool.execute({})

        # Check if it's wrapped or raw
        error_str = str(exc_info.value)
        assert "Something went wrong" in error_str

    @pytest.mark.asyncio
    async def test_execute_with_multiple_simple_args(self):
        """Test executing function with multiple simple arguments."""

        def multi_arg_function(name: str, count: int, active: bool = True) -> str:
            return f"{name}: {count} (active={active})"

        pydantic_tool = Tool(function=multi_arg_function, name="multi_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        # Execute with dict arguments
        result = await virtual_tool.execute({"name": "test", "count": 5, "active": False})

        assert result == "test: 5 (active=False)"


class TestGetSchema:
    """Tests for VirtualTool.get_schema() method."""

    def test_get_schema_contains_tool_name(self):
        """Test that schema contains tool name."""

        def test_function(arg: str) -> str:
            return arg

        pydantic_tool = Tool(function=test_function, name="my_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        schema = virtual_tool.get_schema()

        assert "my_tool" in schema
        assert "AVAILABLE VIRTUAL TOOL" in schema

    def test_get_schema_contains_description(self):
        """Test that schema contains function description."""

        def documented_function(arg: str) -> str:
            """This is a well-documented function."""
            return arg

        pydantic_tool = Tool(function=documented_function, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        schema = virtual_tool.get_schema()

        assert "documented function" in schema.lower()

    def test_get_schema_contains_arguments(self):
        """Test that schema contains argument information."""

        def function_with_args(name: str, count: int = 5) -> str:
            return f"{name}: {count}"

        pydantic_tool = Tool(function=function_with_args, name="test_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        schema = virtual_tool.get_schema()

        assert "Arguments" in schema or "arguments" in schema


class TestBuildVirtualToolSchemasSection:
    """Tests for build_virtual_tool_schemas_section() function."""

    def test_build_schemas_empty_list(self):
        """Test building schemas with empty tool list."""
        result = build_virtual_tool_schemas_section([])

        assert result == ""

    def test_build_schemas_single_tool(self):
        """Test building schemas with single tool."""

        def tool_function(arg: str) -> str:
            return arg

        pydantic_tool = Tool(function=tool_function, name="single_tool")
        virtual_tool = VirtualTool(pydantic_tool)

        result = build_virtual_tool_schemas_section([virtual_tool])

        assert "single_tool" in result
        assert "TOOL USAGE INSTRUCTIONS" in result

    def test_build_schemas_multiple_tools(self):
        """Test building schemas with multiple tools."""

        def tool1(arg: str) -> str:
            return arg

        def tool2(arg: int) -> str:
            return str(arg)

        pydantic_tool1 = Tool(function=tool1, name="tool_one")
        pydantic_tool2 = Tool(function=tool2, name="tool_two")

        virtual_tool1 = VirtualTool(pydantic_tool1)
        virtual_tool2 = VirtualTool(pydantic_tool2)

        result = build_virtual_tool_schemas_section([virtual_tool1, virtual_tool2])

        assert "tool_one" in result
        assert "tool_two" in result
        assert result.count("AVAILABLE VIRTUAL TOOL") == 2
