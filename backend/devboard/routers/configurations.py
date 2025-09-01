"""Configuration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Configuration, ContextProviderLink
from devboard.repositories.configuration import ConfigurationRepository
from devboard.repositories.context_provider_link import ContextProviderLinkRepository
from devboard.schemas.configuration import (
    ConfigurationCreate,
    ConfigurationResponse,
    ConfigurationUpdate,
    ContextProviderLinkCreate,
    ContextProviderLinkResponse,
    ContextProviderLinkUpdate,
)

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


@router.delete("/{config_key}")
async def delete_configuration(config_key: str, db: Session = Depends(get_db)):
    """Delete a configuration."""
    config_repo = ConfigurationRepository(db)
    deleted = config_repo.delete_by_key(config_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.commit()
    return {"message": "Configuration deleted successfully"}


# Context Provider Link endpoints
@router.get("/provider-links/", response_model=list[ContextProviderLinkResponse])
async def list_provider_links(
    parent_type: str = None, parent_id: int = None, db: Session = Depends(get_db)
):
    """List context provider links, optionally filtered by parent."""
    link_repo = ContextProviderLinkRepository(db)
    if parent_type and parent_id:
        links = link_repo.get_by_parent(parent_id, parent_type)
    else:
        # For now, require both parameters - can extend later if needed
        raise HTTPException(status_code=400, detail="Both parent_type and parent_id are required")
    return links


@router.post("/provider-links/", response_model=ContextProviderLinkResponse)
async def create_provider_link(link: ContextProviderLinkCreate, db: Session = Depends(get_db)):
    """Create a new context provider link."""
    link_repo = ContextProviderLinkRepository(db)
    db_link = ContextProviderLink(**link.model_dump())
    created_link = link_repo.create(db_link)
    db.commit()
    db.refresh(created_link)
    return created_link


@router.patch("/provider-links/{link_id}", response_model=ContextProviderLinkResponse)
async def update_provider_link(
    link_id: int, link_update: ContextProviderLinkUpdate, db: Session = Depends(get_db)
):
    """Update a context provider link."""
    link_repo = ContextProviderLinkRepository(db)
    link = link_repo.get_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Context provider link not found")

    update_data = link_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)

    updated_link = link_repo.update(link)
    db.commit()
    db.refresh(updated_link)
    return updated_link


@router.delete("/provider-links/{link_id}")
async def delete_provider_link(link_id: int, db: Session = Depends(get_db)):
    """Delete a context provider link."""
    link_repo = ContextProviderLinkRepository(db)
    deleted = link_repo.delete_by_id(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Context provider link not found")

    db.commit()
    return {"message": "Context provider link deleted successfully"}
