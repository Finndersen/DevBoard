"""Document API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.repositories import get_document_repository
from devboard.api.schemas import DocumentResponse
from devboard.db.repositories import DocumentRepository

router = APIRouter()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    document_repo: DocumentRepository = Depends(get_document_repository),
) -> DocumentResponse:
    """Get a specific document by ID."""
    document = document_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(document)
