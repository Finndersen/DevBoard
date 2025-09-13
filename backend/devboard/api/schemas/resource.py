from pydantic import BaseModel


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
