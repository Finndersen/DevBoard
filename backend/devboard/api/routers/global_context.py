"""Global context API endpoints."""

from fastapi import APIRouter, Depends

from devboard.api.dependencies.services import get_global_context_service
from devboard.api.schemas.global_context import GlobalContextResponse, GlobalContextUpdate
from devboard.services.global_context_service import GlobalContextService

router = APIRouter()


@router.get("/", response_model=GlobalContextResponse)
async def get_global_context(
    service: GlobalContextService = Depends(get_global_context_service),
) -> GlobalContextResponse:
    """Get the workspace-level global context document."""
    data = service.get()
    return GlobalContextResponse(content=data.content, content_hash=data.content_hash, updated_at=data.updated_at)


@router.put("/", response_model=GlobalContextResponse)
async def update_global_context(
    body: GlobalContextUpdate,
    service: GlobalContextService = Depends(get_global_context_service),
) -> GlobalContextResponse:
    """Update the workspace-level global context document."""
    data = service.update(body.content)
    return GlobalContextResponse(content=data.content, content_hash=data.content_hash, updated_at=data.updated_at)
