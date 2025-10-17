"""Tests for AgentConversationService."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from devboard.agents.engines.internal import BaseDeps, InternalAgent, PydanticAIConversationService
from devboard.agents.roles.types import AgentRole
from devboard.api.schemas.agent_conversation import (
    MessageRole,
    PromptResponseType,
    ToolApprovalDecision,
)
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import (
    DeferredToolRequests,
    ToolApproved,
    ToolDenied,
)
from sqlalchemy.orm import Session


class MockAgent(InternalAgent):
    """Mock agent for testing."""

    agent_role = AgentRole.PROJECT

    def __init__(self, context_service, agent_config_service):
        self.context_service = context_service
        self.llm_service = agent_config_service

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        return "Test context"

    def _get_role_prompt(self) -> str:
        return "Test system prompt"

    def _get_tools(self) -> list:
        return []


class TestAgentConversationService:
    """Test AgentConversationService functionality."""

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service."""
        return Mock()

    @pytest.fixture
    def mock_agent(self, mock_llm_service, mock_context_service):
        """Create mock agent."""
        return MockAgent(mock_context_service, mock_llm_service)

    @pytest.fixture
    def conversation(self, db_session: Session) -> Conversation:
        """Create a test conversation."""
        conversation_repo = ConversationRepository(db_session)
        from devboard.agents.engines.agent_engines import AgentEngine
        from devboard.db.models import ParentEntityType

        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=1,
            agent_role=AgentRole.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="anthropic:claude-sonnet-4.5",
            is_active=True,
        )
        db_session.commit()
        return conversation

    @pytest.fixture
    def conversation_repo(self, db_session: Session) -> ConversationRepository:
        """Create conversation repository."""
        return ConversationRepository(db_session)

    @pytest.fixture
    def service(self, mock_agent, conversation_repo, conversation):
        """Create PydanticAIConversationService instance."""
        return PydanticAIConversationService(
            conversation=conversation, agent=mock_agent, conversation_repository=conversation_repo
        )

    @pytest.mark.asyncio
    async def test_send_message_text_response(self, service, mock_agent):
        """Test sending a message that returns a text response."""
        # Mock agent run to return a text response
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Test response"
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Test message")]),
            ModelResponse(parts=[TextPart(content="Test response")]),
        ]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            response = await service.send_message(message="Test message")

        assert response.type == PromptResponseType.MESSAGE
        assert response.message is not None
        assert response.message.text_content == "Test response"
        assert response.message.role == MessageRole.AGENT
        assert response.tool_requests is None

    @pytest.mark.asyncio
    async def test_send_message_tool_request(self, service, mock_agent):
        """Test sending a message that returns tool requests."""
        # Create mock deferred tool requests
        mock_tool_request = MagicMock()
        mock_tool_request.tool_call_id = "tool_123"
        mock_tool_request.tool_name = "edit_document"
        mock_tool_request.args = {"edits": [{"find": "old", "replace": "new"}]}

        mock_deferred = DeferredToolRequests(approvals=[mock_tool_request])

        # Mock agent run to return deferred tool requests
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_deferred
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Edit this")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="edit_document",
                        tool_call_id="tool_123",
                        args={"edits": [{"find": "old", "replace": "new"}]},
                    )
                ]
            ),
        ]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            response = await service.send_message(message="Edit this")

        assert response.type == PromptResponseType.TOOL_REQUEST
        assert response.tool_requests is not None
        assert len(response.tool_requests) == 1
        assert response.tool_requests[0].tool_call_id == "tool_123"
        assert response.tool_requests[0].tool_name == "edit_document"
        assert response.message is None

    @pytest.mark.asyncio
    async def test_process_tool_approvals(self, service, mock_agent, conversation_repo, conversation, db_session):
        """Test processing tool approval decisions."""
        # Setup: Add existing messages including a tool call message
        user_pydantic_msg = ModelRequest(parts=[UserPromptPart(content="Edit this document")])
        tool_call_pydantic_msg = ModelResponse(
            parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={})]
        )

        conversation_repo.create_message(conversation.id, user_pydantic_msg)
        conversation_repo.create_message(conversation.id, tool_call_pydantic_msg)
        db_session.commit()

        # Set up approvals
        approvals = {
            "tool_123": ToolApprovalDecision(approved=True),
            "tool_456": ToolApprovalDecision(approved=False, feedback="Not good"),
        }

        # Mock agent run with approval results
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Continued after approval"
        mock_result.new_messages.return_value = [ModelResponse(parts=[TextPart(content="Continued after approval")])]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            response = await service.process_tool_approvals(approvals=approvals)

        # Verify the agent was called with proper approval results
        mock_run.assert_called_once()
        args = mock_run.call_args[1]
        approval_result = args["prompt_or_approvals"]

        # Check the approval result structure
        assert hasattr(approval_result, "approvals")
        assert "tool_123" in approval_result.approvals
        assert "tool_456" in approval_result.approvals

        # Check response
        assert response.type == PromptResponseType.MESSAGE

    def test_convert_messages_to_pydantic(self, service, conversation_repo, conversation, db_session):
        """Test converting database messages to PydanticAI format."""
        # Create messages via repository
        user_msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        agent_msg = ModelResponse(parts=[TextPart(content="Hi there")])

        conversation_repo.create_message(conversation.id, user_msg)
        conversation_repo.create_message(conversation.id, agent_msg)
        db_session.commit()

        db_messages = conversation_repo.get_messages(conversation.id)
        messages = conversation_repo.convert_messages_to_pydantic(db_messages)

        assert len(messages) == 2

    def test_store_new_messages(self, service, conversation_repo, conversation, db_session):
        """Test storing new messages from agent result."""
        # Create PydanticAI messages
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Test")]),
            ModelResponse(parts=[TextPart(content="Response")]),
        ]

        saved = service._store_new_messages(messages)
        db_session.commit()

        assert len(saved) == 2
        # Verify messages are in database
        db_messages = conversation_repo.get_messages(conversation.id)
        assert len(db_messages) == 2

    def test_create_deferred_results_approved(self, service):
        """Test creating deferred results for approved tools."""
        approvals = {"tool_123": ToolApprovalDecision(approved=True)}

        result = service._create_deferred_results(approvals)

        assert hasattr(result, "approvals")
        assert "tool_123" in result.approvals
        assert isinstance(result.approvals["tool_123"], ToolApproved)

    def test_create_deferred_results_denied(self, service):
        """Test creating deferred results for denied tools."""
        approvals = {"tool_456": ToolApprovalDecision(approved=False, feedback="Not allowed")}

        result = service._create_deferred_results(approvals)

        assert hasattr(result, "approvals")
        assert "tool_456" in result.approvals
        assert isinstance(result.approvals["tool_456"], ToolDenied)
        assert result.approvals["tool_456"].message == "Tool call DENIED with feedback: Not allowed"

    def test_create_deferred_results_mixed(self, service):
        """Test creating deferred results with mixed approvals."""
        approvals = {
            "tool_1": ToolApprovalDecision(approved=True),
            "tool_2": ToolApprovalDecision(approved=False, feedback="Nope"),
            "tool_3": ToolApprovalDecision(approved=True),
        }

        result = service._create_deferred_results(approvals)

        assert len(result.approvals) == 3
        assert isinstance(result.approvals["tool_1"], ToolApproved)
        assert isinstance(result.approvals["tool_2"], ToolDenied)
        assert isinstance(result.approvals["tool_3"], ToolApproved)

    @pytest.mark.asyncio
    async def test_send_message_when_expecting_tool_approval(
        self, service, mock_agent, conversation_repo, conversation, db_session
    ):
        """Test sending a text message when the conversation is expecting tool approval.

        This should trigger cleanup of the pending tool call message.
        """
        # Setup: Add a previous tool call message to simulate pending tool approval
        user_msg = ModelRequest(parts=[UserPromptPart(content="Do something")])
        tool_call_msg = ModelResponse(parts=[ToolCallPart(tool_name="some_tool", tool_call_id="tool_1", args={})])

        conversation_repo.create_message(conversation.id, user_msg)
        conversation_repo.create_message(conversation.id, tool_call_msg)
        db_session.commit()

        # Now send a new message (should trigger cleanup)
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "I've processed your new request"
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="New message")]),
            ModelResponse(parts=[TextPart(content="I've processed your new request")]),
        ]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            # Mock logfire.warning to verify it's called
            with patch("devboard.agents.engines.internal.agent_conversation.logfire.warning") as mock_warning:
                response = await service.send_message(message="New message")

        # Verify the cleanup warning was logged
        mock_warning.assert_called_once()
        assert "Deleted" in str(mock_warning.call_args) and "messages due to missing tool approvals" in str(
            mock_warning.call_args
        )

        # Verify response is correct
        assert response.type == PromptResponseType.MESSAGE
        assert response.message is not None

    @pytest.mark.asyncio
    async def test_process_tool_approvals_with_no_existing_messages(self, service, mock_agent):
        """Test processing tool approvals when there are no existing messages."""
        approvals = {"tool_123": ToolApprovalDecision(approved=True)}

        with pytest.raises(ValueError, match="No existing messages found for processing tool approvals"):
            await service.process_tool_approvals(approvals=approvals)

    @pytest.mark.asyncio
    async def test_process_tool_approvals_with_no_tool_call_message(
        self, service, mock_agent, conversation_repo, conversation, db_session
    ):
        """Test processing tool approvals when the last message is not a tool call."""
        # Setup: Add a regular text message (not a tool call)
        user_msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        conversation_repo.create_message(conversation.id, user_msg)
        db_session.commit()

        approvals = {"tool_123": ToolApprovalDecision(approved=True)}

        with pytest.raises(
            ValueError,
            match="Last message is not a tool call; cannot process approvals",
        ):
            await service.process_tool_approvals(approvals=approvals)
