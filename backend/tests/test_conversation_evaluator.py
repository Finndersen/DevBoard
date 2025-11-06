"""Tests for conversation evaluator service."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.evaluation_models import (
    AgentSpecification,
    ConversationEvaluation,
    Evaluation,
    Improvement,
    PerformanceEvaluations,
    Priority,
    ToolSpecification,
)
from devboard.agents.events import MessageRole, TextMessage, ToolCall, ToolResult
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import Conversation, ConversationMessage, MessageType, ParentEntityType, Project, Task
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.services.conversation_evaluator_service import ConversationEvaluatorService


@pytest.fixture
def evaluation_repository(db_session):
    """Evaluation repository instance for testing."""
    from devboard.db.repositories import ConversationEvaluationRepository

    return ConversationEvaluationRepository(db_session)


@pytest.fixture
def evaluator_service(
    conversation_repository, project_repository, task_repository, document_repository, evaluation_repository
):
    """Create ConversationEvaluatorService instance for testing."""
    return ConversationEvaluatorService(
        conversation_repo=conversation_repository,
        project_repo=project_repository,
        task_repo=task_repository,
        document_repo=document_repository,
        evaluation_repo=evaluation_repository,
    )


@pytest.fixture
def sample_project(db_session, project_repository):
    """Create a sample project for testing."""
    project = Project(
        name="Test Project",
        description="A test project for evaluator",
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def sample_conversation(db_session, conversation_repository, sample_project):
    """Create a sample conversation for testing."""
    conversation = conversation_repository.create(
        parent_entity_type=ParentEntityType.PROJECT,
        parent_entity_id=sample_project.id,
        agent_role=AgentRoleType.PROJECT,
        engine=AgentEngine.INTERNAL,
        model_id="anthropic:claude-sonnet-4",
    )
    db_session.flush()
    return conversation


@pytest.fixture
def sample_messages(db_session, conversation_repository, sample_conversation):
    """Create sample conversation messages for testing."""
    # User message
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    user_msg = ModelRequest(parts=[UserPromptPart(content="What is this project about?")])
    msg1 = ConversationMessage.from_pydantic_message(sample_conversation.id, user_msg)
    db_session.add(msg1)

    # Agent response
    from pydantic_ai.messages import ModelResponse, TextPart

    agent_msg = ModelResponse(
        parts=[TextPart(content="This is a test project for evaluating conversation quality.")]
    )
    msg2 = ConversationMessage.from_pydantic_message(sample_conversation.id, agent_msg)
    db_session.add(msg2)

    db_session.flush()
    return [msg1, msg2]


class TestConversationEvaluatorService:
    """Tests for ConversationEvaluatorService."""

    def test_convert_messages_to_events(self, evaluator_service, sample_messages):
        """Test converting database messages to ConversationEvent objects."""
        events = evaluator_service._convert_messages_to_events(sample_messages)

        assert len(events) == 2
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].text_content == "What is this project about?"

        assert isinstance(events[1], TextMessage)
        assert events[1].role == MessageRole.AGENT
        assert "test project" in events[1].text_content

    def test_extract_tool_parameters(self, evaluator_service):
        """Test extracting parameters from a tool."""
        from pydantic_ai import Tool

        def sample_tool(query: str, limit: int = 10) -> str:
            return f"Results for {query}"

        tool = Tool(sample_tool, name="search", description="Search for items")

        params = evaluator_service._extract_tool_parameters(tool)
        assert "parameters" in params
        assert "query" in params["parameters"]
        assert "limit" in params["parameters"]

    @pytest.mark.asyncio
    async def test_format_agent_specification(
        self, evaluator_service, sample_conversation, project_repository, document_repository
    ):
        """Test formatting agent specification from conversation."""
        from devboard.agents.roles.project_qa import ProjectQARole

        project = project_repository.get_by_id(sample_conversation.parent_entity_id)
        role = ProjectQARole(project=project, document_repository=document_repository)

        agent_spec = await evaluator_service._format_agent_specification(sample_conversation, role)

        assert isinstance(agent_spec, AgentSpecification)
        assert agent_spec.role_type == AgentRoleType.PROJECT
        assert len(agent_spec.system_prompt) > 0
        assert isinstance(agent_spec.tools, list)
        assert len(agent_spec.context_summary) > 0

    @pytest.mark.asyncio
    async def test_evaluate_conversation_not_found(self, evaluator_service):
        """Test evaluating a non-existent conversation raises error."""
        with pytest.raises(ValueError, match="Conversation 999 not found"):
            await evaluator_service.evaluate_conversation(999)

    @pytest.mark.asyncio
    async def test_evaluate_conversation_no_messages(self, evaluator_service, sample_conversation):
        """Test evaluating a conversation with no messages raises error."""
        with pytest.raises(ValueError, match="has no messages"):
            await evaluator_service.evaluate_conversation(sample_conversation.id)

    @pytest.mark.asyncio
    async def test_evaluate_conversation_success(
        self, evaluator_service, sample_conversation, sample_messages, document_repository, project_repository
    ):
        """Test successful conversation evaluation."""
        # Mock the evaluation agent to return a structured result
        mock_evaluation = ConversationEvaluation(
            overall_rating=8.5,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(
                    score=9.0,
                    explanation="Clear and well-structured system prompt",
                    evidence=["message_1"],
                    improvements=[],
                ),
                tool_specification_quality=Evaluation(
                    score=8.5,
                    explanation="Tools are well-defined with clear descriptions",
                    evidence=["tool_spec_1"],
                    improvements=[
                        Improvement(
                            priority=Priority.MEDIUM,
                            title="Add more parameter validation",
                            description="Some tool parameters could benefit from additional validation",
                            suggested_changes="Add Pydantic validators for input parameters",
                            expected_impact="Reduce tool call errors by 15%",
                        )
                    ],
                ),
                context_management=Evaluation(
                    score=8.0,
                    explanation="Context is relevant and well-organized",
                    evidence=["context_1"],
                    improvements=[],
                ),
                response_quality=Evaluation(
                    score=9.0,
                    explanation="Responses are accurate and helpful",
                    evidence=["message_2"],
                    improvements=[],
                ),
                conversation_efficiency=Evaluation(
                    score=8.0,
                    explanation="Good conversation flow with minimal unnecessary steps",
                    evidence=["flow_1"],
                    improvements=[],
                ),
            ),
            summary="Overall strong performance with minor areas for improvement in tool validation.",
        )

        # Mock the PydanticAI agent run
        with patch("devboard.services.conversation_evaluator_service.PydanticAgent") as mock_agent_class:
            mock_agent_instance = Mock()
            mock_agent_class.return_value = mock_agent_instance

            mock_result = Mock()
            mock_result.output = mock_evaluation
            mock_agent_instance.run = AsyncMock(return_value=mock_result)

            # Run evaluation
            result = await evaluator_service.evaluate_conversation(
                sample_conversation.id, evaluator_model_id="anthropic:claude-sonnet-4"
            )

            # Verify result
            assert isinstance(result, ConversationEvaluation)
            assert result.overall_rating == 8.5
            assert result.evaluations.system_prompt_effectiveness.score == 9.0
            assert len(result.evaluations.tool_specification_quality.improvements) == 1
            assert result.summary == "Overall strong performance with minor areas for improvement in tool validation."

    def test_db_message_to_events_user_prompt(self, evaluator_service):
        """Test converting user prompt message to event."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        msg = ConversationMessage(
            conversation_id=1,
            message_type=MessageType.USER_PROMPT,
            text_content="Hello, agent!",
            pydantic_content={},
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        events = evaluator_service._db_message_to_events(msg)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].text_content == "Hello, agent!"

    def test_db_message_to_events_text_response(self, evaluator_service):
        """Test converting agent text response to event."""
        msg = ConversationMessage(
            conversation_id=1,
            message_type=MessageType.TEXT_RESPONSE,
            text_content="Hello, user!",
            pydantic_content={},
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        events = evaluator_service._db_message_to_events(msg)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.AGENT
        assert events[0].text_content == "Hello, user!"


class TestConversationEvaluationModels:
    """Tests for evaluation data models."""

    def test_evaluation_model_creation(self):
        """Test creating Evaluation model with improvements."""
        evaluation = Evaluation(
            score=7.5,
            explanation="Good performance with room for improvement",
            evidence=["event_1", "event_2"],
            improvements=[
                Improvement(
                    priority=Priority.HIGH,
                    title="Improve error handling",
                    description="Add better error messages",
                    suggested_changes="Add try-catch blocks with descriptive errors",
                    expected_impact="Improve user experience and debugging",
                )
            ],
        )

        assert evaluation.score == 7.5
        assert len(evaluation.evidence) == 2
        assert len(evaluation.improvements) == 1
        assert evaluation.improvements[0].priority == Priority.HIGH

    def test_conversation_evaluation_model(self):
        """Test creating full ConversationEvaluation model."""
        evaluation = ConversationEvaluation(
            overall_rating=8.0,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(
                    score=8.0, explanation="Good", evidence=[], improvements=[]
                ),
                tool_specification_quality=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                context_management=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                response_quality=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                conversation_efficiency=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
            ),
            summary="Overall good performance",
        )

        assert evaluation.overall_rating == 8.0
        assert evaluation.summary == "Overall good performance"
        assert evaluation.evaluations.system_prompt_effectiveness.score == 8.0

    def test_tool_specification_model(self):
        """Test creating ToolSpecification model."""
        tool_spec = ToolSpecification(
            name="search_documents",
            description="Search through project documents",
            parameters={"query": "str", "limit": "int"},
            requires_approval=False,
        )

        assert tool_spec.name == "search_documents"
        assert tool_spec.requires_approval is False
        assert "query" in tool_spec.parameters


