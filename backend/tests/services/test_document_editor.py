"""Tests for the document editor service with simplified DocumentEdit schema."""

from devboard.api.schemas import DocumentEdit
from devboard.services.document_editor import DocumentEditorService


class TestDocumentEditorService:
    """Test the document editor service with simplified schema."""

    def setup_method(self):
        """Set up test fixtures."""
        self.editor = DocumentEditorService()

    def test_apply_single_edit_success(self):
        """Test applying a single successful edit."""
        content = "Hello world! This is a test document."
        edit = DocumentEdit(old_string="world", new_string="universe")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is True
        assert result.content == "Hello universe! This is a test document."
        assert result.errors == []

    def test_apply_multiple_edits_success(self):
        """Test applying multiple edits successfully."""
        content = "The quick brown fox jumps over the lazy dog."
        edits = [
            DocumentEdit(old_string="quick", new_string="fast"),
            DocumentEdit(old_string="brown", new_string="red"),
            DocumentEdit(old_string="lazy", new_string="sleepy"),
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is True
        assert result.content == "The fast red fox jumps over the sleepy dog."
        assert result.errors == []

    def test_apply_edit_text_not_found(self):
        """Test applying edit when find text doesn't exist."""
        content = "Hello world!"
        edit = DocumentEdit(old_string="nonexistent", new_string="something")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content  # Unchanged
        assert len(result.errors) == 1
        assert "Text not found" in result.errors[0]

    def test_apply_edit_empty_find_text(self):
        """Test applying edit with empty find text."""
        content = "Hello world!"
        edit = DocumentEdit(old_string="", new_string="something")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content
        assert len(result.errors) == 1
        assert "'find' text cannot be empty" in result.errors[0]

    def test_apply_edit_identical_find_replace(self):
        """Test applying edit where find and replace are identical."""
        content = "Hello world!"
        edit = DocumentEdit(old_string="world", new_string="world")

        result = self.editor.apply_edits(content, [edit])

        assert result.success is False
        assert result.content == content
        assert len(result.errors) == 1
        assert "Edit did not change content" in result.errors[0]

    def test_apply_edits_empty_list(self):
        """Test applying empty list of edits."""
        content = "Hello world!"

        result = self.editor.apply_edits(content, [])

        assert result.success is True
        assert result.content == content
        assert result.errors == []

    def test_apply_edits_ambiguous_text_error(self):
        """Test that ambiguous edits are treated as errors."""
        content = "abc abc abc"
        edits = [
            DocumentEdit(old_string="abc", new_string="xyz"),  # Should fail due to ambiguity
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is False
        assert result.content == content  # Original content unchanged
        assert len(result.errors) == 1
        assert "Ambiguous edit" in result.errors[0]
        assert "appears 3 times" in result.errors[0]
        assert "make the find text more specific" in result.errors[0]

    def test_apply_edits_ambiguous_text_long_truncation(self):
        """Test that long ambiguous find text is properly truncated in error messages."""
        long_text = "a" * 60  # Longer than 50 character limit
        content = f"{long_text} some text {long_text} more text {long_text}"
        edits = [
            DocumentEdit(old_string=long_text, new_string="short"),
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is False
        assert "appears 3 times" in result.errors[0]
        assert "..." in result.errors[0]  # Should be truncated

    def test_apply_edits_collects_errors_and_continues(self):
        """Test that edit failures are collected and processing continues."""
        content = "Hello world!"
        edits = [
            DocumentEdit(old_string="Hello", new_string="Hi"),  # Should succeed
            DocumentEdit(old_string="nonexistent", new_string="x"),  # Should fail
            DocumentEdit(old_string="!", new_string="?"),  # Should succeed
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is False  # Overall failure due to one failed edit
        assert result.content == "Hello world!"  # Original content returned on any failure
        assert len(result.errors) == 1
        assert "Text not found: 'nonexistent'" in result.errors[0]

    def test_apply_edits_collects_all_errors(self):
        """Test that apply_edits collects all errors when multiple edits fail."""
        content = "Hello world!"
        edits = [
            DocumentEdit(old_string="Hello", new_string="Hi"),  # Valid
            DocumentEdit(old_string="", new_string="something"),  # Invalid: empty find
            DocumentEdit(old_string="nonexistent", new_string="x"),  # Invalid: text not found
            DocumentEdit(
                old_string="universe", new_string="cosmos"
            ),  # Invalid: 'universe' not found in modified content
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is False
        assert result.content == "Hello world!"  # Original content unchanged
        assert len(result.errors) == 3  # First succeeds, rest fail
        assert "'find' text cannot be empty" in result.errors[0]
        assert "Text not found: 'nonexistent'" in result.errors[1]
        assert "Text not found: 'universe'" in result.errors[2]  # 'universe' not found in modified content

    def test_apply_edits_unique_text_success(self):
        """Test that edits with unique find text succeed."""
        content = "Hello wonderful world"
        edits = [
            DocumentEdit(old_string="Hello", new_string="Hi"),  # Unique
            DocumentEdit(old_string="wonderful", new_string="amazing"),  # Unique
            DocumentEdit(old_string="world", new_string="universe"),  # Unique
        ]

        result = self.editor.apply_edits(content, edits)

        assert result.success is True
        assert result.content == "Hi amazing universe"
        assert result.errors == []

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
                old_string="Create a new authentication system.",
                new_string="Implement OAuth 2.0 authentication with JWT tokens.",
            ),
            DocumentEdit(
                old_string="- Use JWT tokens\n- Support multiple providers",
                new_string="- Implement OAuth 2.0 flow\n- Support Google, GitHub, and Microsoft providers\n- Use refresh tokens for session management",
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
            old_string="\n".join([f"Line {i}" for i in range(10, 20)]),
            new_string=large_replacement,
        )

        result = self.editor.apply_edits(content, [edit])

        assert result.success is True
        assert "New line 0" in result.content
        assert "New line 49" in result.content
        assert "Line 9" in result.content  # Before replaced section
        assert "Line 20" in result.content  # After replaced section
