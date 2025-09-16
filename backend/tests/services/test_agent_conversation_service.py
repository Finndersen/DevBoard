"""Tests for AgentConversationService."""

import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.types import AgentType
from devboard.api.schemas.agent_conversation import (
    MessageRole,
    PromptResponseType,
    ToolApprovalDecision,
)
from devboard.db.models.messages import BaseConversationMessage, MessageType
from devboard.db.repositories.conversation_message import (
    BaseConversationMessageRepository,
)
from devboard.services.agent_conversation import AgentConversationService


class MockConversationMessage(BaseConversationMessage):
    """Mock concrete conversation message for testing."""

    __tablename__ = "mock_conversation_messages"

    parent_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))


class MockMessageRepository(BaseConversationMessageRepository):
    """Mock implementation of MessageRepository for testing."""

    MESSAGE_MODEL = MockConversationMessage

    def __init__(self):
        self.messages = []

    def get_all_for_entity(self, entity_id: int) -> list[MockConversationMessage]:
        return [msg for msg in self.messages if msg.parent_id == entity_id]

    def create(self, message: MockConversationMessage) -> MockConversationMessage:
        message.id = len(self.messages) + 1
        message.timestamp = datetime.datetime.now(datetime.UTC)
        self.messages.append(message)
        return message

    def delete_tool_approval_messages(self, entity_id: int) -> int:
        """Delete tool approval messages and return count of deleted messages."""
        # Filter out the last message if it's a tool call for this entity
        entity_messages = [msg for msg in self.messages if msg.parent_id == entity_id]
        if entity_messages and entity_messages[-1].message_type == MessageType.TOOL_CALL:
            # Remove the last tool call message
            self.messages = [
                msg
                for msg in self.messages
                if not (msg.parent_id == entity_id and msg.message_type == MessageType.TOOL_CALL)
            ]
            return 1
        return 0


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    agent_type = AgentType.PROJECT
    deps_type = BaseDeps

    def _get_system_prompt(self) -> str:
        return "Test system prompt"

    def _get_tools(self):
        return []

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        return "Test context"


