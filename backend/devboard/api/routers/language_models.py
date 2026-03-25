"""Language model API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.repositories import get_language_model_repository
from devboard.api.dependencies.services import get_language_model_service
from devboard.api.schemas.language_model import (
    CreateLanguageModelRequest,
    LanguageModelResponse,
    UpdateLanguageModelRequest,
)
from devboard.db.repositories.language_model import LanguageModelRepository
from devboard.services.language_model_service import DuplicateLanguageModelError, LanguageModelService

router = APIRouter()


@router.get("/", response_model=list[LanguageModelResponse])
def list_language_models(
    repo: LanguageModelRepository = Depends(get_language_model_repository),
):
    """List all language models."""
    return repo.get_all()


@router.post("/", response_model=LanguageModelResponse, status_code=201)
def create_language_model(
    data: CreateLanguageModelRequest,
    service: LanguageModelService = Depends(get_language_model_service),
):
    """Create a new language model."""
    try:
        return service.create_model(
            provider=data.provider,
            name=data.name,
            model_type=data.model_type,
            full_name=data.full_name,
            bedrock_id=data.bedrock_id,
            context_window=data.context_window,
        )
    except DuplicateLanguageModelError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.put("/{model_id}", response_model=LanguageModelResponse)
def update_language_model(
    model_id: int,
    data: UpdateLanguageModelRequest,
    service: LanguageModelService = Depends(get_language_model_service),
):
    """Update an existing language model."""
    try:
        model = service.update_model(
            model_id=model_id,
            fields=data.model_dump(exclude_unset=True),
        )
    except DuplicateLanguageModelError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    if model is None:
        raise HTTPException(status_code=404, detail="Language model not found")
    return model


@router.delete("/{model_id}")
def delete_language_model(
    model_id: int,
    service: LanguageModelService = Depends(get_language_model_service),
):
    """Delete a language model."""
    deleted = service.delete_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Language model not found")
    return {"message": "Language model deleted successfully", "success": True}
