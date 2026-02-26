import datetime
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.db.models import ParentEntityType, Task
from devboard.db.models.codebase import BranchHandling
from devboard.db.models.conversation import AgentRoleType
from devboard.db.models.task import TaskStatus
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git_service import TaskGitService
from devboard.workflow_actions.base import TaskWorkflowAction


async def _get_task_changes_prompt_context(task_git_service: TaskGitService, task: Task) -> str:
    """Build a prompt context string describing the current state of changes on the task branch.

    Returns a string with commit history and uncommitted change details that can be
    inserted into finalisation action prompts.
    """
    # Check if a worktree slot exists
    last_used_slot = task_git_service.worktree_slot_repo.get_last_used_slot_for_task(task.id)

    if not last_used_slot:
        return "Unable to determine branch state — no worktree slot found for this task."

    # Fetch commit history and uncommitted changes
    commits = await task_git_service.get_task_commit_metadata(task)
    uncommitted = await task_git_service.get_task_uncommitted_changes(task)

    parts: list[str] = []

    # Commit history
    if commits:
        commit_list = "\n".join(f"  - {c.hash[:7]}: {c.subject}" for c in commits)
        parts.append(f"**Commits on task branch** ({len(commits)}):\n{commit_list}")
    else:
        parts.append("No commits on task branch yet.")

    # Uncommitted changes
    if uncommitted.files:
        parts.append(f"**Uncommitted changes:**\n{uncommitted.format_summary()}")
    else:
        parts.append("No uncommitted changes.")

    return "\n\n".join(parts)


class CreateImplementationPlanAction(TaskWorkflowAction):
    """Workflow action that creates an implementation plan document and prompts the agent to generate it.

    This action:
    1. Validates the task is in PLANNING status and has no implementation plan yet
    2. Creates an implementation_plan document
    3. Emits a TASK_UPDATED SystemEvent
    4. Streams the agent's implementation plan generation

    Note: Does NOT change task status - task remains in PLANNING throughout.
    The same conversation is used for both specification and planning work.
    """

    KEY = "task.create_implementation_plan"
    DESCRIPTION = "Generate a technical implementation plan from the task specification"

    PROMPT = "Proceed with creating a detailed technical implementation plan for the task, following your behaviour guidelines"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: status is PLANNING, specification has content, and no implementation plan yet.
        """
        return (
            task.status == TaskStatus.PLANNING
            and task.specification is not None
            and bool(task.specification.content.strip())
            and task.implementation_plan is None
        )

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: create implementation plan document and generate content.

        Yields:
            ConversationEvent objects including SystemEvent and agent messages

        Raises:
            ValueError: If task is not in PLANNING status or already has an implementation plan
        """
        # Create implementation plan document (validates status, checks plan doesn't exist)
        self.task_service.create_implementation_plan(self.task)

        # Get the current conversation (no role change needed)
        current_conversation = self.conversation_repo.get_active_conversation_for_entity(
            ParentEntityType.TASK, self.task.id
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
                    "implementation_plan_id": self.task.implementation_plan_id,
                },
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # Stream agent response for the current conversation
        async for event in self._stream_agent_response(current_conversation, self.PROMPT):
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

    Behavior varies by task status:
    - PLANNING: Direct service call (no agent involvement, no file changes expected)
    - IMPLEMENTING: Delegates to agent with rebase_task_branch tool for conflict resolution

    For IMPLEMENTING, the agent handles:
    1. Stashing uncommitted changes (if any)
    2. Starting/continuing the rebase
    3. Conflict resolution (agent resolves, then calls tool again)
    4. Restoring stashed changes after successful rebase
    """

    KEY = "task.rebase_branch"
    DESCRIPTION = "Rebase task branch onto base branch"

    IMPLEMENTING_PROMPT = """Use the mcp__builtin_tools__rebase_task_branch tool to rebase this task's feature branch onto the base branch.

The tool is idempotent - if a rebase is already in progress, it will continue it.
If you encounter merge conflicts:
1. The tool will tell you which files have conflicts
2. Edit those files to resolve the conflicts (remove conflict markers, keep correct code)
3. Stage the resolved files with `git add`
4. Call the mcp__builtin_tools__rebase_task_branch tool again to continue

Keep using the tool until the rebase completes successfully."""

    BASE_BRANCH_CHANGES_PROMPT_TEMPLATE = """The task branch has been rebased onto the latest base branch.

{changes_summary}

