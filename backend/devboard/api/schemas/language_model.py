"""Language model Pydantic schemas."""

import datetime

from pydantic import BaseModel

from devboard.agents.language_models import LLMProvider, ModelType


class LanguageModelResponse(BaseModel):
    """Schema for language model responses."""

    id: int
    provider: LLMProvider
    name: str
    model_type: ModelType
    full_name: str | None
    bedrock_id: str | None
    context_window: int | None
    model_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class CreateLanguageModelRequest(BaseModel):
    """Schema for creating a new language model."""

    provider: LLMProvider
    name: str
    model_type: ModelType
    full_name: str | None = None
    bedrock_id: str | None = None
    context_window: int | None = None


class UpdateLanguageModelRequest(BaseModel):
    """Schema for updating an existing language model."""

    provider: LLMProvider | None = None
    name: str | None = None
    model_type: ModelType | None = None
    full_name: str | None = None
    bedrock_id: str | None = None
    context_window: int | None = None
