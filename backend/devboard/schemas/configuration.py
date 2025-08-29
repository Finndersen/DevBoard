"""Configuration Pydantic schemas."""
import datetime
from typing import Optional

from pydantic import BaseModel


class ConfigurationBase(BaseModel):
    """Base configuration schema."""
    key: str
    value_json: str
    schema_version: str = "1.0"


class ConfigurationCreate(ConfigurationBase):
    """Schema for creating a new configuration."""
    pass


class ConfigurationUpdate(BaseModel):
    """Schema for updating a configuration."""
    value_json: Optional[str] = None
    schema_version: Optional[str] = None


class ConfigurationResponse(ConfigurationBase):
    """Schema for configuration responses."""
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ContextProviderLinkBase(BaseModel):
    """Base context provider link schema."""
    provider_name: str
    parent_id: int
    parent_type: str
    resource_uri: str
    description: Optional[str] = None
    auto_generated_description: bool = True


class ContextProviderLinkCreate(ContextProviderLinkBase):
    """Schema for creating a new context provider link."""
    pass


class ContextProviderLinkUpdate(BaseModel):
    """Schema for updating a context provider link."""
    provider_name: Optional[str] = None
    resource_uri: Optional[str] = None
    description: Optional[str] = None
    auto_generated_description: Optional[bool] = None


class ContextProviderLinkResponse(ContextProviderLinkBase):
    """Schema for context provider link responses."""
    id: int

    model_config = {"from_attributes": True}