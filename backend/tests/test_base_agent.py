"""Tests for BaseAgentService."""

from unittest.mock import MagicMock, patch

import pytest

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.types import AgentType
from devboard.api.schemas.task import DocumentEdit


class MockBaseDeps(BaseDeps):
    """Mock context for BaseAgentService testing."""

    test_field: str = "test_value"


class MockBaseAgent(BaseAgent):
    """Mock implementation of BaseAgentService."""

    def __init__(self):
        super().__init__(AgentType.PROJECT, None)

    def _create_agent(self):
        return MagicMock()

    def _get_system_prompt(self) -> str:
        return "Test system prompt"


class TestBaseAgentServiceUnit:
    """Test BaseAgentService functionality."""

    @pytest.fixture
    def base_agent_service(self):
        """Create test BaseAgentService instance."""
        return MockBaseAgent()

    @pytest.fixture
    def mock_agent_result(self):
        """Mock agent result with messages."""
        mock_result = MagicMock()
        mock_result.all_messages.return_value = [
            {"kind": "request", "parts": [{"text": "Test user message"}]},
            {"kind": "response", "parts": [{"text": "Test agent response"}]},
        ]
        return mock_result

    def test_serialize_messages(self, base_agent_service, mock_agent_result):
        """Test message serialization."""
        result = base_agent_service.serialize_messages(mock_agent_result)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["kind"] == "request"
        assert result[1]["kind"] == "response"

    def test_extract_message_history_from_records_empty(self, base_agent_service):
        """Test extracting message history from empty records."""
        result = base_agent_service.extract_message_history_from_records([])

        assert result == []

    def test_extract_message_history_from_records_with_data(self, base_agent_service):
        """Test extracting message history from database records."""
        # Mock database records
        mock_record1 = MagicMock()
        mock_record1.message_type = "request"
        mock_record1.pydantic_content = [{"kind": "request", "parts": [{"text": "User message"}]}]

        mock_record2 = MagicMock()
        mock_record2.message_type = "response"
        mock_record2.pydantic_content = [
            {"kind": "response", "parts": [{"text": "Agent response"}]}
        ]

        records = [mock_record1, mock_record2]

        result = base_agent_service.extract_message_history_from_records(records)

        assert isinstance(result, list)
        assert len(result) == 2

    @patch("devboard.agents.base_agent.document_editor_service")
    def test_create_document_edit_tool(self, mock_editor_service, base_agent_service):
        """Test creating document edit tool."""
        # Mock the document editor service
        mock_editor_service.validate_edits.return_value = []

        def get_current_content(ctx):
            return "Current document content"

        tool_func = base_agent_service.create_document_edit_tool(
            "test_document", get_current_content
        )

        assert callable(tool_func)

    @patch("devboard.agents.base_agent.document_editor_service")
    @pytest.mark.asyncio
    async def test_document_edit_tool_validation_success(
        self, mock_editor_service, base_agent_service
    ):
        """Test document edit tool with successful validation."""
        # Mock the document editor service
        mock_editor_service.validate_edits.return_value = []  # Empty list means success

        def get_current_content(ctx):
            return "Current document content"

        tool_func = base_agent_service.create_document_edit_tool(
            "test_document", get_current_content
        )

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.deps = MockBaseDeps()

        # Test edits
        edits = [DocumentEdit(find="old text", replace="new text")]

        result = await tool_func(mock_ctx, edits, "Test edit reasoning")

        assert "successfully validated" in result
        mock_service_instance.validate_edits.assert_called_once()

    @patch("devboard.agents.base_agent.document_editor_service")
    @pytest.mark.asyncio
    async def test_document_edit_tool_validation_failure(
        self, mock_editor_service, base_agent_service
    ):
        """Test document edit tool with validation failure."""
        # Mock the document editor service
        mock_editor_service.validate_edits.return_value = ["Text not found"]  # Error list

        def get_current_content(ctx):
            return "Current document content"

        tool_func = base_agent_service.create_document_edit_tool(
            "test_document", get_current_content
        )

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.deps = MockBaseDeps()

        # Test edits
        edits = [DocumentEdit(find="nonexistent text", replace="new text")]

        result = await tool_func(mock_ctx, edits, "Test edit reasoning")

        assert "validation failed" in result.lower()
        assert "Text not found" in result
        mock_service_instance.validate_edits.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_with_history_not_implemented(self, base_agent_service):
        """Test that process_message_with_history raises NotImplementedError."""
        mock_context = MockBaseDeps()

        with pytest.raises(NotImplementedError):
            await base_agent_service.run("test message", [], mock_context)

    @pytest.mark.asyncio
    async def test_process_tool_approval_not_implemented(self, base_agent_service):
        """Test that process_tool_approval raises NotImplementedError."""
        mock_context = MockBaseDeps()

        with pytest.raises(NotImplementedError):
            await base_agent_service.process_tool_approval([], [], mock_context)

    def test_get_preferred_model_fallback(self, base_agent_service):
        """Test _get_preferred_model returns fallback when no models available."""
        with patch("devboard.agents.base_agent.llm_service") as mock_llm_service:
            mock_llm_service.get_preferred_model_for_agent.return_value = None

            result = base_agent_service._get_preferred_model()

            assert result == "test"  # Fallback model

    def test_get_preferred_model_success(self, base_agent_service):
        """Test _get_preferred_model returns preferred model when available."""
        with patch("devboard.agents.base_agent.llm_service") as mock_llm_service:
            mock_llm_service.get_preferred_model_for_agent.return_value = "openai/gpt-4"

            result = base_agent_service._get_preferred_model()

            assert result == "openai/gpt-4"
