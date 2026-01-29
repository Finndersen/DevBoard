"""Custom field API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.repositories import get_custom_field_repository
from devboard.api.schemas import (
    CustomFieldCreate,
    CustomFieldResponse,
    CustomFieldUpdate,
    DeleteResponse,
)
from devboard.db.models.custom_field import CustomFieldType
from devboard.db.repositories import CustomFieldRepository

router = APIRouter()


@router.get("/", response_model=list[CustomFieldResponse])
async def list_custom_fields(
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """List all custom field definitions."""
    fields = custom_field_repo.get_all()
    return fields


@router.post("/", response_model=CustomFieldResponse, status_code=201)
async def create_custom_field(
    field_data: CustomFieldCreate,
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Create a new custom field definition.

    Args:
        field_data: The custom field definition data

    Returns:
        Created custom field definition

    Raises:
        HTTPException: If field name already exists
    """
    # Check if field with same name already exists
    existing = custom_field_repo.get_by_name(field_data.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Custom field with name '{field_data.name}' already exists",
        )

    # Create the field
    field = custom_field_repo.create(
        name=field_data.name,
        field_type=field_data.type,
        description=field_data.description,
        options=field_data.options,
        mandatory=field_data.mandatory,
    )

    custom_field_repo.commit()
    return field


@router.get("/{field_id}", response_model=CustomFieldResponse)
async def get_custom_field(
    field_id: int,
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Get a specific custom field definition.

    Args:
        field_id: The ID of the custom field definition

    Returns:
        Custom field definition

    Raises:
        HTTPException: If field not found
    """
    field = custom_field_repo.get_by_id(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    return field


@router.patch("/{field_id}", response_model=CustomFieldResponse)
async def update_custom_field(
    field_id: int,
    field_data: CustomFieldUpdate,
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Update a custom field definition.

    Args:
        field_id: The ID of the custom field definition
        field_data: The update data

    Returns:
        Updated custom field definition

    Raises:
        HTTPException: If field not found or name conflict
    """
    field = custom_field_repo.get_by_id(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")

    # Check for name conflict if name is being changed
    if field_data.name is not None and field_data.name != field.name:
        existing = custom_field_repo.get_by_name(field_data.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Custom field with name '{field_data.name}' already exists",
            )

    # If type is being changed to ENUM, validate options
    new_type = field_data.type if field_data.type is not None else field.type
    new_options = field_data.options if field_data.options is not None else field.options

    if new_type == CustomFieldType.ENUM:
        if not new_options or len(new_options) == 0:
            raise HTTPException(
                status_code=400,
                detail="options is required when type is 'enum'",
            )

    # Update the field
    updated_field = custom_field_repo.update(
        field=field,
        name=field_data.name,
        description=field_data.description,
        field_type=field_data.type,
        options=field_data.options,
        mandatory=field_data.mandatory,
    )

    custom_field_repo.commit()
    return updated_field


@router.delete("/{field_id}", response_model=DeleteResponse)
async def delete_custom_field(
    field_id: int,
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Delete a custom field definition.

    Note: This only deletes the definition. Existing task values are retained
    and will be displayed as plain "field: value" (orphaned fields).

    Args:
        field_id: The ID of the custom field definition

    Returns:
        Success message

    Raises:
        HTTPException: If field not found
    """
    deleted = custom_field_repo.delete_by_id(field_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Custom field not found")

    custom_field_repo.commit()
    return {"message": "Custom field deleted successfully", "success": True}
