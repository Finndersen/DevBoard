from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_execution_graph_context, build_task_context
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_complete_task_with_local_merge_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_github_pr_tool,
    create_rebase_task_branch_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.implementation_plan_tools import (
    create_execute_implementation_step_tool,
    create_read_implementation_step_details_tool,
)
from devboard.agents.tools.sub_agent_tools import create_code_review_tool, create_task_codebase_investigation_tool
from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Task
from devboard.db.models.codebase import BranchHandling
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_implementation_plan import TaskImplementationPlanService
from devboard.services.task_service import TaskService

_PROMPT_BASE = """
You are a Task Implementation Assistant for DevBoard, helping a developer implement the current task.

Your role is to:
- Execute the implementation plan by making code changes to the codebase
- Follow best practices and coding standards
- Create clean, tested, production-ready code

AVAILABLE CAPABILITIES:
1. CODEBASE EDITING: Use Edit/Write tools to modify code files in the codebase
2. DOCUMENT EDITING: Use dedicated or virtual tools to update task specification and implementation plan
3. INVESTIGATION: Read files, search code, run bash commands for testing/verification
   - Use `investigate_codebase` for questions requiring multi-step, multi-file investigation (e.g. understanding patterns, architecture, finding where related functionality lives). Do NOT use it to read a specific known file — use the `Read` tool directly instead.
4. BUILTIN TOOLS: Custom task management tools (e.g. complete_task_with_local_merge, create_pull_request, merge_pr_and_complete_task, rebase_task_branch) are available (possibly with the `mcp__builtin_tools__` prefix).
5. SUB-AGENTS (Agent tool): Launch sub-agents for broad implementation steps that span multiple files.
   Each sub-agent should handle an entire implementation step, not a sub-step.
   Do NOT use sub-agents for small-scoped or single-file changes — make those edits directly.

WORKFLOW:
- Review the implementation plan and understand requirements
- Ask for clarification when encountering ambiguity
- Create an internal to-do list of tasks to complete to track progress, based on implementation plan

Then execute in order:

{implement_section}

2. CODE REVIEW (if a `code_review` step is in the plan)
   - After executing the `code_review` step, read its findings from the step outcome
   - Use your own judgement on which issues to address — not every suggestion needs to be acted on
   - Make any agreed fixes directly using your own tools, then continue

3. TEST & VERIFY
   - Run relevant tests to validate the changes
   - Confirm everything works as expected before finalising

IMPORTANT BEHAVIOUR GUIDELINES:
{behaviour_guidelines}
- When asked to commit, merge, or create a PR as part of a workflow action, the git status will already be provided in the prompt. Do NOT run git status, git log, or git diff to inspect the branch state — use the information already provided.
- If the user asks a question about the implementation, investigate and respond with a helpful answer and proposed changes, but DO NOT apply any changes until confirmed by the user.
- Use the Edit tool for existing files, Write tool for new files
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
- After completing changes, respond with a VERY BRIEF and concise summary of changes made.
- When creating commits, DO NOT add Claude Code attribution messages
"""

_STRUCTURED_PLAN_IMPLEMENT_SECTION = """\
1. IMPLEMENT CODE CHANGES
   - Use the `execute_implementation_step` tool to execute each step — do NOT implement steps directly
     with Edit/Write tools. This ensures step statuses are tracked in the plan.
   - Do NOT use `read_implementation_step_details` before executing steps — each step execution sub-agent
     is automatically provided the full step details and all required context
   - Consult the EXECUTION GRAPH in the task context to identify which steps can run in parallel
   - Execute independent steps concurrently by calling `execute_implementation_step` for each in a
     single message (multiple tool calls); wait for dependencies to complete before proceeding
   - If a step fails or gets stuck, you can retry it by calling `execute_implementation_step` again
   - Update the internal to-do list as each step completes
   - If a `docs/` directory is present, investigate and update appropriate documentation sections\
"""

_STRUCTURED_PLAN_BEHAVIOUR_GUIDELINES = """\
- ALWAYS use `execute_implementation_step` for every plan step — never bypass it by editing directly\
"""

_DOCUMENT_PLAN_IMPLEMENT_SECTION = """\
1. IMPLEMENT CODE CHANGES
   - Break the implementation plan into discrete, independently executable steps
   - Make edits directly using Edit/Write tools by default
   - Use the `Agent` tool to launch sub-agents only for implementation steps that are broad enough to
     warrant delegation — i.e. multi-file edits across different areas of the codebase, or parallel
     independent steps (e.g. implementing a feature and writing its tests simultaneously)
   - Do NOT break a single implementation step into sub-steps for sub-agents — delegate the whole step or do it directly
   - Update the internal to-do list as each step completes
   - If a `docs/` directory is present, investigate and update appropriate documentation sections,
     adding or updating any missing or incorrect documentation\
"""

