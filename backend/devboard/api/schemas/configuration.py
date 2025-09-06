"""Configuration Pydantic schemas."""

import datetime
from typing import Any

from pydantic import BaseModel


class ConfigurationFieldInfo(BaseModel):
    """Information about a single configuration field with source tracking."""

    name: str
    type: str  # "string", "boolean", "integer", "number"
    required: bool
    description: str | None = None
    current_value: Any | None = None
    value_source: str | None = None  # "environment", "database", "default"
    is_secret: bool = False
    env_var_name: str | None = None
    default_value: Any | None = None
    env_value_present: bool = False


class ConfigurationDetailResponse(BaseModel):
    """Detailed configuration response with field-level information."""

    key: str
    fields: list[ConfigurationFieldInfo]
    validation_status: str  # "valid", "invalid", "unconfigured"
    validation_errors: list[str] | None = None


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

    value_json: str | None = None
    schema_version: str | None = None


class ConfigurationResponse(ConfigurationBase):
    """Schema for configuration responses."""

    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ContextProviderResourceBase(BaseModel):
    """Base context provider resource schema."""

    provider_name: str
    parent_id: int
    parent_type: str
    resource_uri: str
    description: str | None = None
    auto_generated_description: bool = True


class ContextProviderResourceCreate(ContextProviderResourceBase):
    """Schema for creating a new context provider resource."""

    pass


class ContextProviderResourceUpdate(BaseModel):
    """Schema for updating a context provider resource."""

    provider_name: str | None = None
    resource_uri: str | None = None
    description: str | None = None
    auto_generated_description: bool | None = None


class ContextProviderResourceResponse(ContextProviderResourceBase):
    """Schema for context provider resource responses."""

    id: int

    model_config = {"from_attributes": True}


class ProjectResourceCreate(BaseModel):
    """Schema for creating a context provider resource for a project."""

    resource_uri: str
    description: str | None = None


class TaskResourceCreate(BaseModel):
    """Schema for creating a context provider resource for a task."""

    resource_uri: str
    description: str | None = None


class ResourceResponse(BaseModel):
    """Schema for context provider resource responses in domain-specific endpoints."""

    id: int
    resource_uri: str
    description: str | None = None

    model_config = {"from_attributes": True}
