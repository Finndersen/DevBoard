"""Configuration API endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Configuration, ContextProviderLink
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
@router.get("/", response_model=List[ConfigurationResponse])
async def list_configurations(prefix: str = None, db: Session = Depends(get_db)):
    """List all configurations, optionally filtered by key prefix."""
    query = db.query(Configuration)
    if prefix:
        query = query.filter(Configuration.key.startswith(prefix))
    configs = query.all()
    return configs


@router.get("/{config_key}", response_model=ConfigurationResponse)
async def get_configuration(config_key: str, db: Session = Depends(get_db)):
    """Get a specific configuration."""
    config = db.query(Configuration).filter(Configuration.key == config_key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.post("/", response_model=ConfigurationResponse)
async def create_configuration(config: ConfigurationCreate, db: Session = Depends(get_db)):
    """Create or update a configuration."""
    # Check if configuration already exists
    existing = db.query(Configuration).filter(Configuration.key == config.key).first()
    if existing:
        # Update existing configuration
        for field, value in config.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new configuration
        db_config = Configuration(**config.model_dump())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config


@router.patch("/{config_key}", response_model=ConfigurationResponse)
async def update_configuration(
    config_key: str, config_update: ConfigurationUpdate, db: Session = Depends(get_db)
):
    """Update a configuration."""
    config = db.query(Configuration).filter(Configuration.key == config_key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_key}")
async def delete_configuration(config_key: str, db: Session = Depends(get_db)):
    """Delete a configuration."""
    config = db.query(Configuration).filter(Configuration.key == config_key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    db.delete(config)
    db.commit()
    return {"message": "Configuration deleted successfully"}


# Context Provider Link endpoints
@router.get("/provider-links/", response_model=List[ContextProviderLinkResponse])
async def list_provider_links(
    parent_type: str = None, parent_id: int = None, db: Session = Depends(get_db)
):
    """List context provider links, optionally filtered by parent."""
    query = db.query(ContextProviderLink)
    if parent_type:
        query = query.filter(ContextProviderLink.parent_type == parent_type)
    if parent_id:
        query = query.filter(ContextProviderLink.parent_id == parent_id)
    links = query.all()
    return links


@router.post("/provider-links/", response_model=ContextProviderLinkResponse)
async def create_provider_link(link: ContextProviderLinkCreate, db: Session = Depends(get_db)):
    """Create a new context provider link."""
    db_link = ContextProviderLink(**link.model_dump())
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


@router.patch("/provider-links/{link_id}", response_model=ContextProviderLinkResponse)
async def update_provider_link(
    link_id: int, link_update: ContextProviderLinkUpdate, db: Session = Depends(get_db)
):
    """Update a context provider link."""
    link = db.query(ContextProviderLink).filter(ContextProviderLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Context provider link not found")
    
    update_data = link_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(link, field, value)
    
    db.commit()
    db.refresh(link)
    return link


@router.delete("/provider-links/{link_id}")
async def delete_provider_link(link_id: int, db: Session = Depends(get_db)):
    """Delete a context provider link."""
    link = db.query(ContextProviderLink).filter(ContextProviderLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Context provider link not found")
    
    db.delete(link)
    db.commit()
    return {"message": "Context provider link deleted successfully"}