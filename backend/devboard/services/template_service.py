"""Template service for document templates."""

from enum import Enum
from pathlib import Path


class TemplateType(Enum):
    """Available template types."""

    TASK_SPECIFICATION = "task_specification"
    IMPLEMENTATION_PLAN = "implementation_plan"
    ARCHITECTURE_DOCUMENT = "architecture_document"


class TemplateService:
    """Service for managing document templates."""

    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates"

    def get_template(self, template_type: TemplateType | str) -> str:
        """Get a template by type.
        
        Args:
            template_type: The type of template to retrieve (enum or string)
            
        Returns:
            Template content as string
            
        Raises:
            ValueError: If template_type is invalid
        """
        # Handle both enum and string inputs
        if isinstance(template_type, str):
            # Check if string is a valid enum value
            try:
                template_type = TemplateType(template_type)
            except ValueError:
                raise ValueError(f"Unknown template type: {template_type}")

        template_path = self.template_dir / f"{template_type.value}.md"

        if not template_path.exists():
            raise ValueError(f"Template file not found: {template_path}")

        return template_path.read_text(encoding="utf-8")

    # Legacy methods for backward compatibility - will be removed after migration
    def get_task_specification_template(self) -> str:
        """Get the task specification template."""
        return self.get_template(TemplateType.TASK_SPECIFICATION)

    def get_implementation_plan_template(self) -> str:
        """Get the implementation plan template."""
        return self.get_template(TemplateType.IMPLEMENTATION_PLAN)


# Global instance
template_service = TemplateService()
