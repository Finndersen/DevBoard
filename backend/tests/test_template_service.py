"""Tests for the TemplateService refactoring."""

from pathlib import Path

import pytest

from devboard.services.template_service import TemplateService, TemplateType


class TestTemplateService:
    """Test the refactored TemplateService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = TemplateService()

    def test_template_type_enum(self):
        """Test TemplateType enum values."""
        assert TemplateType.TASK_SPECIFICATION.value == "task_specification"
        assert TemplateType.IMPLEMENTATION_PLAN.value == "implementation_plan"
        assert TemplateType.ARCHITECTURE_DOCUMENT.value == "architecture_document"

    def test_get_template_task_specification(self):
        """Test getting task specification template."""
        template = self.service.get_template(TemplateType.TASK_SPECIFICATION)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Task: [Title]" in template
        assert "## Objective" in template
        assert "## Context" in template
        assert "## Requirements" in template

    def test_get_template_implementation_plan(self):
        """Test getting implementation plan template."""
        template = self.service.get_template(TemplateType.IMPLEMENTATION_PLAN)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Implementation Plan: [Title]" in template
        assert "## Summary" in template
        assert "## Technical Analysis" in template
        assert "## Implementation Steps" in template

    def test_get_template_architecture_document(self):
        """Test getting architecture document template."""
        template = self.service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Architecture Overview" in template
        assert "## Project Structure" in template
        assert "## Technology Stack" in template
        assert "## Key Components" in template

    def test_get_template_with_invalid_type(self):
        """Test getting template with invalid type."""
        with pytest.raises(ValueError, match="Unknown template type"):
            self.service.get_template("invalid_type")

    def test_legacy_get_task_specification_template(self):
        """Test legacy method for backward compatibility."""
        template = self.service.get_task_specification_template()

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Task: [Title]" in template

    def test_legacy_get_implementation_plan_template(self):
        """Test legacy method for backward compatibility."""
        template = self.service.get_implementation_plan_template()

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Implementation Plan: [Title]" in template

    def test_template_consistency(self):
        """Test that new and legacy methods return the same templates."""
        # Task specification
        new_spec = self.service.get_template(TemplateType.TASK_SPECIFICATION)
        legacy_spec = self.service.get_task_specification_template()
        assert new_spec == legacy_spec

        # Implementation plan
        new_plan = self.service.get_template(TemplateType.IMPLEMENTATION_PLAN)
        legacy_plan = self.service.get_implementation_plan_template()
        assert new_plan == legacy_plan

    def test_template_files_exist(self):
        """Test that template files exist in the expected location."""
        templates_dir = Path(__file__).parent.parent / "devboard" / "templates"

        # Check that architecture document template file exists
        arch_template_path = templates_dir / "architecture_document.md"
        assert arch_template_path.exists(), f"Architecture template not found at {arch_template_path}"

    def test_template_content_structure(self):
        """Test that templates have proper markdown structure."""
        templates = {
            TemplateType.TASK_SPECIFICATION: self.service.get_template(TemplateType.TASK_SPECIFICATION),
            TemplateType.IMPLEMENTATION_PLAN: self.service.get_template(TemplateType.IMPLEMENTATION_PLAN),
            TemplateType.ARCHITECTURE_DOCUMENT: self.service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)
        }

        for template_type, content in templates.items():
            # Each template should start with a main heading
            assert content.startswith("#"), f"{template_type.value} template should start with # heading"

            # Should contain placeholder for title replacement
            assert "[Title]" in content or "Architecture Overview" in content, \
                f"{template_type.value} template should contain title placeholder or specific title"

            # Should contain multiple sections (## headings)
            section_count = content.count("## ")
            assert section_count >= 3, f"{template_type.value} template should have at least 3 sections"

    def test_template_placeholder_replacement_example(self):
        """Test example of how templates would be used with placeholder replacement."""
        spec_template = self.service.get_template(TemplateType.TASK_SPECIFICATION)
        plan_template = self.service.get_template(TemplateType.IMPLEMENTATION_PLAN)

        # Example usage - replace title placeholder
        task_title = "Implement User Authentication"

        customized_spec = spec_template.replace("[Title]", task_title)
        customized_plan = plan_template.replace("[Title]", task_title)

        assert f"# Task: {task_title}" in customized_spec
        assert f"# Implementation Plan: {task_title}" in customized_plan

    def test_architecture_template_sections(self):
        """Test that architecture template has all expected sections."""
        template = self.service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)

        expected_sections = [
            "## Overview",
            "## Architecture Overview",
            "## Project Structure",
            "## Technology Stack",
            "## Key Components",
            "## API Endpoints",
            "## Data Models",
            "## Configuration & Environment",
            "## Development Patterns",
            "## Testing Strategy",
            "## Deployment & Operations",
            "## Getting Started"
        ]

        for section in expected_sections:
            assert section in template, f"Architecture template missing section: {section}"

    def test_template_service_singleton_behavior(self):
        """Test that TemplateService works consistently across instances."""
        service1 = TemplateService()
        service2 = TemplateService()

        # Both instances should return the same content
        template1 = service1.get_template(TemplateType.TASK_SPECIFICATION)
        template2 = service2.get_template(TemplateType.TASK_SPECIFICATION)

        assert template1 == template2

    def test_template_content_not_empty(self):
        """Test that all templates return non-empty content."""
        for template_type in TemplateType:
            template = self.service.get_template(template_type)
            assert template.strip(), f"{template_type.value} template should not be empty"
            assert len(template) > 100, f"{template_type.value} template should be substantial"

    def test_enum_iteration(self):
        """Test that all TemplateType enum values work with get_template."""
        for template_type in TemplateType:
            try:
                template = self.service.get_template(template_type)
                assert isinstance(template, str)
                assert len(template) > 0
            except Exception as e:
                pytest.fail(f"Failed to get template for {template_type.value}: {e}")
