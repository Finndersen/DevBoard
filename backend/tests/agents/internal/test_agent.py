"""Tests for InternalAgent with Role-based architecture."""

import pytest
from pydantic_ai import Agent, Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.engines.internal import InternalAgent
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.agents.roles.base import AgentRole


class MockAgentRole(AgentRole):
    """Mock role for testing."""

    def get_system_prompt(self) -> str:
        return "Test system prompt for mock role"

    def get_tools(self) -> list[Tool | ToolFuncEither]:
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
        return LanguageModel(
            provider=LLMProvider.OPENAI,
            name="gpt-4",
            type=ModelType.STANDARD,
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

    @pytest.mark.asyncio
    async def test_build_system_and_context_messages(self, agent, mock_role):
        """Test agent builds system and context messages from role."""
        request = await agent.build_system_and_context_messages()

        # Should have system prompt and context message
        assert len(request.parts) == 2

        # First part should be system prompt
        assert request.parts[0].content == mock_role.get_system_prompt()

        # Second part should be context
        context_content = await mock_role.get_context_content()
        assert "CURRENT STATE AND CONTEXT:" in request.parts[1].content
        assert context_content in request.parts[1].content

    def test_agent_creates_pydantic_agent(self, agent):
        """Test that agent can create PydanticAI agent."""
        pydantic_agent = agent._create_agent()

        # Should be a PydanticAI Agent instance
        assert isinstance(pydantic_agent, Agent)