class TestAgentConversationService:
    """Test AgentConversationService functionality."""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service to avoid database dependencies."""
        mock_service = Mock()
        mock_service.get_preferred_model_for_agent.return_value = "openai/gpt-4"
        return mock_service

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def mock_agent(self, mock_llm_service, mock_context_service):
        """Create mock agent."""
        return MockAgent(mock_context_service, mock_llm_service)

    @pytest.fixture
    def mock_message_repo(self):
        """Create mock message repository."""
        return MockMessageRepository()

    @pytest.fixture
    def service(self, mock_agent, mock_message_repo):
        """Create AgentConversationService instance."""
        return AgentConversationService(agent=mock_agent, message_repository=mock_message_repo)

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

            response = await service.send_message(message="Test message", entity_id=1)

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

            response = await service.send_message(message="Edit this", entity_id=1)

        assert response.type == PromptResponseType.TOOL_REQUEST
        assert response.tool_requests is not None
        assert len(response.tool_requests) == 1
        assert response.tool_requests[0].tool_call_id == "tool_123"
        assert response.tool_requests[0].tool_name == "edit_document"
        assert response.message is None

    @pytest.mark.asyncio
    async def test_process_tool_approvals(self, service, mock_agent, mock_message_repo):
        """Test processing tool approval decisions."""
        # Setup: Add existing messages including a tool call message
        user_message = MockConversationMessage()
        user_message.parent_id = 1
        user_message.message_type = MessageType.USER_PROMPT
        user_message.pydantic_content = {
            "kind": "request",
            "parts": [{"part_kind": "user-prompt", "content": "Edit this document"}],
        }

        tool_call_message = MockConversationMessage()
        tool_call_message.parent_id = 1
        tool_call_message.message_type = MessageType.TOOL_CALL
        tool_call_message.pydantic_content = {
            "kind": "response",
            "parts": [{"part_kind": "tool-call", "tool_name": "edit_document", "tool_call_id": "tool_123"}],
        }

        mock_message_repo.create(user_message)
        mock_message_repo.create(tool_call_message)

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

            response = await service.process_tool_approvals(approvals=approvals, entity_id=1)

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
        assert response.message.text_content == "Continued after approval"

    def test_convert_messages_to_pydantic(self, service, mock_message_repo):
        """Test converting database messages to PydanticAI format."""
        # Create mock messages with proper PydanticAI message structure
        msg1 = MockConversationMessage()
        msg1.parent_id = 1
        msg1.message_type = MessageType.USER_PROMPT
        msg1.pydantic_content = {
            "kind": "request",
            "parts": [{"part_kind": "user-prompt", "content": "Hello"}],
        }

        msg2 = MockConversationMessage()
        msg2.parent_id = 1
        msg2.message_type = MessageType.TEXT_RESPONSE
        msg2.pydantic_content = {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": "Hi there"}],
        }

        messages = service.convert_messages_to_pydantic([msg1, msg2])

        assert len(messages) == 2
        # Messages should be deserialized PydanticAI messages

    def test_store_new_messages(self, service, mock_message_repo):
        """Test storing new messages from agent result."""
        # Create PydanticAI messages
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Test")]),
            ModelResponse(parts=[TextPart(content="Response")]),
        ]

        # Mock the MESSAGE_MODEL
        mock_message_repo.MESSAGE_MODEL = Mock()
        mock_message_repo.MESSAGE_MODEL.from_pydantic_message = Mock(
            side_effect=lambda entity_id, msg: MockConversationMessage()
        )

        saved = service.store_new_messages(messages, entity_id=1)

        assert len(saved) == 2
        assert len(mock_message_repo.messages) == 2

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
        assert result.approvals["tool_456"].message == "Not allowed"

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
    async def test_handle_message_or_approval_with_message(self, service, mock_agent):
        """Test handling a regular message."""
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Response text"
        mock_result.new_messages.return_value = [ModelResponse(parts=[TextPart(content="Response text")])]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            response = await service._handle_message_or_approval(entity_id=1, message_or_approvals="User message")

        assert response.type == PromptResponseType.MESSAGE
        assert response.message.text_content == "Response text"

    @pytest.mark.asyncio
    async def test_handle_message_or_approval_with_approval(self, service, mock_agent):
        """Test handling tool approval results."""
        # Create approval result
        approval_result = MagicMock()
        approval_result.approvals = {"tool_1": ToolApproved()}

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Continued"
        mock_result.new_messages.return_value = [ModelResponse(parts=[TextPart(content="Continued")])]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            response = await service._handle_message_or_approval(entity_id=1, message_or_approvals=approval_result)

        assert response.type == PromptResponseType.MESSAGE
        assert response.message.text_content == "Continued"

    @pytest.mark.asyncio
    async def test_send_message_when_expecting_tool_approval(self, service, mock_agent, mock_message_repo):
        """Test sending a text message when the conversation is expecting DeferredToolResults.

        This should trigger cleanup of the pending tool call message.
        """
        # Setup: Add a previous tool call message to simulate pending tool approval
        tool_call_message = MockConversationMessage()
        tool_call_message.parent_id = 1
        tool_call_message.message_type = MessageType.TOOL_CALL
        tool_call_message.pydantic_content = {
            "kind": "response",
            "parts": [{"part_kind": "tool-call", "tool_name": "edit_document", "tool_call_id": "tool_123"}],
        }
        mock_message_repo.create(tool_call_message)

        # Mock agent run to return a text response
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "I've processed your new request"
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="New message")]),
            ModelResponse(parts=[TextPart(content="I've processed your new request")]),
        ]

        with patch.object(mock_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            # Mock logfire.warning to verify it's called
            with patch("devboard.services.agent_conversation.logfire.warning") as mock_warning:
                response = await service.send_message(message="New message", entity_id=1)

        # Verify the cleanup warning was logged
        mock_warning.assert_called_once()
        assert "Deleted 1 messages due to missing tool approvals" in str(mock_warning.call_args)

        # Verify response is correct
        assert response.type == PromptResponseType.MESSAGE
        assert response.message is not None
        assert response.message.text_content == "I've processed your new request"
        assert response.message.role == MessageRole.AGENT
        assert response.tool_requests is None

        # Verify the agent was called with cleaned message history
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs["prompt_or_approvals"] == "New message"

    @pytest.mark.asyncio
    async def test_process_tool_approvals_with_no_existing_messages(self, service, mock_agent):
        """Test processing tool approvals when there are no existing messages.

        This should raise a ValueError.
        """
        approvals = {"tool_123": ToolApprovalDecision(approved=True)}

        with pytest.raises(ValueError, match="No existing messages found for processing tool approvals"):
            await service.process_tool_approvals(approvals=approvals, entity_id=1)

    @pytest.mark.asyncio
    async def test_process_tool_approvals_with_no_tool_call_message(self, service, mock_agent, mock_message_repo):
        """Test processing tool approvals when the last message is not a tool call.

        This should raise a ValueError.
        """
        # Setup: Add a regular text message (not a tool call)
        text_message = MockConversationMessage()
        text_message.parent_id = 1
        text_message.message_type = MessageType.TEXT_RESPONSE
        text_message.pydantic_content = {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": "Regular response"}],
        }
        mock_message_repo.create(text_message)

        approvals = {"tool_123": ToolApprovalDecision(approved=True)}

        with pytest.raises(ValueError, match="Last message is not a tool call; cannot process approvals"):
            await service.process_tool_approvals(approvals=approvals, entity_id=1)

    @pytest.mark.asyncio
    async def test_handle_message_or_approval_validation_no_messages_for_tool_approvals(self, service):
        """Test that DeferredToolResults validation fails with no existing messages."""
        # Create a DeferredToolResults object
        tool_results = DeferredToolResults(approvals={"tool_1": ToolApproved()})

        with pytest.raises(ValueError, match="No existing messages found for processing tool approvals"):
            await service._handle_message_or_approval(entity_id=1, message_or_approvals=tool_results)

    @pytest.mark.asyncio
    async def test_handle_message_or_approval_validation_wrong_last_message_type(self, service, mock_message_repo):
        """Test that DeferredToolResults validation fails when last message is not a tool call."""
        # Setup: Add a regular text message
        text_message = MockConversationMessage()
        text_message.parent_id = 1
        text_message.message_type = MessageType.TEXT_RESPONSE
        text_message.pydantic_content = {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": "Regular response"}],
        }
        mock_message_repo.create(text_message)

        # Create a DeferredToolResults object
        tool_results = DeferredToolResults(approvals={"tool_1": ToolApproved()})

        with pytest.raises(ValueError, match="Last message is not a tool call; cannot process approvals"):
            await service._handle_message_or_approval(entity_id=1, message_or_approvals=tool_results)
