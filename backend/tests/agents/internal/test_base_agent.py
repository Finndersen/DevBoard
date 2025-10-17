"""Tests for BaseAgent abstract class."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.tools import DeferredToolApprovalResult

from devboard.agents.engines.internal import BaseDeps, InternalAgent
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.agents.roles.types import AgentRole


class MockDeps(BaseDeps):
    """Mock dependencies for testing."""

    test_field: str = "test_value"


class MockInternalAgent(InternalAgent):
    """Mock implementation of BaseAgent for testing."""

    agent_role = AgentRole.PROJECT
    deps_type = MockDeps

    def _get_system_prompt(self) -> str:
        return "Test system prompt"

    def _get_tools(self):
        return []

    async def _get_context_message_content(self, deps: MockDeps) -> str:
        return "Test context"


class MockPydanticAgent:
    def __init__(self, run_result):
        self.run = AsyncMock(return_value=run_result)


class TestBaseAgent:
    """Test BaseAgent abstract class functionality."""

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def mock_model(self):
        """Create a mock language model."""
        return LanguageModel(
            provider=LLMProvider.OPENAI,
            name="gpt-4",
            type=ModelType.REASONING,
        )

    @pytest.fixture
    def mock_agent_instance(self, mock_context_service, mock_model):
        """Create mock agent instance with mocked dependencies."""
        return MockInternalAgent(mock_context_service, mock_model)

    @pytest.mark.asyncio
    async def test_agent_initialization_and_context(self, mock_agent_instance):
        """Test agent initializes correctly and provides context."""
        # Test initialization
        assert mock_agent_instance.agent_role == AgentRole.PROJECT
        assert mock_agent_instance.deps_type == MockDeps

        # Test context method
        deps = MockDeps()
        content = await mock_agent_instance._get_context_message_content(deps)
        assert content == "Test context"

    def test_get_model(self, mock_agent_instance):
        """Test _get_model returns the configured model name."""
        model_id = mock_agent_instance._get_model()
        # The method should return the model_name passed during initialization
        assert model_id == "openai:gpt-4"

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
        mock_pydantic_agent = MockPydanticAgent(run_result=mock_result)
        mock_agent_instance._create_agent = Mock(return_value=mock_pydantic_agent)

        # Mock deps
        deps = MockDeps()
        message_history: list[ModelMessage] = []

        result = await mock_agent_instance.run(
            prompt_or_approvals="Test message",
            conversation_history=message_history,
            deps=deps,
        )

        assert result == mock_result
        mock_pydantic_agent.run.assert_called_once()

        # Check that deps and message history were passed
        call_args = mock_pydantic_agent.run.call_args
        assert call_args.kwargs["deps"] == deps

    @pytest.mark.asyncio
    async def test_run_with_approval_results(self, mock_agent_instance):
        """Test run method with approval results (deferred tool continuation)."""
        # Mock approval results
        mock_approvals = Mock(spec=DeferredToolApprovalResult)

        # Mock the internal agent and result
        mock_result = Mock()
        mock_result.output = "Continued response"
        mock_pydantic_agent = MockPydanticAgent(run_result=mock_result)
        mock_agent_instance._create_agent = Mock(return_value=mock_pydantic_agent)

        # Mock deps
        deps = MockDeps()
        message_history: list[ModelMessage] = []

        result = await mock_agent_instance.run(
            prompt_or_approvals=mock_approvals,
            conversation_history=message_history,
            deps=deps,
        )

        assert result == mock_result
        mock_pydantic_agent.run.assert_called_once()

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
        mock_pydantic_agent = MockPydanticAgent(run_result=mock_result)
        mock_agent_instance._create_agent = Mock(return_value=mock_pydantic_agent)

        # Mock deps
        deps = MockDeps()

        result = await mock_agent_instance.run(
            prompt_or_approvals="Test message",
            conversation_history=mock_messages,
            deps=deps,
        )

        assert result == mock_result
        mock_pydantic_agent.run.assert_called_once()

        # Verify message history was included (should be appended after initial context)
        call_args = mock_pydantic_agent.run.call_args
        message_history_arg = call_args.kwargs.get("message_history", [])
        # Should have initial context messages + our mock messages
        assert len(message_history_arg) >= len(mock_messages)

    def test_agent_properties_and_abstract_methods(self, mock_agent_instance):
        """Test that agent has required properties and implements abstract methods."""
        # Test properties
        assert mock_agent_instance.agent_role == AgentRole.PROJECT
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


class ConcreteAgent(InternalAgent):
    """Concrete implementation for testing abstract class requirements."""

    agent_role = AgentRole.TASK_SPECIFICATION
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

    @pytest.fixture
    def mock_model_for_abstract(self):
        """Create a mock language model for abstract tests."""
        return LanguageModel(
            provider=LLMProvider.OPENAI,
            name="gpt-4",
            type=ModelType.REASONING,
        )

    def test_concrete_implementation_works(self, mock_context_service_for_abstract, mock_model_for_abstract):
        """Test that concrete implementation can be instantiated."""
        agent = ConcreteAgent(mock_context_service_for_abstract, mock_model_for_abstract)
        assert agent.agent_role == AgentRole.TASK_SPECIFICATION
        assert agent.deps_type == BaseDeps

    def test_abstract_enforcement(self):
        """Test that BaseAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # This should fail because BaseAgent has abstract methods
            InternalAgent()  # type: ignore

    def test_incomplete_implementation_fails(self):
        """Test that incomplete implementations fail."""

        class IncompleteAgent(InternalAgent):
            agent_role = AgentRole.PROJECT
            deps_type = BaseDeps

            # Missing _get_system_prompt, _get_tools, _get_context_message_content

        with pytest.raises(TypeError):
            IncompleteAgent()  # type: ignore
