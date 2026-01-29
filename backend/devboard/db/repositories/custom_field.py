"""Custom field repository for custom field definition data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import CustomFieldDefinition, CustomFieldType
from devboard.db.repositories.base import BaseRepository


class CustomFieldRepository(BaseRepository[CustomFieldDefinition]):
    """Repository for custom field definition data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_all(self) -> list[CustomFieldDefinition]:
        """Get all custom field definitions.

        Returns:
            List of all custom field definitions ordered by name
        """
        stmt = select(CustomFieldDefinition).order_by(CustomFieldDefinition.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, field_id: int) -> CustomFieldDefinition | None:
        """Get a custom field definition by its ID.

        Args:
            field_id: The field definition ID to search for

        Returns:
            CustomFieldDefinition instance if found, None otherwise
        """
        stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.id == field_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> CustomFieldDefinition | None:
        """Get a custom field definition by its name.

        Args:
            name: The field name to search for

        Returns:
            CustomFieldDefinition instance if found, None otherwise
        """
        stmt = select(CustomFieldDefinition).where(CustomFieldDefinition.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_mandatory_fields(self) -> list[CustomFieldDefinition]:
        """Get all mandatory custom field definitions.

        Returns:
            List of custom field definitions where mandatory is True
        """
        stmt = (
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.mandatory.is_(True))
            .order_by(CustomFieldDefinition.name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        name: str,
        field_type: CustomFieldType,
        description: str | None = None,
        options: list[str] | None = None,
        mandatory: bool = False,
    ) -> CustomFieldDefinition:
        """Create a new custom field definition.

        Args:
            name: Field name (unique identifier/label)
            field_type: Field type (TEXT, BOOLEAN, or ENUM)
            description: Optional help text for users
            options: Required if field_type is ENUM - allowed values
            mandatory: Whether field is required on task creation

        Returns:
            Created custom field definition with assigned ID
        """
        field = CustomFieldDefinition(
            name=name,
            description=description,
            type=field_type,
            options=options,
            mandatory=mandatory,
        )

        self.db.add(field)
        self.db.flush()  # Get the ID without committing
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
