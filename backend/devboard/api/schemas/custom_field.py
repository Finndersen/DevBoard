"""Custom field Pydantic schemas."""

import datetime

from pydantic import BaseModel, field_validator, model_validator

from devboard.db.models.custom_field import CustomFieldType
from devboard.db.models.enums import EntityType


class CustomFieldCreate(BaseModel):
    """Schema for creating a new custom field definition."""

    name: str
    entity_type: EntityType = EntityType.TASK
    description: str | None = None
    type: CustomFieldType
    options: list[str] | None = None
    mandatory: bool = False

    @model_validator(mode="after")
    def validate_options_for_enum(self) -> "CustomFieldCreate":
        """Validate that options are provided when type is ENUM."""
        if self.type == CustomFieldType.ENUM:
            if not self.options or len(self.options) == 0:
                raise ValueError("options is required when type is 'enum'")
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty and has reasonable length."""
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        if len(v) > 100:
            raise ValueError("name cannot exceed 100 characters")
        return v


class CustomFieldUpdate(BaseModel):
    """Schema for updating a custom field definition."""

    name: str | None = None
    description: str | None = None
    type: CustomFieldType | None = None
    options: list[str] | None = None
    mandatory: bool | None = None

    @model_validator(mode="after")
    def validate_options_for_enum(self) -> "CustomFieldUpdate":
        """Validate that options are provided when type is changed to ENUM."""
        if self.type == CustomFieldType.ENUM:
            if self.options is not None and len(self.options) == 0:
                raise ValueError("options cannot be empty when type is 'enum'")
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate that name is not empty and has reasonable length."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name cannot be empty")
            if len(v) > 100:
                raise ValueError("name cannot exceed 100 characters")
        return v


class CustomFieldResponse(BaseModel):
    """Schema for custom field definition responses."""

    id: int
    name: str
    entity_type: EntityType
    description: str | None
    type: CustomFieldType
    options: list[str] | None
    mandatory: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
