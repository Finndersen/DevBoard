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

    def get_template(self, template_type: TemplateType) -> str:
        """Get a template by type.

        Args:
            template_type: The type of template to retrieve (enum)

        Returns:
            Template content as string

        Raises:
            ValueError: If template_type is invalid
        """
        template_path = self.template_dir / f"{template_type.value}.md"

        if not template_path.exists():
            raise ValueError(f"Template file not found: {template_path}")

        return template_path.read_text(encoding="utf-8")


# Note: No global instance - use dependency injection
