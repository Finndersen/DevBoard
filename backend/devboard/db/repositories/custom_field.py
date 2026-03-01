"""Custom field repository for custom field definition data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import CustomFieldDefinition, CustomFieldType
from devboard.db.models.enums import EntityType
from devboard.db.repositories.base import BaseRepository


class CustomFieldRepository(BaseRepository[CustomFieldDefinition]):
    """Repository for custom field definition data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_all(self, entity_type: EntityType | None = None) -> list[CustomFieldDefinition]:
        """Get all custom field definitions, optionally filtered by entity type."""
        stmt = select(CustomFieldDefinition)
        if entity_type is not None:
            stmt = stmt.where(CustomFieldDefinition.entity_type == entity_type)
        stmt = stmt.order_by(CustomFieldDefinition.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, field_id: int) -> CustomFieldDefinition | None:
        stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.id == field_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str, entity_type: EntityType | None = None) -> CustomFieldDefinition | None:
        """Get a custom field definition by name, optionally scoped to entity type."""
        stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.name == name)
        if entity_type is not None:
            stmt = stmt.where(CustomFieldDefinition.entity_type == entity_type)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_mandatory_fields(self, entity_type: EntityType | None = None) -> list[CustomFieldDefinition]:
        """Get all mandatory custom field definitions, optionally filtered by entity type."""
        stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.mandatory.is_(True))
        if entity_type is not None:
            stmt = stmt.where(CustomFieldDefinition.entity_type == entity_type)
        stmt = stmt.order_by(CustomFieldDefinition.name)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        name: str,
        field_type: CustomFieldType,
        entity_type: EntityType = EntityType.TASK,
        description: str | None = None,
        options: list[str] | None = None,
        mandatory: bool = False,
    ) -> CustomFieldDefinition:
        field = CustomFieldDefinition(
            name=name,
            entity_type=entity_type,
            description=description,
            type=field_type,
            options=options,
            mandatory=mandatory,
        )

        self.db.add(field)
        self.db.flush()
        return field

    def update(
        self,
        field: CustomFieldDefinition,
        name: str | None = None,
        description: str | None = None,
        field_type: CustomFieldType | None = None,
        options: list[str] | None = None,
        mandatory: bool | None = None,
    ) -> CustomFieldDefinition:
        """Update an existing custom field definition.

        Args:
            field: CustomFieldDefinition instance to update
            name: Optional new name
            description: Optional new description
            field_type: Optional new field type
            options: Optional new options
            mandatory: Optional new mandatory flag

        Returns:
            Updated custom field definition
        """
        if name is not None:
            field.name = name
        if description is not None:
            field.description = description
        if field_type is not None:
            field.type = field_type
        if options is not None:
            field.options = options
        if mandatory is not None:
            field.mandatory = mandatory

        self.db.flush()
        self.db.refresh(field)
        return field

    def delete(self, field: CustomFieldDefinition) -> bool:
        """Delete a custom field definition.

        Note: This only deletes the definition. Existing task values are retained
        and will be displayed as plain "field: value" (orphaned fields).

        Args:
            field: CustomFieldDefinition instance to delete

        Returns:
            True if deleted successfully
        """
        self.db.delete(field)
        return True

    def delete_by_id(self, field_id: int) -> bool:
        """Delete a custom field definition by its ID.

        Args:
            field_id: The field definition ID to delete

        Returns:
            True if field was deleted, False if not found
        """
        field = self.get_by_id(field_id)
        if field:
            self.db.delete(field)
            return True
        return False
