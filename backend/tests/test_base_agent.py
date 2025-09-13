"""Tests for BaseAgent abstract class."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
    def mock_llm_service(self):
        """Mock LLM service to avoid database dependencies."""
        with patch("devboard.agents.base_agent.llm_service") as mock_service:
            mock_service.get_preferred_model_for_agent.return_value = "test"
            yield mock_service

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        with patch("devboard.agents.base_agent.context_assembly_service") as mock_service:
            yield mock_service

    @pytest.fixture
    def mock_agent_instance(self, mock_llm_service, mock_context_service):
        """Create mock agent instance with mocked dependencies."""
        return MockAgent()

    def test_agent_initialization(self, mock_agent_instance):
        """Test agent initializes with correct properties."""
        assert mock_agent_instance.agent_type == AgentType.PROJECT
        assert mock_agent_instance.deps_type == MockDeps

    def test_get_system_prompt(self, mock_agent_instance):
        """Test system prompt is implemented."""
        prompt = mock_agent_instance._get_system_prompt()
        assert prompt == "Test system prompt"

    def test_get_tools(self, mock_agent_instance):
        """Test tools method returns list."""
        tools = mock_agent_instance._get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_get_context_message_content(self, mock_agent_instance):
        """Test context message content method."""
        deps = MockDeps()
        content = await mock_agent_instance._get_context_message_content(deps)
        assert content == "Test context"

    def test_get_preferred_model(self, mock_agent_instance, mock_llm_service):
        """Test _get_preferred_model returns model from LLM service."""
        # Reset the mock call count since it was called during initialization
        mock_llm_service.get_preferred_model_for_agent.reset_mock()
        mock_llm_service.get_preferred_model_for_agent.return_value = "test"
        
        model_name = mock_agent_instance._get_preferred_model()
        assert model_name == "test"
        mock_llm_service.get_preferred_model_for_agent.assert_called_once_with(
            AgentType.PROJECT
        )

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
            deps=deps
        )
        
        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()
        
        # Check that deps and message history were passed
        call_args = mock_agent_instance.agent.run.call_args
        assert call_args.kwargs['deps'] == deps

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
            deps=deps
        )
        
        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()

    @pytest.mark.asyncio 
    async def test_run_with_message_history(self, mock_agent_instance):
        """Test run method includes message history in agent context."""
        # Mock message history
        mock_messages: list[ModelMessage] = [Mock(spec=ModelMessage), Mock(spec=ModelMessage)]
        
        # Mock the internal agent and result
        mock_result = Mock()
        mock_result.output = "Response with history"
        mock_agent_instance.agent.run = AsyncMock(return_value=mock_result)
        
        # Mock deps
        deps = MockDeps()
        
        result = await mock_agent_instance.run(
            prompt_or_approvals="Test message",
            message_history=mock_messages,
            deps=deps
        )
        
        assert result == mock_result
        mock_agent_instance.agent.run.assert_called_once()
        
        # Verify message history was included (should be appended after initial context)
        call_args = mock_agent_instance.agent.run.call_args
        message_history_arg = call_args.kwargs.get('message_history', [])
        # Should have initial context messages + our mock messages
        assert len(message_history_arg) >= len(mock_messages)

    def test_agent_type_property(self, mock_agent_instance):
        """Test agent_type property access."""
        assert hasattr(mock_agent_instance, 'agent_type')
        assert mock_agent_instance.agent_type == AgentType.PROJECT

    def test_deps_type_property(self, mock_agent_instance):
        """Test deps_type property access."""
        assert hasattr(mock_agent_instance, 'deps_type')
        assert mock_agent_instance.deps_type == MockDeps

    def test_abstract_methods_implemented(self, mock_agent_instance):
        """Test that abstract methods are properly implemented."""
        # All these should not raise NotImplementedError
        prompt = mock_agent_instance._get_system_prompt()
        assert isinstance(prompt, str)
        
        tools = mock_agent_instance._get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_abstract_context_method_implemented(self, mock_agent_instance):
        """Test that abstract context method is implemented."""
        deps = MockDeps()
        content = await mock_agent_instance._get_context_message_content(deps)
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_build_system_and_context_messages(self, mock_agent_instance):
        """Test building system and context messages."""
        deps = MockDeps()
        
        result = await mock_agent_instance.build_system_and_context_messages(deps)
        
        # Should return a ModelRequest with system and user parts
        assert hasattr(result, 'parts')
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
    def mock_llm_service_for_abstract(self):
        """Mock LLM service for abstract tests."""
        with patch("devboard.agents.base_agent.llm_service") as mock_service:
            mock_service.get_preferred_model_for_agent.return_value = "test"
            yield mock_service

    @pytest.fixture
    def mock_context_service_for_abstract(self):
        """Mock context assembly service for abstract tests."""
        with patch("devboard.agents.base_agent.context_assembly_service") as mock_service:
            yield mock_service
    
    def test_concrete_implementation_works(self, mock_llm_service_for_abstract, mock_context_service_for_abstract):
        """Test that concrete implementation can be instantiated."""
        agent = ConcreteAgent()
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