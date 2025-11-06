"""Service for evaluating agent conversation performance.

This service analyzes completed conversations to assess agent performance
across multiple dimensions and provides structured feedback with improvement
suggestions.
"""

import datetime
import json
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from devboard.agents.engines.internal.agent import InternalAgent
from devboard.agents.evaluation_models import (
    AgentSpecification,
    ConversationAnalysis,
    ConversationEvaluation,
    ToolSpecification,
)
from devboard.agents.events import ConversationEvent, MessageRole, TextMessage, ToolCall, ToolResult
from devboard.agents.language_models import LanguageModel, llm_registry
from devboard.agents.roles.base import Role
from devboard.agents.roles.conversation_evaluator import ConversationEvaluatorRole
from devboard.agents.roles.project_qa import ProjectQARole
from devboard.agents.roles.task_implementation import TaskImplementationRole
from devboard.agents.roles.task_planning import TaskPlanningRole
from devboard.agents.roles.task_specification import TaskSpecificationRole
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import (
    Conversation,
    ConversationMessage,
    MessageType,
    ParentEntityType,
    Project,
    Task,
)
from devboard.db.models.conversation_evaluation import ConversationEvaluation as DbConversationEvaluation
from devboard.db.repositories import (
    ConversationEvaluationRepository,
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)


