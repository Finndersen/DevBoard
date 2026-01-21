import datetime
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.db.models import ParentEntityType, Task
from devboard.db.models.codebase import BranchHandling
from devboard.db.models.conversation import AgentRoleType
from devboard.db.models.task import TaskStatus
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.github import GitHubIntegration
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
    DESCRIPTION = "Generate a technical implementation plan from the task specification"

    PROMPT = "Proceed with creating a detailed technical implementation plan for the task, following your behaviour guidelines"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is DEFINING and specification has content.
        """
        return (
            task.status == TaskStatus.DEFINING
            and task.specification is not None
            and bool(task.specification.content.strip())
        )

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

        # Stream agent response for the new conversation
        async for event in self._stream_agent_response(new_conversation, self.PROMPT):
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
    DESCRIPTION = "Start implementing the approved plan"

    PROMPT_TEMPLATE = "The implementation plan has been approved. Your goal is to write the code to fulfill the plan."

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is PLANNING and implementation plan has content.
        """
        return task.status == TaskStatus.PLANNING and task.implementation_plan_id is not None

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

        # Stream agent response for the new conversation
        async for event in self._stream_agent_response(new_conversation, self.PROMPT_TEMPLATE):
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
    DESCRIPTION = "Rebase task branch onto base branch"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is IMPLEMENTING and task has feature branch.
        """
        return task.status == TaskStatus.IMPLEMENTING and task.branch_name is not None

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

            prompt = (
                f"The rebase onto {task.base_branch} succeeded, but restoring your uncommitted changes "
                f"resulted in merge conflicts.\n\n"
                f"**Conflicted files:**\n{conflict_list}\n\n"
                f"Please resolve the merge conflicts in these files."
            )

            # Stream agent response to resolve conflicts
            async for event in self._stream_agent_response(current_conversation, prompt):
                yield event


class ApproveAndMergeAction(TaskWorkflowAction):
    """Workflow action for solo/local development - approve changes and merge feature branch locally.

    This action prompts the agent to:
    1. Commit any uncommitted changes
    2. Complete the task using the complete_task_with_local_merge tool (includes change summary)

    The complete_task_with_local_merge tool creates the change summary document, merges the branch,
    and transitions the task to COMPLETE status.
    """

    KEY = "task.approve_and_merge"
    PROMPT = """Finalize this task for local merge.

Please do the following:
1. Review any uncommitted changes in the workspace
2. If there are uncommitted changes, create appropriate commit(s) with clear commit messages
3. Once all changes are committed, use the complete_task_with_local_merge tool to merge the feature branch and complete the task. Include a change_summary with:
   - A brief overview of what was implemented
   - Key files that were added or modified
   - Any notable implementation decisions or trade-offs
   - Testing considerations or known limitations"""

    DESCRIPTION = "Approve changes and merge locally"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is IMPLEMENTING, task has feature branch,
        and branch handling is LOCAL_MERGE.
        """
        return (
            task.status == TaskStatus.IMPLEMENTING
            and task.branch_name is not None
            and task.codebase.branch_handling == BranchHandling.LOCAL_MERGE.value
        )

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: agent commits and calls merge tool.

        Yields:
            ConversationEvent objects from agent interaction
        """
        # Stream agent response - agent uses role's complete_task_with_local_merge tool
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, self.PROMPT):
            yield event


class ApproveAndCreatePRAction(TaskWorkflowAction):
    """Workflow action for GitHub workflows - approve changes and create a pull request.

    This action prompts the agent to:
    1. Review and commit any uncommitted changes
    2. Create a GitHub PR using the create_pull_request tool

    The create_pull_request tool handles:
    - Creating the PR on GitHub
    - Transitioning task to PR_OPEN
    - Creating new conversation with TASK_PR_REVIEW role
    """

    KEY = "task.approve_and_create_pr"
    PROMPT = """Finalize and create a pull request for this task.

Please do the following:
1. Review any uncommitted changes in the workspace
2. If there are uncommitted changes, create appropriate atomic commit(s) with clear & concise commit messages
3. Once all changes are committed, use the create_pull_request tool to create a GitHub PR

