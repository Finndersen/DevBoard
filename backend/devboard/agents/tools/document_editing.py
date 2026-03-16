from pydantic_ai import ModelRetry, Tool

from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document
from devboard.db.repositories import DocumentRepository
from devboard.services.document_editor import DocumentEditorService


def create_document_edit_tool(
    document: Document, document_repo: DocumentRepository, requires_approval: bool = True
) -> Tool:
    """Create an engine-agnostic document editing tool.

    The tool validates edits before applying them.

    Args:
        document: Document model to edit
        document_repo: Repository for document operations
        requires_approval: Whether to require approval before executing edits (default: True)
    """

    def edit_document_tool(edits: list[DocumentEdit], reasoning: str = "") -> str:
        """
        Apply edits to the virtual document.
        This document DOES NOT exist on the file system, but is managed by the application.

        DOCUMENT EDITING RULES:
        1. Make precise find-replace edits using DocumentEdit objects
        2. Use exact text matches for 'find' - the text must exist exactly as written
        3. Use the MINIMUM necessary text to uniquely identify the location to replace
        4. Preserve markdown formatting and structure
        5. ONLY call this tool after discussing with the user and arriving at an understanding of the changes to be made

        Args:
            edits: List of find-replace edits to apply
            reasoning: Optional CONCISE reasoning for why these edits are being made
        """
        # Create document editor service
        editor_service = DocumentEditorService()

        # Pre-validate edits can be applied
        edit_result = editor_service.apply_edits(document.content, edits)
        if not edit_result.success:
            raise ModelRetry(f"Failed to apply edits to document: {'; '.join(edit_result.errors)}")

        # Update document content and hash using repository
        document_repo.update_content(document, edit_result.content)
        # Commit changes so that new content can be retrieved before stream ends
        document_repo.commit()

        return f"Edits applied successfully to {document.document_type}. Your context will be dynamically updated to reflect these changes."

    return Tool(
        function=edit_document_tool,
        name=f"edit_{document.document_type}",
        requires_approval=requires_approval,
        takes_ctx=False,
    )


def create_set_document_content_tool(
    document: Document, document_repo: DocumentRepository, requires_approval: bool | None = None
) -> Tool:
    """Create an engine-agnostic tool for setting the content of a document.

    This tool can be used on both blank and non-blank documents:
    - For blank documents: No approval required by default (non-destructive)
    - For non-blank documents: Requires approval by default (destructive - replaces existing content)

    Args:
        document: Document model to set content for
        document_repo: Repository for document operations
        requires_approval: Whether to require approval. If None, uses smart logic:
            requires approval only if document already has content (default: None)
    """

    def set_document_content_tool(content: str, reasoning: str = "") -> str:
        """Set the content of a virtual document.
        This document DOES NOT exist on the file system, but managed by the application.
        ONLY call this tool after discussing with the user and arriving at an understanding of the changes to be made.

        Args:
            content: The full content to set for the document
            reasoning: Optional CONCISE reasoning for the content being set

        Returns:
            Success message or error details
        """
        # Validate content is not empty
        if not content.strip():
            raise ModelRetry("Error: Content cannot be empty.")

        # Update document content and hash using repository
        document_repo.update_content(document, content)
        # Commit changes so that new content can be retrieved before stream ends
        document_repo.commit()

        return f"Successfully set content for {document.document_type}. Your context will be dynamically updated to reflect these changes."

    # Determine approval requirement: use provided value or smart logic based on content
    if requires_approval is None:
        requires_approval = bool(document.content and document.content.strip())

    return Tool(
        function=set_document_content_tool,
        name=f"set_{document.document_type}_content",
        requires_approval=requires_approval,
        takes_ctx=False,
    )
