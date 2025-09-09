"""Tests for the document editor service with simplified DocumentEdit schema."""

from devboard.api.schemas.task import DocumentEdit
from devboard.services.document_editor import DocumentEditorService


class TestDocumentEditorService:
    """Test the document editor service with simplified schema."""

    def setup_method(self):
        """Set up test fixtures."""
        self.editor = DocumentEditorService()

    def test_apply_single_edit_success(self):
        """Test applying a single successful edit."""
        content = "Hello world! This is a test document."
        edit = DocumentEdit(find="world", replace="universe")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is True
        assert result.content == "Hello universe! This is a test document."
        assert result.error is None

    def test_apply_multiple_edits_success(self):
        """Test applying multiple edits successfully."""
        content = "The quick brown fox jumps over the lazy dog."
        edits = [
            DocumentEdit(find="quick", replace="fast"),
            DocumentEdit(find="brown", replace="red"),
            DocumentEdit(find="lazy", replace="sleepy"),
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is True
        assert result.content == "The fast red fox jumps over the sleepy dog."
        assert result.error is None

    def test_apply_edit_text_not_found(self):
        """Test applying edit when find text doesn't exist."""
        content = "Hello world!"
        edit = DocumentEdit(find="nonexistent", replace="something")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content  # Unchanged
        assert "Text to find not found" in result.error

    def test_apply_edit_empty_find_text(self):
        """Test applying edit with empty find text."""
        content = "Hello world!"
        edit = DocumentEdit(find="", replace="something")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content
        assert "Edit 'find' text cannot be empty" in result.error

    def test_apply_edit_identical_find_replace(self):
        """Test applying edit where find and replace are identical."""
        content = "Hello world!"
        edit = DocumentEdit(find="world", replace="world")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content
        assert "Edit did not change content" in result.error

    def test_apply_edits_empty_list(self):
        """Test applying empty list of edits."""
        content = "Hello world!"

        result = self.editor.apply_edits(content, [])

        assert result.success is True
        assert result.content == content
        assert result.error is None

    def test_apply_edits_sequential_processing(self):
        """Test that edits are applied sequentially."""
        content = "abc abc abc"
        edits = [
            DocumentEdit(find="abc", replace="xyz"),  # Only replaces first occurrence
            DocumentEdit(find="abc", replace="123"),  # Replaces first remaining occurrence
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is True
        assert result.content == "xyz 123 abc"  # Third 'abc' remains
        assert result.error is None

    def test_apply_edits_failure_stops_processing(self):
        """Test that edit failure stops processing subsequent edits."""
        content = "Hello world!"
        edits = [
            DocumentEdit(find="Hello", replace="Hi"),  # Should succeed
            DocumentEdit(find="nonexistent", replace="x"),  # Should fail
            DocumentEdit(find="world", replace="universe"),  # Should not be processed
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is False
        assert result.content == "Hello world!"  # Original content returned
        assert "Text to find not found" in result.error

    def test_validate_edits_all_valid(self):
        """Test validation when all edits are valid."""
        content = "The quick brown fox"
        edits = [
            DocumentEdit(find="quick", replace="fast"),
            DocumentEdit(find="brown", replace="red"),
        ]

        errors = self.editor.validate_edits(content, edits)

        assert errors == []

    def test_validate_edits_with_errors(self):
        """Test validation when some edits have errors."""
        content = "Hello world!"
        edits = [
            DocumentEdit(find="Hello", replace="Hi"),  # Valid
            DocumentEdit(find="", replace="something"),  # Invalid: empty find
            DocumentEdit(find="nonexistent", replace="x"),  # Invalid: text not found
            DocumentEdit(find="world", replace="universe"),  # Valid
        ]

        errors = self.editor.validate_edits(content, edits)

        assert len(errors) == 2
        assert "Edit 2: 'find' text cannot be empty" in errors
        assert "Edit 3: Text not found: 'nonexistent'" in errors

    def test_validate_edits_sequential_context(self):
        """Test that validation considers sequential edit context."""
        content = "Hello world world"
        edits = [
            DocumentEdit(find="world", replace="universe"),  # First occurrence becomes 'universe'
            DocumentEdit(find="world", replace="cosmos"),  # Second occurrence becomes 'cosmos'
        ]

        errors = self.editor.validate_edits(content, edits)

        assert errors == []  # Both should be valid

    def test_markdown_content_editing(self):
        """Test editing markdown content with formatting."""
        content = """# Task Specification

## Objective
Create a new authentication system.

## Requirements
- Use JWT tokens
- Support multiple providers
"""

        edits = [
            DocumentEdit(
                find="Create a new authentication system.",
                replace="Implement OAuth 2.0 authentication with JWT tokens.",
            ),
            DocumentEdit(
                find="- Use JWT tokens\n- Support multiple providers",
                replace="- Implement OAuth 2.0 flow\n- Support Google, GitHub, and Microsoft providers\n- Use refresh tokens for session management",
            ),
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is True
        assert "Implement OAuth 2.0 authentication with JWT tokens." in result.content
        assert "- Implement OAuth 2.0 flow" in result.content
        assert "- Support Google, GitHub, and Microsoft providers" in result.content

    def test_large_content_edit(self):
        """Test editing large content blocks."""
        content = "Start\n" + "\n".join([f"Line {i}" for i in range(100)]) + "\nEnd"
        large_replacement = "Replaced\n" + "\n".join([f"New line {i}" for i in range(50)])

        edit = DocumentEdit(
            find="\n".join([f"Line {i}" for i in range(10, 20)]), replace=large_replacement
        )

        result = self.editor.apply_edits(content, [edit])

        assert result.success is True
        assert "New line 0" in result.content
        assert "New line 49" in result.content
        assert "Line 9" in result.content  # Before replaced section
        assert "Line 20" in result.content  # After replaced section