Please briefly review these changes and note if any are relevant to the current task."""

    @classmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Available when: task has feature branch and status is PLANNING or IMPLEMENTING.
        """
        return task.status in (TaskStatus.PLANNING, TaskStatus.IMPLEMENTING)

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: rebase task branch onto base branch.

        For PLANNING: Direct service call, then agent reviews base branch changes.
        For IMPLEMENTING: Delegates to agent with rebase tool for conflict resolution.

        Yields:
            ConversationEvent objects from agent interaction or system events
        """
        if self.task.status == TaskStatus.PLANNING:
            async for event in self._run_direct_rebase():
                yield event
        else:
            # IMPLEMENTING: Use agent for potential conflict resolution
            async for event in self._run_agent_rebase():
                yield event

    async def _run_direct_rebase(self) -> AsyncIterator[ConversationEvent]:
        """Execute direct rebase for PLANNING states (no file changes expected)."""
        try:
            rebase_result = await self.task_git_service.rebase_task_branch(self.task)
        except Exception as e:
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={
                    "task_id": self.task.id,
                    "message": f"Rebase failed: {str(e)}",
                },
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return

        # Check for conflicts (shouldn't happen in PLANNING since no file changes)
        if rebase_result.outcome.value == "conflict":
            yield SystemEvent(
                event_type="system",
                type=SystemEventType.STREAM_ERROR,
                data={
                    "task_id": self.task.id,
                    "message": f"Rebase encountered conflicts. Conflicted files: {', '.join(rebase_result.conflicted_files or [])}",
                },
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            return

        # Emit success event
        yield SystemEvent(
            event_type="system",
            type=SystemEventType.BRANCH_REBASED,
            data={
                "task_id": self.task.id,
                "message": f"Rebased onto {self.task.base_branch}",
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # If base branch had changes, stream agent response to review them
        if rebase_result.base_branch_changes:
            prompt = self.BASE_BRANCH_CHANGES_PROMPT_TEMPLATE.format(
                changes_summary=rebase_result.base_branch_changes.format_summary(self.task.base_branch),
            )

            current_conversation = self.conversation_repo.get_active_conversation_for_entity(
                ParentEntityType.TASK, self.task.id
            )

            # Stream agent response - agent uses the rebase_task_branch tool
            async for event in self._stream_agent_response(current_conversation, prompt):
                yield event

    async def _run_agent_rebase(self) -> AsyncIterator[ConversationEvent]:
        """Execute agent-based rebase for IMPLEMENTING state (handles conflict resolution)."""
        # Get current active conversation
        current_conversation = self.conversation_repo.get_active_conversation_for_entity(
            ParentEntityType.TASK, self.task.id
        )

        # Stream agent response - agent uses the rebase_task_branch tool
        async for event in self._stream_agent_response(current_conversation, self.IMPLEMENTING_PROMPT):
            yield event

        # After agent completes, emit success event
        yield SystemEvent(
            event_type="system",
            type=SystemEventType.BRANCH_REBASED,
            data={
                "task_id": self.task.id,
                "message": f"Rebased onto {self.task.base_branch}",
            },
            timestamp=datetime.datetime.now(datetime.UTC),
        )


class ApproveAndMergeAction(TaskWorkflowAction):
    """Workflow action for solo/local development - approve changes and merge feature branch locally.

    This action prompts the agent to:
    1. Commit any uncommitted changes
    2. Complete the task using the complete_task_with_local_merge tool (includes change summary)

    The complete_task_with_local_merge tool creates the change summary document, merges the branch,
    and transitions the task to COMPLETE status.
    """

    KEY = "task.approve_and_merge"
    PROMPT_TEMPLATE = """Finalize this task for local merge.

## Current Branch State
{changes_context}

## Instructions
If there are uncommitted changes, create appropriate commit(s) with clear commit messages first.

Once all changes are committed, use the mcp__builtin_tools__complete_task_with_local_merge tool to merge the feature branch and complete the task. Include a change_summary with:
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
            task.status == TaskStatus.IMPLEMENTING and task.codebase.branch_handling == BranchHandling.LOCAL_MERGE.value
        )

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action: agent commits and calls merge tool.

        Yields:
            ConversationEvent objects from agent interaction
        """
        changes_context = await _get_task_changes_prompt_context(self.task_git_service, self.task)
        prompt = self.PROMPT_TEMPLATE.format(changes_context=changes_context)

        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, prompt):
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
    PROMPT_TEMPLATE = """Finalize and create a pull request for this task.

## Current Branch State
{changes_context}

## Instructions
If there are uncommitted changes, create appropriate commit(s) with clear commit messages first.

Once all changes are committed, use the mcp__builtin_tools__create_pull_request tool to create a GitHub PR.

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

        changes_context = await _get_task_changes_prompt_context(self.task_git_service, self.task)
        prompt = self.PROMPT_TEMPLATE.format(changes_context=changes_context)

        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, prompt):
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
    PROMPT_TEMPLATE = """Merge this PR and complete the task.

## Current Branch State
{changes_context}

## Instructions
If there are uncommitted changes, create appropriate commit(s) with clear commit messages and push them first.

Once all changes are committed and pushed, use the mcp__builtin_tools__merge_pr_and_complete_task tool to merge the PR and complete the task. Include a change_summary with:
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

        changes_context = await _get_task_changes_prompt_context(self.task_git_service, self.task)
        prompt = self.PROMPT_TEMPLATE.format(changes_context=changes_context)

        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        async for event in self._stream_agent_response(conversation, prompt):
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
