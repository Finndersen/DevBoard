"""Configuration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.api.schemas import (
    ConfigurationCreate,
    ConfigurationResponse,
    ConfigurationUpdate,
    DeleteResponse,
)
from devboard.db.database import get_db
from devboard.db.models import Configuration
from devboard.db.repositories import ConfigurationRepository

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


@router.delete("/{config_key}", response_model=DeleteResponse)
async def delete_configuration(config_key: str, db: Session = Depends(get_db)):
    """Delete a configuration."""
    config_repo = ConfigurationRepository(db)
    deleted = config_repo.delete_by_key(config_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.commit()
    return {"message": "Configuration deleted successfully", "success": True}
