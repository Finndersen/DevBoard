"""Tests for BaseAgent abstract class."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.tools import DeferredToolApprovalResult

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.types import AgentType


class MockDeps(BaseDeps):
    """Mock dependencies for testing."""

    test_field: str = "test_value"


class MockAgent(BaseAgent):
    """Mock implementation of BaseAgent for testing."""

    agent_type = AgentType.PROJECT
    deps_type = MockDeps

    def _get_system_prompt(self) -> str:
        return "Test system prompt"

    def _get_tools(self):
        return []

    async def _get_context_message_content(self, deps: MockDeps) -> str:
        return "Test context"


class TestBaseAgent:
    """Test BaseAgent abstract class functionality."""

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def mock_agent_instance(self, mock_llm_service, mock_context_service):
        """Create mock agent instance with mocked dependencies."""
        return MockAgent(mock_context_service, mock_llm_service)

    @pytest.mark.asyncio
    async def test_agent_initialization_and_context(self, mock_agent_instance):
        """Test agent initializes correctly and provides context."""
        # Test initialization
        assert mock_agent_instance.agent_type == AgentType.PROJECT
        assert mock_agent_instance.deps_type == MockDeps

        # Test context method
        deps = MockDeps()
        content = await mock_agent_instance._get_context_message_content(deps)
        assert content == "Test context"

    def test_get_preferred_model(self, mock_agent_instance, mock_llm_service):
        """Test _get_preferred_model returns model from LLM service."""
        # Reset the mock call count since it was called during initialization
        mock_llm_service.get_preferred_model_for_agent.reset_mock()
        # The mock_llm_service fixture already returns a proper LanguageModel instance
        model_name = mock_agent_instance._get_preferred_model()
        # The method should return the pydanticai_id property of the LanguageModel
        assert model_name == "openai:gpt-4"  # This matches the mock fixture
        mock_llm_service.get_preferred_model_for_agent.assert_called_once_with(AgentType.PROJECT)

    def test_create_agent(self, mock_agent_instance):
        """Test _create_agent creates PydanticAI Agent instance."""
        agent = mock_agent_instance._create_agent()

        assert isinstance(agent, Agent)
        # Verify agent has correct configuration
        assert agent.deps_type == MockDeps

    @pytest.mark.asyncio
    async def test_run_with_string_message(self, mock_agent_instance):
        """Test run method with string message."""
        # Mock the internal agent and result
        mock_result = Mock()
        mock_result.output = "Test response"
        mock_agent_instance.agent.run = AsyncMock(return_value=mock_result)

        # Mock deps
        deps = MockDeps()
        message_history: list[ModelMessage] = []

        result = await mock_agent_instance.run(
            prompt_or_approvals="Test message",
            message_history=message_history,
            deps=deps,
        )

        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()

        # Check that deps and message history were passed
        call_args = mock_agent_instance.agent.run.call_args
        assert call_args.kwargs["deps"] == deps

    @pytest.mark.asyncio
    async def test_run_with_approval_results(self, mock_agent_instance):
        """Test run method with approval results (deferred tool continuation)."""
        # Mock approval results
        mock_approvals = Mock(spec=DeferredToolApprovalResult)

        # Mock the internal agent and result
        mock_result = Mock()
        mock_result.output = "Continued response"
        mock_agent_instance.agent.run = AsyncMock(return_value=mock_result)

        # Mock deps
        deps = MockDeps()
        message_history: list[ModelMessage] = []

        result = await mock_agent_instance.run(
            prompt_or_approvals=mock_approvals,
            message_history=message_history,
            deps=deps,
        )

        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_message_history(self, mock_agent_instance):
        """Test run method includes message history in agent context."""
        # Mock message history
        mock_messages: list[ModelMessage] = [
            Mock(spec=ModelMessage),
            Mock(spec=ModelMessage),
        ]

        # Mock the internal agent and result
        mock_result = Mock()
        mock_result.output = "Response with history"
        mock_agent_instance.agent.run = AsyncMock(return_value=mock_result)

        # Mock deps
        deps = MockDeps()

        result = await mock_agent_instance.run(
            prompt_or_approvals="Test message", message_history=mock_messages, deps=deps
        )

        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()

        # Verify message history was included (should be appended after initial context)
        call_args = mock_agent_instance.agent.run.call_args
        message_history_arg = call_args.kwargs.get("message_history", [])
        # Should have initial context messages + our mock messages
        assert len(message_history_arg) >= len(mock_messages)

    def test_agent_properties_and_abstract_methods(self, mock_agent_instance):
        """Test that agent has required properties and implements abstract methods."""
        # Test properties
        assert mock_agent_instance.agent_type == AgentType.PROJECT
        assert mock_agent_instance.deps_type == MockDeps

        # Test abstract method implementations return correct types
        prompt = mock_agent_instance._get_system_prompt()
        assert isinstance(prompt, str) and prompt

        tools = mock_agent_instance._get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_build_system_and_context_messages(self, mock_agent_instance):
        """Test building system and context messages."""
        deps = MockDeps()

        result = await mock_agent_instance.build_system_and_context_messages(deps)

        # Should return a ModelRequest with system and user parts
        assert hasattr(result, "parts")
        assert len(result.parts) >= 2  # At least system prompt and context message


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing abstract class requirements."""

    agent_type = AgentType.TASK_SPECIFICATION
    deps_type = BaseDeps

    def _get_system_prompt(self) -> str:
        return "Concrete system prompt"

    def _get_tools(self):
        return []

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        return "Concrete context"


class TestBaseAgentAbstract:
    """Test that BaseAgent properly enforces abstract method implementation."""

    @pytest.fixture
    def mock_context_service_for_abstract(self):
        """Mock context assembly service for abstract tests."""
        return Mock()

    def test_concrete_implementation_works(self, mock_llm_service, mock_context_service_for_abstract):
        """Test that concrete implementation can be instantiated."""
        agent = ConcreteAgent(mock_context_service_for_abstract, mock_llm_service)
        assert agent.agent_type == AgentType.TASK_SPECIFICATION
        assert agent.deps_type == BaseDeps

    def test_abstract_enforcement(self):
        """Test that BaseAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # This should fail because BaseAgent has abstract methods
            BaseAgent()  # type: ignore

    def test_incomplete_implementation_fails(self):
        """Test that incomplete implementations fail."""

        class IncompleteAgent(BaseAgent):
            agent_type = AgentType.PROJECT
            deps_type = BaseDeps

            # Missing _get_system_prompt, _get_tools, _get_context_message_content

        with pytest.raises(TypeError):
            IncompleteAgent()  # type: ignore
