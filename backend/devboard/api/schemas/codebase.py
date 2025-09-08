"""Codebase Pydantic schemas."""

from pydantic import BaseModel


class CodebaseBase(BaseModel):
    """Base codebase schema."""

    name: str
    description: str
    repository_url: str | None = None
    local_path: str


class CodebaseCreate(BaseModel):
    """Schema for creating a new codebase."""

    name: str
    description: str
    local_path: str


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""

    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    local_path: str | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}


class ArchitectureStatusResponse(BaseModel):
    """Schema for architecture document status response."""

    exists: bool
    file_path: str | None = None
    size_bytes: int | None = None


class ArchitectureContentResponse(BaseModel):
    """Schema for architecture document content response."""

    content: str | None = None
    exists: bool


class ArchitectureGenerationResponse(BaseModel):
    """Schema for architecture document generation response."""

    success: bool
    file_path: str | None = None
    content: str | None = None
    error_message: str | None = None
    error_type: str | None = None


class ArchitectureDocumentResponse(BaseModel):
    """Schema for combined architecture document response."""

    exists: bool
    content: str | None = None
    content_hash: str | None = None
    file_path: str | None = None
    size_bytes: int | None = None


class ArchitectureUpdateRequest(BaseModel):
    """Schema for updating architecture document."""

    content: str
    original_hash: str | None = None  # None for new documents


class ArchitectureUpdateResponse(BaseModel):
    """Schema for architecture document update response."""

    success: bool
    content_hash: str | None = None
    message: str | None = None
    error_type: str | None = None
    current_hash: str | None = None  # Returned on conflict for retry
