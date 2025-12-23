import datetime
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.db.models import ParentEntityType
from devboard.db.models.conversation import AgentRoleType
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import RebaseConflictError
from devboard.workflow_actions.base import TaskWorkflowAction


class CreateImplementationPlanAction(TaskWorkflowAction):
    """Workflow action that transitions a task to PLANNING and generates an implementation plan.

    This action:
    1. Validates the task has a specification
    2. Creates an implementation_plan document if needed
    3. Updates task status to PLANNING
    4. Reuses the conversation (if same engine) or creates new one for the planning phase
    5. Emits a TASK_UPDATED SystemEvent
    6. Streams the agent's implementation plan generation

    Note: Conversation is reused from DEFINING→PLANNING to maintain specification context.
    """

    KEY = "task.create_implementation_plan"

    PROMPT = "Proceed with creating a detailed technical implementation plan for the task, following your behaviour guidelines"

    @property
    def key(self) -> str:
        return self.KEY

    @property
    def description(self) -> str:
        return "Generate a technical implementation plan from the task specification"

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: transition to PLANNING and generate implementation plan.

        Yields:
            ConversationEvent objects including SystemEvent and agent messages

        Raises:
            ValueError: If task is not in DEFINING status or transition validation fails
        """
        # Transition task to PLANNING (validates status, creates implementation_plan doc, updates status)
        self.task_service.transition_to_planning(self.task)

        # Handle conversation: reuse if DEFINING→PLANNING with same engine, otherwise replace
        current_conversation = self.conversation_repo.get_active_conversation_for_entity(
            ParentEntityType.TASK, self.task.id
        )
        new_agent_role = AgentRoleType.TASK_PLANNING
        agent_config = self.agent_config_service.get_agent_configuration(new_agent_role)

        # Check if we can reuse the conversation when same engine
        if current_conversation.engine == agent_config.config.engine:
            # Reuse conversation by updating role and model
            new_conversation = self.conversation_repo.update_role_and_model(
                conversation=current_conversation,
                agent_role=new_agent_role,
                model_id=agent_config.config.model_id,
            )
        else:
            # Replace: archive current and create new conversation
            new_conversation = self.conversation_service.replace_active_conversation(
                entity_type=ParentEntityType.TASK,
                entity_id=self.task.id,
                new_agent_role=new_agent_role,
            )

        # Commit changes before sending event
        self.conversation_repo.commit()

        # Emit SystemEvent for task update
        yield SystemEvent(
            event_type="system",
            type=SystemEventType.TASK_UPDATED,
            data={
                "task_id": self.task.id,
                "updated_fields": {
                    "status": self.task.status.value,
                    "conversation_id": new_conversation.id,
                    "implementation_plan_id": self.task.implementation_plan_id,
                },
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Create agent service for the new conversation with correct role
        agent_conversation_service = self._create_agent_conversation_service(new_conversation)

        agent_event_stream = self.workspace_allocation_service.run_task_agent_in_workspace(
            task=self.task,
            agent_stream=agent_conversation_service.stream_events_for_message_or_approval(self.PROMPT),
        )

        # Stream agent prompt events
        async for event in agent_event_stream:
            yield event


class BeginImplementationAction(TaskWorkflowAction):
    """Workflow action that transitions a task to IMPLEMENTING and begins implementation.

    This action:
    1. Validates the task has an implementation plan
    2. Updates task status to IMPLEMENTING
    3. Creates a new conversation for the implementation phase (archives planning conversation)
    4. Emits a TASK_UPDATED SystemEvent
    5. Streams the agent's implementation work

    Note: Always creates a new conversation to provide clean context for implementation.
    """

    KEY = "task.begin_implementation"
    PROMPT_TEMPLATE = "The implementation plan has been approved. Your goal is to write the code to fulfill the plan."

    @property
    def key(self) -> str:
        return self.KEY

    @property
    def description(self) -> str:
        return "Start implementing the approved plan"

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: transition to IMPLEMENTING and begin implementation.

        Yields:
            ConversationEvent objects including SystemEvent and agent messages

        Raises:
            ValueError: If task is not in PLANNING status or transition validation fails
        """
        # Transition task to IMPLEMENTING (validates status, updates status)
        self.task_service.transition_to_implementing(self.task)

        # Always create new conversation for implementation (clean context)
        new_conversation = self.conversation_service.replace_active_conversation(
            entity_type=ParentEntityType.TASK,
            entity_id=self.task.id,
            new_agent_role=AgentRoleType.TASK_IMPLEMENTATION,
        )
        # Commit changes before sending event
        self.conversation_repo.commit()

        # Emit SystemEvent for task update
        yield SystemEvent(
            event_type="system",
            type=SystemEventType.TASK_UPDATED,
            data={
                "task_id": self.task.id,
                "updated_fields": {
                    "status": self.task.status.value,
                    "conversation_id": new_conversation.id,
                },
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Create agent service for the new conversation with correct role
        agent_conversation_service = self._create_agent_conversation_service(new_conversation)

        agent_event_stream = self.workspace_allocation_service.run_task_agent_in_workspace(
            task=self.task,
            agent_stream=agent_conversation_service.stream_events_for_message_or_approval(self.PROMPT_TEMPLATE),
        )

        # Stream agent prompt events
        async for event in agent_event_stream:
            yield event


class RebaseTaskBranchAction(TaskWorkflowAction):
    """Workflow action that rebases a task's feature branch onto its base branch.

    This action:
    1. Stashes uncommitted changes (if any)
    2. Rebases the feature branch onto the base branch
    3. Restores stashed changes
    4. If stash apply conflicts, hands off to agent to resolve

    Replaces the direct rebase endpoint with a streaming workflow action.
    """

    KEY = "task.rebase_branch"

    @property
    def key(self) -> str:
        return self.KEY

    @property
    def description(self) -> str:
        return "Rebase task branch onto base branch"

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: rebase branch with stash handling.

        Yields:
            ConversationEvent objects including SystemEvents and optionally agent messages

        Raises:
            ValueError: If task has no branch name or worktree slot
        """
        task = self.task

        try:
            result = await self.task_git_service.rebase_task_branch(task)
        except ValueError as e:
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={"message": str(e)},
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return
        except RebaseConflictError as e:
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={"message": str(e), "error_code": "REBASE_CONFLICT"},
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return

        # Emit success event
        yield SystemEvent(
            event_type="system",
            type=SystemEventType.BRANCH_REBASED,
            data={
                "task_id": task.id,
                "message": f"Rebased onto {task.base_branch}",
                "new_head": result.new_head,
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # If stash couldn't be applied cleanly, hand to agent to resolve conflicts
        if result.has_stash_conflicts:
            git = GitRepoIntegration(result.slot_path)

            # Get list of conflicted files for context
            conflicted_files = await git.get_conflicted_files()
            conflict_list = (
                "\n".join(f"  - {f}" for f in conflicted_files) if conflicted_files else "  (unable to determine)"
            )

            # Emit event to notify UI that stash apply had conflicts
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STASH_APPLY_CONFLICT,
                data={
                    "task_id": task.id,
                    "message": "Stash apply had conflicts - agent will resolve",
                    "conflicted_files": conflicted_files,
                },
                timestamp=datetime.datetime.now(datetime.UTC),
            )

            # Get or create implementation conversation for agent
            current_conversation = self.conversation_repo.get_active_conversation_for_entity(
                ParentEntityType.TASK, task.id
            )

            agent_service = self._create_agent_conversation_service(current_conversation)
            prompt = (
                f"The rebase onto {task.base_branch} succeeded, but restoring your uncommitted changes "
                f"resulted in merge conflicts.\n\n"
                f"**Conflicted files:**\n{conflict_list}\n\n"
                f"Please resolve the merge conflicts in these files."
            )

            # Run agent within workspace context
            agent_event_stream = self.workspace_allocation_service.run_task_agent_in_workspace(
                task=task,
                agent_stream=agent_service.stream_events_for_message_or_approval(prompt),
            )

            async for event in agent_event_stream:
                yield event
