"""Document editing service for applying structured edits to markdown documents."""

from typing import NamedTuple

import logfire

from ..api.schemas import DocumentEdit


class EditResult(NamedTuple):
    """Result of applying an edit operation."""

    success: bool
    content: str
    errors: list[str] = []


class DocumentEditError(Exception):
    """Exception raised when document editing fails."""

    pass


class DocumentEditorService:
    """Service for applying find-replace edits to documents."""

    def apply_edits(self, content: str, edits: list[DocumentEdit]) -> EditResult:
        """Apply a list of edits to document content.

        Args:
            content: Original document content
            edits: List of find-replace edits to apply

        Returns:
            EditResult with success status, final content, and list of errors
        """
        if not edits:
            return EditResult(success=True, content=content)

        with logfire.span("document_editor.apply_edits", edit_count=len(edits)):
            current_content = content
            errors: list[str] = []

            for i, edit in enumerate(edits):
                with logfire.span(
                    "document_editor.apply_single_edit",
                    edit_index=i,
                    find_length=len(edit.old_string),
                ):
                    edit_result = self._apply_single_edit(current_content, edit)
                    if not edit_result.success:
                        error_msg = (
                            f"Edit {i + 1}: {edit_result.errors[0]}"
                            if edit_result.errors
                            else f"Edit {i + 1}: Unknown error"
                        )
                        errors.append(error_msg)
                    else:
                        current_content = edit_result.content

            if errors:
                logfire.error("Edit failed", errors=errors)
                return EditResult(
                    success=False,
                    content=content,  # Return original content on failure
                    errors=errors,
                )

            logfire.info(
                "All edits applied successfully",
                original_length=len(content),
                final_length=len(current_content),
            )

            return EditResult(success=True, content=current_content)

    def _apply_single_edit(self, content: str, edit: DocumentEdit) -> EditResult:
        """Apply a single find-replace edit.

        Args:
            content: Current document content
            edit: Single edit operation

        Returns:
            EditResult with success status and updated content
        """
        if not edit.old_string:
            return EditResult(success=False, content=content, errors=["'find' text cannot be empty"])

        # Check if the find text exists
        if edit.old_string not in content:
            # Only add ... if text was actually truncated
            display_text = edit.old_string[:100]
            if len(edit.old_string) > 100:
                display_text += "..."
            return EditResult(
                success=False,
                content=content,
                errors=[f"Text not found: '{display_text}'"],
            )

        # Check for ambiguous edits
        occurrences = content.count(edit.old_string)
        if occurrences > 1:
            display_text = edit.old_string[:50]
            if len(edit.old_string) > 50:
                display_text += "..."
            return EditResult(
                success=False,
                content=content,
                errors=[
                    f"Ambiguous edit: text appears {occurrences} times. Please make the find text more specific to uniquely identify the location: '{display_text}'"
                ],
            )

        # Apply the replacement
        new_content = content.replace(edit.old_string, edit.new_string, 1)  # Replace only first occurrence

        # Check if find and replace are identical (no-op edit)
        if edit.old_string == edit.new_string:
            return EditResult(success=False, content=content, errors=["Edit did not change content"])

        # Verify the edit was applied (should not happen with valid find/replace)
        if new_content == content:
            return EditResult(
                success=False,
                content=content,
                errors=["Edit did not change content - unexpected failure"],
            )

        logfire.info("Edit applied", find_length=len(edit.old_string), replace_length=len(edit.new_string))

        return EditResult(success=True, content=new_content)


# Global document editor service instance
document_editor_service = DocumentEditorService()