class ConversationEvaluatorService:
    """Service for evaluating agent conversation performance."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        project_repo: ProjectRepository,
        task_repo: TaskRepository,
        document_repo: DocumentRepository,
        evaluation_repo: ConversationEvaluationRepository | None = None,
    ):
        """Initialize conversation evaluator service.

        Args:
            conversation_repo: Repository for conversation data access
            project_repo: Repository for project data access
            task_repo: Repository for task data access
            document_repo: Repository for document data access
            evaluation_repo: Optional repository for persisting evaluation results
        """
        self.conversation_repo = conversation_repo
        self.project_repo = project_repo
        self.task_repo = task_repo
        self.document_repo = document_repo
        self.evaluation_repo = evaluation_repo

    async def evaluate_conversation(
        self,
        conversation_id: int,
        evaluator_model_id: str | None = None,
        persist: bool = True,
    ) -> ConversationEvaluation:
        """Evaluate a conversation and return structured feedback.

        Args:
            conversation_id: ID of the conversation to evaluate
            evaluator_model_id: Optional model ID for the evaluator agent
                               (defaults to a capable model like Claude Sonnet 4)
            persist: Whether to persist the evaluation to database (default True)

        Returns:
            ConversationEvaluation with scores and improvement suggestions

        Raises:
            ValueError: If conversation not found or has no messages
        """
        # Retrieve conversation
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Retrieve messages
        db_messages = self.conversation_repo.get_messages(conversation_id)
        if not db_messages:
            raise ValueError(f"Conversation {conversation_id} has no messages")

        # Get role for the conversation
        role = await self._get_role_for_conversation(conversation)

        # Format agent specification
        agent_spec = await self._format_agent_specification(conversation, role)

        # Convert messages to events
        events = self._convert_messages_to_events(db_messages)

        # Calculate metadata
        tool_call_count = sum(1 for event in events if isinstance(event, ToolCall))

        # Create conversation analysis
        analysis = ConversationAnalysis(
            conversation_id=conversation_id,
            agent_specification=agent_spec,
            engine=conversation.engine,
            model_id=conversation.model_id or "default",
            events=events,
            started_at=conversation.created_at,
            event_count=len(events),
            tool_call_count=tool_call_count,
        )

        # Run evaluation agent and get model ID used
        evaluation, actual_model_id = await self._run_evaluation_agent(analysis, evaluator_model_id)

        # Persist evaluation if requested and repository is available
        if persist and self.evaluation_repo:
            db_evaluation = DbConversationEvaluation.from_evaluation_result(
                conversation_id=conversation_id,
                evaluator_model_id=actual_model_id,
                evaluation=evaluation,
            )
            self.evaluation_repo.create(
                conversation_id=db_evaluation.conversation_id,
                evaluator_model_id=db_evaluation.evaluator_model_id,
                overall_rating=db_evaluation.overall_rating,
                evaluations_json=db_evaluation.evaluations_json,
                summary=db_evaluation.summary,
            )

        return evaluation

    async def _get_role_for_conversation(self, conversation: Conversation) -> Role:
        """Get the role instance for a conversation.

        Args:
            conversation: Conversation instance

        Returns:
            Role instance configured for this conversation

        Raises:
            ValueError: If role type is unsupported or parent entity not found
        """
        # Get parent entity
        if conversation.parent_entity_type == ParentEntityType.TASK:
            task = self.task_repo.get_by_id(conversation.parent_entity_id)
            if not task:
                raise ValueError(f"Task {conversation.parent_entity_id} not found")
            parent_entity = task
        elif conversation.parent_entity_type == ParentEntityType.PROJECT:
            project = self.project_repo.get_by_id(conversation.parent_entity_id)
            if not project:
                raise ValueError(f"Project {conversation.parent_entity_id} not found")
            parent_entity = project
        else:
            raise ValueError(f"Unsupported parent entity type: {conversation.parent_entity_type}")

        # Create role based on agent_role type
        if conversation.agent_role == AgentRoleType.PROJECT:
            if not isinstance(parent_entity, Project):
                raise ValueError(f"Expected Project for PROJECT role, got {type(parent_entity)}")
            return ProjectQARole(project=parent_entity, document_repository=self.document_repo)

        elif conversation.agent_role == AgentRoleType.TASK_SPECIFICATION:
            if not isinstance(parent_entity, Task):
                raise ValueError(f"Expected Task for TASK_SPECIFICATION role, got {type(parent_entity)}")
            # Note: AgentConfigService not needed for evaluation, using None
            return TaskSpecificationRole(
                task=parent_entity, document_repository=self.document_repo, agent_config_service=None  # type: ignore
            )

        elif conversation.agent_role == AgentRoleType.TASK_PLANNING:
            if not isinstance(parent_entity, Task):
                raise ValueError(f"Expected Task for TASK_PLANNING role, got {type(parent_entity)}")
            return TaskPlanningRole(
                task=parent_entity, document_repository=self.document_repo, agent_config_service=None  # type: ignore
            )

        elif conversation.agent_role == AgentRoleType.TASK_IMPLEMENTATION:
            if not isinstance(parent_entity, Task):
                raise ValueError(f"Expected Task for TASK_IMPLEMENTATION role, got {type(parent_entity)}")
            return TaskImplementationRole(task=parent_entity, document_repository=self.document_repo)

        else:
            raise ValueError(f"Unsupported agent role for evaluation: {conversation.agent_role}")

    async def _format_agent_specification(self, conversation: Conversation, role: Role) -> AgentSpecification:
        """Extract and format agent configuration.

        Args:
            conversation: Conversation instance
            role: Role instance for the conversation

        Returns:
            AgentSpecification with formatted agent configuration
        """
        # Extract tool specifications
        tools = role.get_tools()
        tool_specs = []
        for tool in tools:
            # Extract tool metadata from PydanticAI Tool
            tool_specs.append(
                ToolSpecification(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=self._extract_tool_parameters(tool),
                    requires_approval=tool.requires_approval,
                )
            )

        # Get context content
        context_content = await role.get_context_content()

        # Truncate context if too long (keep first 5000 chars for summary)
        context_summary = context_content[:5000] + "..." if len(context_content) > 5000 else context_content

        return AgentSpecification(
            role_type=conversation.agent_role,
            system_prompt=role.get_system_prompt(),
            tools=tool_specs,
            context_summary=context_summary,
            allowed_builtin_tools=role.allowed_builtin_tools,
        )

    def _extract_tool_parameters(self, tool: Any) -> dict[str, Any]:
        """Extract parameter schema from a PydanticAI Tool.

        Args:
            tool: PydanticAI Tool instance

        Returns:
            Dictionary representing parameter schema
        """
        try:
            # Try to get function signature if available
            if hasattr(tool, "function") and hasattr(tool.function, "__annotations__"):
                return {
                    "parameters": {
                        name: str(annotation) for name, annotation in tool.function.__annotations__.items()
                    }
                }
            return {}
        except Exception:
            return {}

    def _convert_messages_to_events(self, db_messages: list[ConversationMessage]) -> list[ConversationEvent]:
        """Convert database messages to ConversationEvent objects.

        Args:
            db_messages: List of database conversation messages

        Returns:
            List of ConversationEvent instances
        """
        events: list[ConversationEvent] = []

        for msg in db_messages:
            # Convert each database message to appropriate ConversationEvent type(s)
            msg_events = self._db_message_to_events(msg)
            events.extend(msg_events)

        return events

    def _db_message_to_events(self, msg: ConversationMessage) -> list[ConversationEvent]:
        """Convert a database message to one or more ConversationEvent objects.

        Args:
            msg: Database conversation message

        Returns:
            List of ConversationEvent objects representing the message content
        """
        events: list[ConversationEvent] = []

        if msg.message_type == MessageType.USER_PROMPT:
            # User prompt - single text message
            events.append(
                TextMessage(
                    role=MessageRole.USER,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type == MessageType.TEXT_RESPONSE:
            # Agent text response - single text message
            events.append(
                TextMessage(
                    role=MessageRole.AGENT,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type in (MessageType.TOOL_CALL, MessageType.TOOL_RESULT, MessageType.STRUCTURED_RESPONSE):
            # Parse PydanticAI message to extract tool calls and results
            pydantic_msg = ModelMessagesTypeAdapter.validate_python([msg.pydantic_content])[0]
            events.extend(self._parse_pydantic_message_for_tools(pydantic_msg, msg.timestamp))

        return events

    def _parse_pydantic_message_for_tools(
        self, pydantic_msg: ModelMessage, timestamp: datetime.datetime
    ) -> list[ConversationEvent]:
        """Parse a PydanticAI message to extract tool-related events.

        Args:
            pydantic_msg: PydanticAI ModelMessage instance
            timestamp: Timestamp for the events

        Returns:
            List of ToolCall and ToolResult events
        """
        events: list[ConversationEvent] = []

        for part in pydantic_msg.parts:
            if isinstance(part, ToolCallPart):
                # Tool call event
                events.append(
                    ToolCall(
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        tool_args=part.args.args_dict if part.args else None,
                        timestamp=timestamp,
                    )
                )
            elif isinstance(part, ToolReturnPart):
                # Tool result success
                events.append(
                    ToolResult(
                        tool_call_id=part.tool_call_id,
                        result_content=str(part.content),
                        is_error=False,
                        timestamp=timestamp,
                    )
                )
            elif isinstance(part, RetryPromptPart):
                # Tool result error
                events.append(
                    ToolResult(
                        tool_call_id=part.tool_call_id,
                        result_content=part.content,
                        is_error=True,
                        timestamp=timestamp,
                    )
                )

        return events

    async def _run_evaluation_agent(
        self, analysis: ConversationAnalysis, evaluator_model_id: str | None
    ) -> tuple[ConversationEvaluation, str]:
        """Execute the evaluator agent and parse structured output.

        Args:
            analysis: Conversation analysis data
            evaluator_model_id: Optional model ID for evaluator

        Returns:
            Tuple of (ConversationEvaluation, model_id_used)

        Raises:
            ValueError: If evaluation fails or output is invalid
        """
        # Get model for evaluation (default to a capable model)
        if evaluator_model_id:
            model = llm_registry.get(evaluator_model_id)
            if not model:
                raise ValueError(f"Model {evaluator_model_id} not found in registry")
            actual_model_id = evaluator_model_id
        else:
            # Default to Claude Sonnet 4 if available, otherwise first available model
            model = llm_registry.get("anthropic:claude-sonnet-4")
            if model:
                actual_model_id = "anthropic:claude-sonnet-4"
            else:
                available_models = llm_registry.list_values()
                if not available_models:
                    raise ValueError("No LLM models configured")
                model = available_models[0]
                actual_model_id = model.id

        # Create evaluator role with conversation analysis
        evaluator_role = ConversationEvaluatorRole(conversation_analysis=analysis)

        # Create internal agent with structured output type
        agent = InternalAgent(role=evaluator_role, model=model)

        # Build context message
        context_request = await agent.build_system_and_context_messages()

        # Create PydanticAI agent with structured output
        from pydantic_ai import Agent as PydanticAgent

        pydantic_agent = PydanticAgent(
            agent._get_model(),
            system_prompt=evaluator_role.get_system_prompt(),
            output_type=ConversationEvaluation,
        )

        # Run agent with context as initial history
        result = await pydantic_agent.run(
            user_prompt="Please evaluate this conversation.",
            message_history=[context_request],
        )

        # Extract structured output
        if not isinstance(result.output, ConversationEvaluation):
            raise ValueError(f"Expected ConversationEvaluation output, got {type(result.output)}")

        return result.output, actual_model_id

    def get_evaluations_for_conversation(self, conversation_id: int) -> list[ConversationEvaluation]:
        """Get all evaluations for a conversation from the database.

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of ConversationEvaluation objects (from Pydantic models)

        Raises:
            ValueError: If evaluation repository is not configured
        """
        if not self.evaluation_repo:
            raise ValueError("Evaluation repository is not configured")

        db_evaluations = self.evaluation_repo.get_by_conversation_id(conversation_id)
        return [db_eval.to_evaluation_result() for db_eval in db_evaluations]

    def get_latest_evaluation(self, conversation_id: int) -> ConversationEvaluation | None:
        """Get the most recent evaluation for a conversation from the database.

        Args:
            conversation_id: ID of the conversation

        Returns:
            ConversationEvaluation object or None if no evaluations exist

        Raises:
            ValueError: If evaluation repository is not configured
        """
        if not self.evaluation_repo:
            raise ValueError("Evaluation repository is not configured")

        db_evaluation = self.evaluation_repo.get_latest_by_conversation_id(conversation_id)
        return db_evaluation.to_evaluation_result() if db_evaluation else None
