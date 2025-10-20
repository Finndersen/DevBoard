from collections.abc import Awaitable, Callable

from devboard.db.models import Document
from devboard.db.repositories import DocumentRepository


def create_set_document_content_function(
    document: Document,
    document_repo: DocumentRepository,
) -> Callable[[str], Awaitable[str]]:
    """Create a function for setting content of a blank document (no approval).

    This returns a regular async Python function that can be passed to ClaudeClient
    as a normal tool. This version is only for blank documents - for documents
    with content, use the virtual tool version which requires approval.

    Args:
        document: Document instance to set content for
        document_repo: Repository for document operations

    Returns:
        Async function that sets document content and returns a string result
    """

    async def set_document_content(content: str) -> str:
        """Set the content of a blank document.

        Args:
            content: The full content to set for the document

        Returns:
            Success message or error details
        """
        # Validate the document is currently blank
        if document.content and document.content.strip():
            return f"Error: Document already has content. Use edit_{document.document_type.value} or set_{document.document_type.value}_content virtual tools which require approval."

        # Validate content is not empty
        if not content or not content.strip():
            return "Error: Content cannot be empty."

        # Update document content and hash using repository
        document_repo.update_content(document, content)

        return f"Content set successfully for {document.document_type.value}."

    # Set function metadata for tool generation
    set_document_content.__name__ = f"set_{document.document_type.value}_content"
    set_document_content.__doc__ = f"""Set the content of a blank {document.document_type.value} document (no approval required).

This tool only works on blank documents. For documents with existing content,
use the set_{document.document_type.value}_content or edit_{document.document_type.value} virtual tools.

Args:
    content: The full content to set for the document

Returns:
    Success message or error details
"""

    return set_document_content
