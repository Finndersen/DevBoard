"""Tests for the TemplateService."""

import pytest

from devboard.services.template_service import TemplateService, TemplateType


@pytest.fixture
def template_service():
    """Template service instance for testing."""
    return TemplateService()


class TestTemplateService:
    """Test the TemplateService functionality."""

    def test_get_template_task_specification(self, template_service):
        """Test getting task specification template."""
        template = template_service.get_template(TemplateType.TASK_SPECIFICATION)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Task: [Title]" in template
        assert "## Objective" in template
        assert "## Context" in template
        assert "## Requirements" in template

    def test_get_template_implementation_plan(self, template_service):
        """Test getting implementation plan template."""
        template = template_service.get_template(TemplateType.IMPLEMENTATION_PLAN)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Implementation Plan: [Title]" in template
        assert "## Summary" in template
        assert "## Technical Analysis" in template
        assert "## Implementation Steps" in template

    def test_get_template_architecture_document(self, template_service):
        """Test getting architecture document template."""
        template = template_service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)

        assert isinstance(template, str)
        assert len(template) > 0
        assert "# Architecture Overview" in template
        assert "## Project Structure" in template
        assert "## Technology Stack" in template
        assert "## Key Components" in template

    def test_template_content_structure(self, template_service):
        """Test that templates have proper markdown structure."""
        templates = {
            TemplateType.TASK_SPECIFICATION: template_service.get_template(TemplateType.TASK_SPECIFICATION),
            TemplateType.IMPLEMENTATION_PLAN: template_service.get_template(TemplateType.IMPLEMENTATION_PLAN),
            TemplateType.ARCHITECTURE_DOCUMENT: template_service.get_template(TemplateType.ARCHITECTURE_DOCUMENT),
        }

        for template_type, content in templates.items():
            # Each template should start with a main heading
            assert content.startswith("#"), f"{template_type.value} template should start with # heading"

            # Should contain placeholder for title replacement
            assert "[Title]" in content or "Architecture Overview" in content, (
                f"{template_type.value} template should contain title placeholder or specific title"
            )

            # Should contain multiple sections (## headings)
            section_count = content.count("## ")
            assert section_count >= 3, f"{template_type.value} template should have at least 3 sections"

    def test_template_placeholder_replacement_example(self, template_service):
        """Test example of how templates would be used with placeholder replacement."""
        spec_template = template_service.get_template(TemplateType.TASK_SPECIFICATION)
        plan_template = template_service.get_template(TemplateType.IMPLEMENTATION_PLAN)

        # Example usage - replace title placeholder
        task_title = "Implement User Authentication"

        customized_spec = spec_template.replace("[Title]", task_title)
        customized_plan = plan_template.replace("[Title]", task_title)

        assert f"# Task: {task_title}" in customized_spec
        assert f"# Implementation Plan: {task_title}" in customized_plan

    def test_architecture_template_sections(self, template_service):
        """Test that architecture template has all expected sections."""
        template = template_service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)

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
            "## Getting Started",
        ]

        for section in expected_sections:
            assert section in template, f"Architecture template missing section: {section}"

    def test_all_templates_available(self, template_service):
        """Test that all template types return valid content."""
        for template_type in TemplateType:
            template = template_service.get_template(template_type)
            assert isinstance(template, str)
            assert template.strip(), f"{template_type.value} template should not be empty"
