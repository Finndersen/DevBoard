"""Document API endpoints."""

from fastapi import APIRouter, Depends

from devboard.api.dependencies.entities import get_verified_document
from devboard.api.dependencies.repositories import get_document_repository
from devboard.api.schemas import DocumentResponse, DocumentUpdate
from devboard.db.models import Document
from devboard.db.repositories import DocumentRepository

router = APIRouter()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document: Document = Depends(get_verified_document),
) -> DocumentResponse:
    """Get a specific document by ID."""
    return DocumentResponse.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_update: DocumentUpdate,
    document: Document = Depends(get_verified_document),
    document_repo: DocumentRepository = Depends(get_document_repository),
) -> DocumentResponse:
    """Update a document's content."""
    document_repo.update_content(document, document_update.content)
    return DocumentResponse.model_validate(document)
