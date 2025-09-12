"""Document Pydantic schemas."""

import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    """Base document schema."""

    document_type: str
    content: str
    content_hash: str


class DocumentResponse(DocumentBase):
    """Schema for document responses."""

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""

    document_type: str
    content: str = ""


class DocumentUpdate(BaseModel):
    """Schema for updating document content."""

    content: str
