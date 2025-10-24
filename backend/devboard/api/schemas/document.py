"""Document Pydantic schemas."""

import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Schema for document responses."""

    id: int
    document_type: str
    content: str
    content_hash: str
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


class DocumentEdit(BaseModel):
    """Schema for a single document edit."""

    old_string: Annotated[
        str,
        Field(
            description="Text to find in the document to replace with new text. Use the MINIMUM necessary text to uniquely identify the location to replace.",
        ),
    ]
    new_string: Annotated[str, Field(description="New text to replace the found text with.")]