When creating the PR:
- Use a clear, descriptive title that summarizes what this task accomplishes
- Write a comprehensive PR description that includes:
  - Context of the task and its purpose
  - A summary of the changes made
  - Any notable implementation decisions
  - Testing notes if applicable

The PR will be created against the base branch and the task will transition to PR_OPEN status."""

    DESCRIPTION = "Approve changes and create PR"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is IMPLEMENTING, has feature branch, codebase has GitHub remote,
        and branch handling is GITHUB_PR.
        """
        return (
            task.status == TaskStatus.IMPLEMENTING
            and task.branch_name is not None
            and task.codebase.repository_url is not None
            and task.codebase.branch_handling == BranchHandling.GITHUB_PR.value
        )

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: prompt agent to commit changes and create PR.

        The create_pull_request tool (provided by role) handles transitioning task
        to PR_OPEN and creating new conversation with TASK_PR_REVIEW role.

        Yields:
            ConversationEvent objects from agent interaction
        """
        # Check GitHub connection early to fail fast
        github = self.integration_service.get_integration_instance(GitHubIntegration)
        connection_result = await github.test_connection()
        if not connection_result.success:
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={"message": f"GitHub connection failed: {connection_result.message}"},
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return

        # Stream agent response - agent uses role's create_pull_request tool
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, self.PROMPT):
            yield event


class MergeAndFinaliseAction(TaskWorkflowAction):
    """Workflow action to merge an open PR via GitHub and complete the task.

    This action prompts the agent to:
    1. Ensure all changes are committed and pushed
    2. Use the merge_pr_and_complete_task tool to merge the PR and complete the task

    The merge_pr_and_complete_task tool handles:
    - Merging the PR via GitHub API
    - Creating the change summary document
    - Deleting the local feature branch
    - Transitioning the task to COMPLETE status
    """

    KEY = "task.merge_and_finalise"
    PROMPT = """Merge this PR and complete the task.

Please do the following:
1. Review any uncommitted changes in the workspace
2. If there are uncommitted changes, create appropriate commit(s) and push them
3. Once all changes are committed and pushed, use the merge_pr_and_complete_task tool to merge the PR and complete the task. Include a change_summary with:
   - A brief overview of what was implemented
   - Key files that were added or modified
   - Any notable implementation decisions or trade-offs
   - Testing considerations or known limitations"""

    DESCRIPTION = "Merge PR and complete task"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is PR_OPEN and task has PR reference.
        """
        return task.status == TaskStatus.PR_OPEN and task.github_pr_number is not None

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: prompt agent to merge PR and complete task.

        The merge_pr_and_complete_task tool (provided by role) handles the merge
        and task completion.

        Yields:
            ConversationEvent objects from agent interaction
        """
        # Check GitHub connection early to fail fast
        github = self.integration_service.get_integration_instance(GitHubIntegration)
        connection_result = await github.test_connection()
        if not connection_result.success:
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={"message": f"GitHub connection failed: {connection_result.message}"},
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return

        # Stream agent response - agent uses role's merge_pr_and_complete_task tool
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, self.PROMPT):
            yield event


class FinaliseAction(TaskWorkflowAction):
    """Workflow action to complete a task when manual branch handling is configured.

    This action:
    1. Validates the task is in IMPLEMENTING status with MANUAL branch handling
    2. Skips change summary generation (user manages branch manually)
    3. Transitions task to COMPLETE
    4. Emits TASK_UPDATED SystemEvent

    Used for tasks where the user manages the branch manually (e.g., external CI/CD).
    """

    KEY = "task.finalise"
    DESCRIPTION = "Complete task (no merge)"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is IMPLEMENTING and branch handling is MANUAL.
        """
        return task.status == TaskStatus.IMPLEMENTING and task.codebase.branch_handling == BranchHandling.MANUAL.value

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: transition task to COMPLETE.

        Yields:
            ConversationEvent objects including SystemEvent
        """
        # Transition task to COMPLETE (skip change summary for legacy tasks)
        self.task_service.transition_to_complete(self.task)

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
                },
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )
