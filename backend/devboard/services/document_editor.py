"""Document editing service for applying structured edits to markdown documents."""

import logging
from typing import NamedTuple

import logfire

from ..api.schemas.task import DocumentEdit

logger = logging.getLogger(__name__)


class EditResult(NamedTuple):
    """Result of applying an edit operation."""

    success: bool
    content: str
    error: str | None = None


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
            EditResult with success status, final content, and any errors
        """
        if not edits:
            return EditResult(success=True, content=content)

        with logfire.span("document_editor.apply_edits", edit_count=len(edits)):
            try:
                current_content = content

                for i, edit in enumerate(edits):
                    with logfire.span(
                        "document_editor.apply_single_edit",
                        edit_index=i,
                        find_length=len(edit.find),
                    ):
                        edit_result = self._apply_single_edit(current_content, edit)
                        if not edit_result.success:
                            logfire.error("Edit failed", edit_index=i, error=edit_result.error)
                            return EditResult(
                                success=False,
                                content=content,  # Return original content on failure
                                error=edit_result.error,
                            )
                        current_content = edit_result.content

                logfire.info(
                    "All edits applied successfully",
                    original_length=len(content),
                    final_length=len(current_content),
                )

                return EditResult(success=True, content=current_content)

            except Exception as e:
                logfire.error("Unexpected error applying edits", error=str(e), exc_info=e)
                return EditResult(success=False, content=content, error=f"Unexpected error: {e}")

    def _apply_single_edit(self, content: str, edit: DocumentEdit) -> EditResult:
        """Apply a single find-replace edit.

        Args:
            content: Current document content
            edit: Single edit operation

        Returns:
            EditResult with success status and updated content
        """
        try:
            if not edit.find:
                return EditResult(
                    success=False, content=content, error="Edit 'find' text cannot be empty"
                )

            # Check if the find text exists
            if edit.find not in content:
                # Only add ... if text was actually truncated
                display_text = edit.find[:100]
                if len(edit.find) > 100:
                    display_text += "..."
                return EditResult(
                    success=False,
                    content=content,
                    error=f"Text to find not found: '{display_text}'",
                )

            # Count occurrences to warn about ambiguous edits
            occurrences = content.count(edit.find)
            if occurrences > 1:
                logger.warning(
                    "Ambiguous edit: find text appears %d times, replacing first occurrence",
                    occurrences,
                    extra={"find_text": edit.find[:50]},
                )

            # Apply the replacement
            new_content = content.replace(
                edit.find, edit.replace, 1
            )  # Replace only first occurrence

            # Check if find and replace are identical (no-op edit)
            if edit.find == edit.replace:
                return EditResult(
                    success=False, content=content, error="Edit did not change content"
                )

            # Verify the edit was applied (should not happen with valid find/replace)
            if new_content == content:
                return EditResult(
                    success=False,
                    content=content,
                    error="Edit did not change content - unexpected failure",
                )

            logfire.info(
                "Edit applied", find_length=len(edit.find), replace_length=len(edit.replace)
            )

            return EditResult(success=True, content=new_content)

        except Exception as e:
            return EditResult(success=False, content=content, error=f"Error applying edit: {e}")

    def validate_edits(self, content: str, edits: list[DocumentEdit]) -> list[str]:
        """Validate that all edits can be applied without actually applying them.

        Args:
            content: Document content to validate against
            edits: List of edits to validate

        Returns:
            List of error messages, empty if all edits are valid
        """
        errors = []
        current_content = content

        for i, edit in enumerate(edits):
            if not edit.find:
                errors.append(f"Edit {i + 1}: 'find' text cannot be empty")
                continue

            if edit.find not in current_content:
                # Only add ... if text was actually truncated
                display_text = edit.find[:100]
                if len(edit.find) > 100:
                    display_text += "..."
                errors.append(f"Edit {i + 1}: Text not found: '{display_text}'")
                continue

            # Simulate applying the edit for subsequent validations
            current_content = current_content.replace(edit.find, edit.replace, 1)

        return errors


# Global document editor service instance
document_editor_service = DocumentEditorService()
