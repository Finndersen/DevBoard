"""Document repository for document data access operations."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select

from devboard.db.models.document import Document, DocumentType
from devboard.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for document data access operations with auto-hashing."""

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Calculate MD5 hash of content for conflict detection.

        Args:
            content: The document content to hash

        Returns:
            MD5 hash as 32-character hex string
        """
        return hashlib.md5(content.encode()).hexdigest()

    def get_by_id(self, document_id: int) -> Document | None:
        """Get a document by its ID.

        Args:
            document_id: The document ID to search for

        Returns:
            Document instance if found, None otherwise
        """
        stmt = select(Document).where(Document.id == document_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, document_type: DocumentType, content: str = "") -> Document:
        """Create a new document with auto-calculated hash.

        Args:
            document_type: Type of the document
            content: Initial content (defaults to empty string)

        Returns:
            Created document with assigned ID and hash
        """
        document = Document(
            document_type=document_type.value,
            content=content,
            content_hash=self.calculate_hash(content),
        )
        self.db.add(document)
        self.db.flush()  # Get the ID without committing
        return document

    def update_content(self, document: Document, new_content: str) -> Document:
        """Update document content and recalculate hash.

        Args:
            document: Document instance to update
            new_content: New content for the document

        Returns:
            Updated document with new hash
        """
        document.content = new_content
        document.content_hash = self.calculate_hash(new_content)
        document.updated_at = datetime.now(UTC)
        return document

    def update_content_if_changed(
        self, document: Document, new_content: str
    ) -> tuple[Document, bool]:
        """Update document content only if it has changed.

        Args:
            document: Document instance to potentially update
            new_content: New content for the document

        Returns:
            Tuple of (document, was_updated)
        """
        new_hash = self.calculate_hash(new_content)
        if new_hash != document.content_hash:
            document.content = new_content
            document.content_hash = new_hash
            document.updated_at = datetime.now(UTC)
            return document, True
        return document, False

    def verify_hash(self, document: Document) -> bool:
        """Verify that the document's hash matches its content.

        Args:
            document: Document to verify

        Returns:
            True if hash is valid, False otherwise
        """
        expected_hash = self.calculate_hash(document.content)
        return expected_hash == document.content_hash
