"""Tests for InternalAgent with Role-based architecture."""

from unittest.mock import Mock, patch

import pytest
from pydantic_ai import Tool
from pydantic_ai.usage import RunUsage

from devboard.agents.base_agent import SHARED_PROMPT_SUFFIX
from devboard.agents.engines.internal import InternalAgent
from devboard.agents.events import ContextUsage
from devboard.agents.language_models import LLMProvider, ModelType
from devboard.agents.roles.base import AgentRole
from devboard.db.models.language_model import LanguageModelDB


class MockAgentRole(AgentRole):
    """Mock role for testing."""

    def get_system_prompt(self) -> str:
        return "Test system prompt for mock role"

    def get_tools(self) -> list[Tool]:
        return []

    async def get_context_content(self) -> str:
        return "Test context content"


class TestInternalAgent:
    """Test InternalAgent with Role-based architecture."""

    @pytest.fixture
    def mock_role(self):
        """Create mock role."""
        return MockAgentRole()

    @pytest.fixture
    def mock_model(self):
        """Create a mock language model."""
        return LanguageModelDB(
            provider=LLMProvider.OPENAI,
            name="gpt-4",
            model_type=ModelType.STANDARD,
        )

    @pytest.fixture
    def agent(self, mock_role, mock_model):
        """Create InternalAgent instance with mock role."""
        return InternalAgent(
            role=mock_role,
            model=mock_model,
        )

    def test_agent_initialization(self, agent, mock_role, mock_model):
        """Test agent initializes correctly with role and model."""
        assert agent.role == mock_role
        assert agent.model == mock_model

    def test_agent_system_prompt_excludes_context(self, agent, mock_role):
        """Test that system prompt contains role prompt but not context content."""
        # System prompt should contain role prompt and shared suffix
        system_prompt = agent.get_full_system_prompt()
        assert mock_role.get_system_prompt() in system_prompt
        assert SHARED_PROMPT_SUFFIX in system_prompt
        # Context content is no longer in the system prompt
        assert "CURRENT STATE AND CONTEXT" not in system_prompt

    def test_agent_creates_pydantic_agent(self, agent):
        """Test that agent can create PydanticAI agent."""
        with patch("devboard.agents.engines.internal.agent.Agent") as mock_agent_cls:
            agent._create_agent()
            mock_agent_cls.assert_called_once()
            call_kwargs = mock_agent_cls.call_args
            assert call_kwargs[0][0] == "openai:gpt-4"


class TestInternalAgentGetContextUsage:
    """Tests for InternalAgent.get_context_usage()."""

    @pytest.fixture
    def agent(self):
        role = MockAgentRole()
        model = LanguageModelDB(provider=LLMProvider.OPENAI, name="gpt-4", model_type=ModelType.STANDARD)
        return InternalAgent(role=role, model=model)

    def test_returns_none_when_no_run_result(self, agent):
        assert agent.last_run_result is None
        assert agent.get_context_usage() is None

    def test_returns_none_when_usage_empty(self, agent):
        mock_result = Mock()
        mock_result.usage.return_value = RunUsage()
        agent.last_run_result = mock_result

        assert agent.get_context_usage() is None

    def test_extracts_usage_fields(self, agent):
        mock_result = Mock()
        mock_result.usage.return_value = RunUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=800,
            cache_write_tokens=200,
        )
        agent.last_run_result = mock_result

        usage = agent.get_context_usage()

        assert isinstance(usage, ContextUsage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 800
        assert usage.cache_write_tokens == 200
        assert usage.cost_usd is None

    def test_returns_none_for_zero_usage(self, agent):
        mock_result = Mock()
        mock_result.usage.return_value = RunUsage(input_tokens=0, output_tokens=0)
        agent.last_run_result = mock_result

        assert agent.get_context_usage() is None
