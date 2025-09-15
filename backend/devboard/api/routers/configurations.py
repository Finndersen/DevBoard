"""Configuration API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.services import get_config_service
from devboard.api.schemas import (
    ConfigurationDetailResponse,
    DeleteResponse,
)
from devboard.services.config_service import ConfigService

router = APIRouter()


# Configuration endpoints
@router.get("/")
async def list_configurations(
    prefix: str, config_service: ConfigService = Depends(get_config_service)
) -> list[ConfigurationDetailResponse]:
    """List configuration details, filtered by key prefix."""
    keys = config_service.list_configs(prefix=prefix)
    results = []

    for key in keys:
        config_detail = config_service.get_config_details_by_key(key)
        if config_detail is not None:
            results.append(config_detail)

    return results


@router.get("/{config_key}/detail", response_model=ConfigurationDetailResponse)
async def get_configuration_detail(config_key: str, config_service: ConfigService = Depends(get_config_service)):
    """Get detailed configuration with field-level source information."""
    result = config_service.get_config_details_by_key(config_key)

    # If the configuration schema doesn't exist, return 404
    if result is None:
        raise HTTPException(status_code=404, detail="Configuration schema not found")

    return result


@router.patch("/{config_key}", response_model=ConfigurationDetailResponse)
async def update_configuration(
    config_key: str,
    config_data: dict[str, Any],
    config_service: ConfigService = Depends(get_config_service),
):
    """Update configuration with complete structure. None values clear DB overrides."""
    try:
        result = config_service.update_configuration(config_key, config_data)
        return result
    except ValueError as e:
        if "No schema registered" in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        else:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{config_key}", response_model=DeleteResponse)
async def delete_configuration(config_key: str, config_service: ConfigService = Depends(get_config_service)):
    """Delete a configuration."""
    try:
        config_service.delete_config(config_key)
        return {"message": "Configuration deleted successfully", "success": True}
    except Exception as e:
        raise HTTPException(status_code=404, detail="Configuration not found") from e
