"""Tests for sub-agent tools, including the codebase investigation tool."""

from typing import Literal
from unittest.mock import Mock

import pytest
from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.tools.sub_agent_tools import create_codebase_investigation_tool
from devboard.db.models.codebase import Codebase


@pytest.fixture
def mock_codebases():
    """Create mock Codebase instances."""
    backend = Mock(spec=Codebase)
    backend.id = 1
    backend.name = "backend"
    backend.description = "Backend codebase"
    backend.local_path = "/path/to/backend"

    frontend = Mock(spec=Codebase)
    frontend.id = 2
    frontend.name = "frontend"
    frontend.description = "Frontend codebase"
    frontend.local_path = "/path/to/frontend"

    return [backend, frontend]


@pytest.fixture
def mock_agent_config_service():
    """Create a mock AgentConfigService."""
    return Mock(spec=AgentConfigService)


class TestCreateCodebaseInvestigationTool:
    """Tests for create_codebase_investigation_tool."""

    def test_tool_creation_with_single_codebase(self, mock_codebases, mock_agent_config_service):
        """Test tool is created correctly with a single codebase."""
        tool = create_codebase_investigation_tool(
            [mock_codebases[0]],
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_tool_creation_with_multiple_codebases(self, mock_codebases, mock_agent_config_service):
        """Test tool is created correctly with multiple codebases."""
        tool = create_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_raises_error_with_empty_list(self, mock_agent_config_service):
        """Test that empty codebase list raises ValueError."""
        with pytest.raises(ValueError, match="At least one codebase must be provided"):
            create_codebase_investigation_tool([], mock_agent_config_service)

    def test_dynamic_literal_annotation_single_codebase(self, mock_codebases, mock_agent_config_service):
        """Test that Literal annotation is set correctly for single codebase."""
        tool = create_codebase_investigation_tool(
            [mock_codebases[0]],
            mock_agent_config_service,
        )

        # Check that the annotation was dynamically set
        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        # The annotation should be a Literal type with the codebase name
        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal

        # Check the literal values
        assert codebase_name_type.__args__ == ("backend",)

    def test_dynamic_literal_annotation_multiple_codebases(self, mock_codebases, mock_agent_config_service):
        """Test that Literal annotation is set correctly for multiple codebases."""
        tool = create_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        # Check that the annotation was dynamically set
        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        # The annotation should be a Literal type with all codebase names
        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal

        # Check the literal values
        assert set(codebase_name_type.__args__) == {"backend", "frontend"}

    def test_function_signature_has_codebase_name_parameter(self, mock_codebases, mock_agent_config_service):
        """Test that the tool function has a codebase_name parameter."""
        tool = create_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        # Get function signature
        import inspect

        sig = inspect.signature(tool.function)
        params = sig.parameters

        # Check parameters exist
        assert "query" in params
        assert "codebase_name" in params

        # Check parameter annotations
        assert params["query"].annotation is str
        assert params["codebase_name"].annotation is not str  # Should be Literal type
