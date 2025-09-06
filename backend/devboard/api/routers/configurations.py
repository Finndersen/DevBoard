"""Configuration API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.api.schemas import (
    ConfigurationCreate,
    ConfigurationDetailResponse,
    ConfigurationResponse,
    ConfigurationUpdate,
    DeleteResponse,
)
from devboard.db.database import get_db
from devboard.db.models import Configuration
from devboard.db.repositories import ConfigurationRepository
from devboard.services.config_service import config_service

router = APIRouter()


# Configuration endpoints
@router.get("/", response_model=list[ConfigurationResponse])
async def list_configurations(prefix: str = None, db: Session = Depends(get_db)):
    """List all configurations, optionally filtered by key prefix."""
    config_repo = ConfigurationRepository(db)
    configs = config_repo.get_all(prefix=prefix)
    return configs


@router.get("/{config_key}", response_model=ConfigurationResponse)
async def get_configuration(config_key: str, db: Session = Depends(get_db)):
    """Get a specific configuration."""
    config_repo = ConfigurationRepository(db)
    config = config_repo.get_by_key(config_key)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.get("/{config_key}/detail", response_model=ConfigurationDetailResponse)
async def get_configuration_detail(config_key: str):
    """Get detailed configuration with field-level source information."""
    result = config_service.get_config_details(config_key)

    # If the configuration schema doesn't exist, return 404
    if result.validation_status == "unconfigured" and not result.fields:
        raise HTTPException(status_code=404, detail="Configuration schema not found")

    return result


@router.post("/", response_model=ConfigurationResponse)
async def create_configuration(config: ConfigurationCreate, db: Session = Depends(get_db)):
    """Create or update a configuration."""
    config_repo = ConfigurationRepository(db)
    # Check if configuration already exists
    existing = config_repo.get_by_key(config.key)
    if existing:
        # Update existing configuration
        for field, value in config.model_dump().items():
            setattr(existing, field, value)
        updated_config = config_repo.update(existing)
        db.commit()
        db.refresh(updated_config)
        return updated_config
    else:
        # Create new configuration
        db_config = Configuration(**config.model_dump())
        created_config = config_repo.create(db_config)
        db.commit()
        db.refresh(created_config)
        return created_config


@router.patch("/{config_key}", response_model=ConfigurationResponse)
async def update_configuration(
    config_key: str, config_update: ConfigurationUpdate, db: Session = Depends(get_db)
):
    """Update a configuration."""
    config_repo = ConfigurationRepository(db)
    config = config_repo.get_by_key(config_key)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    updated_config = config_repo.update(config)
    db.commit()
    db.refresh(updated_config)
    return updated_config


@router.patch("/{config_key}/fields", response_model=ConfigurationDetailResponse)
async def update_configuration_fields(
    config_key: str, field_updates: dict[str, Any]
):
    """Update specific configuration fields while respecting environment variable precedence."""
    try:
        result = config_service.update_config_fields(config_key, field_updates)
        return result
    except ValueError as e:
        if "environment variables" in str(e):
            raise HTTPException(status_code=400, detail=str(e)) from e
        elif "No schema registered" in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        else:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{config_key}", response_model=DeleteResponse)
async def delete_configuration(config_key: str, db: Session = Depends(get_db)):
    """Delete a configuration."""
    config_repo = ConfigurationRepository(db)
    deleted = config_repo.delete_by_key(config_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.commit()
    return {"message": "Configuration deleted successfully", "success": True}