class TestEvaluationPersistence:
    """Tests for evaluation persistence functionality."""

    @pytest.mark.asyncio
    async def test_evaluate_conversation_with_persistence(
        self, evaluator_service, sample_conversation, sample_messages, evaluation_repository
    ):
        """Test that evaluations are persisted to database when persist=True."""
        # Mock the evaluation agent to return a structured result
        mock_evaluation = ConversationEvaluation(
            overall_rating=8.5,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(
                    score=9.0,
                    explanation="Clear and well-structured system prompt",
                    evidence=["message_1"],
                    improvements=[],
                ),
                tool_specification_quality=Evaluation(
                    score=8.5, explanation="Tools are well-defined", evidence=[], improvements=[]
                ),
                context_management=Evaluation(score=8.0, explanation="Context is relevant", evidence=[], improvements=[]),
                response_quality=Evaluation(score=9.0, explanation="Responses are accurate", evidence=[], improvements=[]),
                conversation_efficiency=Evaluation(
                    score=8.0, explanation="Good conversation flow", evidence=[], improvements=[]
                ),
            ),
            summary="Overall strong performance.",
        )

        # Mock the PydanticAI agent run
        with patch("devboard.services.conversation_evaluator_service.PydanticAgent") as mock_agent_class:
            mock_agent_instance = Mock()
            mock_agent_class.return_value = mock_agent_instance

            mock_result = Mock()
            mock_result.output = mock_evaluation
            mock_agent_instance.run = AsyncMock(return_value=mock_result)

            # Run evaluation with persist=True
            result = await evaluator_service.evaluate_conversation(
                sample_conversation.id, evaluator_model_id="anthropic:claude-sonnet-4", persist=True
            )

            # Verify result
            assert isinstance(result, ConversationEvaluation)
            assert result.overall_rating == 8.5

            # Verify persistence
            db_evaluations = evaluation_repository.get_by_conversation_id(sample_conversation.id)
            assert len(db_evaluations) == 1
            assert db_evaluations[0].overall_rating == 8.5
            assert db_evaluations[0].evaluator_model_id == "anthropic:claude-sonnet-4"
            assert db_evaluations[0].summary == "Overall strong performance."

    @pytest.mark.asyncio
    async def test_evaluate_conversation_without_persistence(
        self, evaluator_service, sample_conversation, sample_messages, evaluation_repository
    ):
        """Test that evaluations are not persisted when persist=False."""
        # Mock the evaluation agent
        mock_evaluation = ConversationEvaluation(
            overall_rating=7.5,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                tool_specification_quality=Evaluation(score=7.0, explanation="OK", evidence=[], improvements=[]),
                context_management=Evaluation(score=7.5, explanation="Good", evidence=[], improvements=[]),
                response_quality=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                conversation_efficiency=Evaluation(score=7.5, explanation="Good", evidence=[], improvements=[]),
            ),
            summary="Good performance.",
        )

        with patch("devboard.services.conversation_evaluator_service.PydanticAgent") as mock_agent_class:
            mock_agent_instance = Mock()
            mock_agent_class.return_value = mock_agent_instance

            mock_result = Mock()
            mock_result.output = mock_evaluation
            mock_agent_instance.run = AsyncMock(return_value=mock_result)

            # Run evaluation with persist=False
            result = await evaluator_service.evaluate_conversation(
                sample_conversation.id, evaluator_model_id="anthropic:claude-sonnet-4", persist=False
            )

            # Verify result
            assert isinstance(result, ConversationEvaluation)

            # Verify no persistence
            db_evaluations = evaluation_repository.get_by_conversation_id(sample_conversation.id)
            assert len(db_evaluations) == 0

    def test_get_evaluations_for_conversation(self, evaluator_service, evaluation_repository, sample_conversation):
        """Test retrieving evaluations for a conversation."""
        # Create some test evaluations
        from devboard.agents.evaluation_models import ConversationEvaluation as EvalResult

        mock_eval = ConversationEvaluation(
            overall_rating=8.0,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                tool_specification_quality=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                context_management=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                response_quality=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
                conversation_efficiency=Evaluation(score=8.0, explanation="Good", evidence=[], improvements=[]),
            ),
            summary="Test evaluation",
        )

        evaluation_repository.create(
            conversation_id=sample_conversation.id,
            evaluator_model_id="test-model",
            overall_rating=mock_eval.overall_rating,
            evaluations_json=mock_eval.evaluations.model_dump(mode="json"),
            summary=mock_eval.summary,
        )

        # Retrieve evaluations
        evaluations = evaluator_service.get_evaluations_for_conversation(sample_conversation.id)

        assert len(evaluations) == 1
        assert evaluations[0].overall_rating == 8.0
        assert evaluations[0].summary == "Test evaluation"

    def test_get_latest_evaluation(self, evaluator_service, evaluation_repository, sample_conversation):
        """Test retrieving the latest evaluation."""
        mock_eval = ConversationEvaluation(
            overall_rating=9.0,
            evaluations=PerformanceEvaluations(
                system_prompt_effectiveness=Evaluation(score=9.0, explanation="Excellent", evidence=[], improvements=[]),
                tool_specification_quality=Evaluation(
                    score=9.0, explanation="Excellent", evidence=[], improvements=[]
                ),
                context_management=Evaluation(score=9.0, explanation="Excellent", evidence=[], improvements=[]),
                response_quality=Evaluation(score=9.0, explanation="Excellent", evidence=[], improvements=[]),
                conversation_efficiency=Evaluation(score=9.0, explanation="Excellent", evidence=[], improvements=[]),
            ),
            summary="Latest evaluation",
        )

        # Create evaluation
        evaluation_repository.create(
            conversation_id=sample_conversation.id,
            evaluator_model_id="test-model",
            overall_rating=mock_eval.overall_rating,
            evaluations_json=mock_eval.evaluations.model_dump(mode="json"),
            summary=mock_eval.summary,
        )

        # Retrieve latest
        latest = evaluator_service.get_latest_evaluation(sample_conversation.id)

        assert latest is not None
        assert latest.overall_rating == 9.0
        assert latest.summary == "Latest evaluation"