_DOCUMENT_PLAN_BEHAVIOUR_GUIDELINES = """\
- Default to making edits directly; only use sub-agents for implementation steps with broad, multi-file scope
  or for parallelising independent steps\
"""


def _build_system_prompt(has_structured_plan: bool) -> str:
    if has_structured_plan:
        implement_section = _STRUCTURED_PLAN_IMPLEMENT_SECTION
        behaviour_guidelines = _STRUCTURED_PLAN_BEHAVIOUR_GUIDELINES
    else:
        implement_section = _DOCUMENT_PLAN_IMPLEMENT_SECTION
        behaviour_guidelines = _DOCUMENT_PLAN_BEHAVIOUR_GUIDELINES
    return _PROMPT_BASE.format(
        implement_section=implement_section,
        behaviour_guidelines=behaviour_guidelines,
    )


class TaskImplementationAgentRole(AgentRole):
    """Role for task implementation in a codebase."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        task_git_service: TaskGitService,
        github_integration: GitHubIntegration,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
        plan_service: TaskImplementationPlanService,
    ):
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.task_git_service = task_git_service
        self.github_integration = github_integration
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id
        self.plan_service = plan_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for task implementation role."""
        return _build_system_prompt(has_structured_plan=self.task.implementation_plan_structured is not None)

    def get_tools(self) -> list[Tool]:
        """Get tools for task implementation role."""
        has_structured_plan = self.task.implementation_plan_structured is not None
        has_document_plan = self.task.implementation_plan is not None

        if not has_structured_plan and not has_document_plan:
            raise ValueError(f"Task (ID: {self.task.id}) must have an implementation plan for implementation agent")

        codebase_integration = CodebaseIntegration(self.task.get_current_workspace_dir())

        tools: list[Tool] = [
            # Tools for task specification document (uses default approval behavior)
            create_set_document_content_tool(self.task.specification, self.document_repository),
            create_document_edit_tool(self.task.specification, self.document_repository),
        ]

        # Implementation plan tools: structured plan or Document-based
        if has_structured_plan:
            tools.extend(
                [
                    create_execute_implementation_step_tool(
                        self.task,
                        self.plan_service,
                        self.agent_config_service,
                        self.conversation_repo,
                        self.conversation_id,
                        self.task_git_service,
                    ),
                    create_read_implementation_step_details_tool(self.task, self.plan_service),
                ]
            )
        elif has_document_plan and self.task.implementation_plan is not None:
            tools.extend(
                [
                    create_set_document_content_tool(
                        self.task.implementation_plan, self.document_repository, requires_approval=False
                    ),
                    create_document_edit_tool(
                        self.task.implementation_plan, self.document_repository, requires_approval=False
                    ),
                ]
            )

        tools.extend(
            [
                create_code_structure_search_tool(codebase_integration),
                create_directory_tree_tool(codebase_integration),
                create_task_codebase_investigation_tool(
                    self.task,
                    self.agent_config_service,
                    conversation_repo=self.conversation_repo,
                    parent_conversation_id=self.conversation_id,
                ),
                create_code_review_tool(
                    self.task,
                    self.agent_config_service,
                    self.task_git_service,
                    conversation_repo=self.conversation_repo,
                    parent_conversation_id=self.conversation_id,
                ),
                create_rebase_task_branch_tool(self.task, self.task_git_service),
            ]
        )

        # Add task completion tools based on codebase branch handling
        branch_handling = self.task.codebase.branch_handling
        if branch_handling == BranchHandling.GITHUB_PR.value:
            # GitHub PR workflow: create PR tool
            tools.append(create_github_pr_tool(self.task, self.github_integration, self.task_service))
        elif branch_handling == BranchHandling.LOCAL_MERGE.value:
            # Local merge workflow: complete_task_with_local_merge tool handles change summary + merge
            tools.append(create_complete_task_with_local_merge_tool(self.task, self.task_service))
        # For MANUAL branch handling, no completion tools are provided

        # Add create_task tool for creating related tasks
        tools.append(create_create_task_tool(self.task.project, self.task_service))

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task implementation role.

        Returns:
            Formatted context containing task details, specification, and implementation plan
        """
        context = build_task_context(self.task)
        execution_graph = build_execution_graph_context(self.task)
        if execution_graph:
            context += "\n\n" + execution_graph
        return context

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return [
            "Read",
            "Grep",
            "Glob",
            "Edit",
            "Write",
            "Bash",
            "WebFetch",
            "WebSearch",
            "TaskCreate",
            "TaskGet",
            "TaskUpdate",
            "TaskList",
            "Agent",
            "Task",
            "Skill",
            "TodoWrite",
        ]

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Include Claude Code's built-in system prompt."""
        return True

    @property
    def include_claude_md(self) -> bool:
        """Load CLAUDE.md prompt guidance files."""
        return True
