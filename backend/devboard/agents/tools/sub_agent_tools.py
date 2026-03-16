import json
from dataclasses import dataclass
from typing import Literal

from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.agents.roles.code_review import CodeReviewAgentRole
from devboard.agents.roles.codebase_investigation import CodebaseInvestigationAgentRole
from devboard.db.models import Task
from devboard.db.models.codebase import Codebase
from devboard.db.models.conversation import ParentEntityType
from devboard.db.repositories import ConversationRepository
from devboard.services.task_git.service import TaskGitService

_active_sub_agent_conversations: set[int] = set()
# Backwards-compatibility alias used by existing tests
_active_investigation_sessions = _active_sub_agent_conversations
_active_sub_agent_sessions = _active_sub_agent_conversations

CODEBASE_INVESTIGATION_PROMPT = """Investigate the codebase documentation and source code to answer the following user query.
Perform the minimum necessary analysis to quickly provide an answer that addresses the query scope and no more.
Your answer should be concise and to the point with no unnecessary preamble or superfluous details.
Query: {query}"""


@dataclass
class SubAgentResult:
    """Result of a sub-agent execution."""

    result: str
    conversation_id: int


@dataclass
class CodebaseInvestigationContext:
    codebase: Codebase
    working_dir: str  # Allows specifying worktree working dir for the codebase


async def run_sub_agent(
    role: AgentRole,
    role_type: AgentRoleType,
    prompt: str,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_entity_type: ParentEntityType,
    parent_entity_id: int,
    parent_conversation_id: int | None = None,
    conversation_id: int | None = None,
) -> SubAgentResult:
    """Execute a sub-agent with the given role and prompt.

    Creates a Conversation record for the sub-agent and executes via AgentExecutionService,
    enabling engine-agnostic message persistence and session resumption.
    """
    if conversation_id is not None:
        # Resumption path: validate and guard against concurrent use
        if conversation_id in _active_sub_agent_conversations:
            raise ModelRetry(
                f"conversation_id '{conversation_id}' is already in use by a concurrent investigation. "
                "Concurrent calls with the same conversation_id are not supported. "
                "Either wait for the previous investigation to complete before making a follow-up call with this conversation_id, "
                "or omit conversation_id to start independent parallel investigations."
            )
        conversation = conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ModelRetry(
                f"conversation_id '{conversation_id}' not found. Start a new investigation by omitting conversation_id."
            )
        if conversation.parent_conversation_id != parent_conversation_id:
            raise ModelRetry(f"conversation_id '{conversation_id}' does not belong to this conversation context.")
        _active_sub_agent_conversations.add(conversation_id)
    else:
        # New conversation path
        config = agent_config_service.get_effective_config(role_type)
        conversation = conversation_repo.create(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=role_type,
            engine=config.engine,
            model_id=config.model_id,
            is_active=False,
            parent_conversation_id=parent_conversation_id,
        )
        # Commit eagerly so that ClaudeCodeAgentExecutionService session_id updates don't fail
        conversation_repo.commit()

    try:
        # Lazy import to avoid circular dependency:
        # sub_agent_tools → api.dependencies.factories → roles → sub_agent_tools
        from devboard.api.dependencies.factories import create_agent_execution_service

        execution_service = create_agent_execution_service(
            conversation=conversation,
            role=role,
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )

        events = await execution_service.send_message_or_approval(prompt)

        final_response = next(
            (e for e in reversed(events) if isinstance(e, TextMessage) and e.role == MessageRole.AGENT),
            None,
        )
        if final_response is None:
            raise ValueError(f"Expected a TextMessage response from {role_type} agent, but none was found in events")

        conversation_repo.commit()
        return SubAgentResult(result=final_response.text_content, conversation_id=conversation.id)
    finally:
        if conversation_id is not None:
            _active_sub_agent_conversations.discard(conversation_id)


def create_multi_codebase_investigation_tool(
    codebases: list[CodebaseInvestigationContext],
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
    parent_entity_type: ParentEntityType,
    parent_entity_id: int,
) -> Tool:
    """Create a codebase investigation tool that delegates investigation queries to a specialized agent.

    This tool allows parent agents to offload codebase investigation work to a specialized
    investigation sub-agent. When multiple codebases are available, the agent must specify
    which codebase to investigate. The sub-agent performs comprehensive analysis and returns
    a detailed answer, avoiding the need for the parent agent to perform multiple searches
    and file reads directly.

    The investigation tool is ideal for:
    - Understanding architectural patterns and system design
    - Finding implementation details for specific features or components
    - Learning how workflows or processes are implemented
    - Discovering code organization and structure
    - Getting comprehensive answers without multiple follow-up queries

    Args:
        codebases: List of CodebaseInvestigationContext instances. Must contain at least one codebase.
        agent_config_service: AgentConfigService for getting configured LLM
        conversation_repo: Repository for creating/loading conversation records
        parent_conversation_id: ID of the invoking agent's conversation
        parent_entity_type: Entity type for sub-conversation records
        parent_entity_id: Entity ID for sub-conversation records

    Raises:
        ValueError: If codebases list is empty
    """
    if not codebases:
        raise ValueError("At least one codebase must be provided")

    # Create name -> codebase mapping for dispatch
    codebase_map: dict[str, CodebaseInvestigationContext] = {
        cb_config.codebase.name: cb_config for cb_config in codebases
    }

    async def investigate_codebase(codebase_name: str, query: str, conversation_id: int | None = None) -> str:
        """Investigate a specific codebase to answer questions about implementation details, architecture, and code organization.

        Use this tool when you need detailed information about:
        - How specific features are implemented
        - Where certain functionality is located in the codebase
        - Architectural patterns and structure
        - Specific functions, classes, or modules
        - How workflows or processes work
        - Code organization and conventions

        ONLY use this tool for questions that likely involve multi-step and multi-file investigation.
        DO NOT use this tool to read or retrieve the content of a specific known file — use the `Read` tool directly instead.

        Guidelines:
        - Be specific about what you want to know and what level of detail is required.
        - Make your query targeted about one specific topic. You may call this tool multiple times in parallel for
          **independent** investigations (each with no `conversation_id`, or with **different** `conversation_id` values).
        - **IMPORTANT**: Do NOT make concurrent calls with the same `conversation_id`. Concurrent calls sharing a `conversation_id`
          will fail. When continuing a previous investigation session, calls must be sequential — wait for the previous
          call to return before making a follow-up call with this `conversation_id`.
        - Provide as much context as possible (e.g. reference specific file paths, class/function names) to help the investigation agent
          focus its analysis and provide more accurate and targeted answers.
        - Indicate specific directories or files to focus on if possible.

        Args:
            query: Specific question about the codebase. Be as detailed as possible about what you want to know.
            codebase_name: Name of the codebase to investigate. Choose from the available codebases.
            conversation_id: Optional conversation ID from a prior call to this tool. Provide it when continuing a previous
                investigation where the prior conversation already has relevant context, to resume rather than starting fresh.

        Returns:
            A JSON string with two keys:
            - `result`: The investigation answer with file paths, code references, and implementation details.
            - `conversation_id`: A conversation identifier to pass back on follow-up calls, or null if unavailable.
        """
        codebase_config = codebase_map[codebase_name]
        investigation_role = CodebaseInvestigationAgentRole(
            codebase=codebase_config.codebase, worktree_dir=codebase_config.working_dir
        )
        prompt = CODEBASE_INVESTIGATION_PROMPT.format(query=query)
        sub_agent_result = await run_sub_agent(
            role=investigation_role,
            role_type=AgentRoleType.INVESTIGATION,
            prompt=prompt,
            agent_config_service=agent_config_service,
            conversation_repo=conversation_repo,
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            parent_conversation_id=parent_conversation_id,
            conversation_id=conversation_id,
        )
        return json.dumps({"result": sub_agent_result.result, "conversation_id": sub_agent_result.conversation_id})

    # Dynamically set the Literal annotation for codebase_name parameter
    # This allows displaying the available codebase names as an enum to the LLM
    investigate_codebase.__annotations__["codebase_name"] = Literal[tuple(codebase_map.keys())]

    return Tool(
        function=investigate_codebase,
        name="investigate_codebase",
    )


def create_task_codebase_investigation_tool(
    task: Task,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
) -> Tool:
    """Create a codebase investigation tool for a task.

    Includes all codebases from the task's project:
    - Task's assigned codebase uses the task's worktree directory
    - Other project codebases use their main local_path
    """
    codebase_contexts: list[CodebaseInvestigationContext] = []

    # Task's own codebase uses worktree
    codebase_contexts.append(
        CodebaseInvestigationContext(
            codebase=task.codebase,
            working_dir=task.get_current_workspace_dir(),
        )
    )

    # Add other project codebases using their local_path
    for codebase in task.project.codebases:
        if codebase.id != task.codebase_id:
            codebase_contexts.append(
                CodebaseInvestigationContext(
                    codebase=codebase,
                    working_dir=codebase.local_path,
                )
            )

    return create_multi_codebase_investigation_tool(
        codebase_contexts,
        agent_config_service,
        conversation_repo=conversation_repo,
        parent_conversation_id=parent_conversation_id,
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=task.id,
    )


def create_code_review_tool(
    task: Task,
    agent_config_service: AgentConfigService,
    task_git_service: TaskGitService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
) -> Tool:
    """Create a code review tool that performs a self-review of all task changes.

    Args:
        task: The task being reviewed
        agent_config_service: AgentConfigService for getting configured LLM
        task_git_service: Service for retrieving the full task diff
        conversation_repo: Repository for creating conversation records
        parent_conversation_id: ID of the invoking agent's conversation
    """

    async def review_code_changes(context: str | None = None) -> str:
        """Perform a comprehensive code review of all changes made so far in this task.

        Use this tool after completing initial implementation to get a thorough review
        of all code changes before finalisation (e.g. before creating a PR or merging).

        The review agent will evaluate:
        - Alignment with the task specification and implementation plan
        - Code quality, patterns, and conventions
        - Architecture and design decisions
        - Test coverage adequacy
        - Potential issues, edge cases, and risks
        - Cross-component impact

        Args:
            context: Optional additional context for the reviewer. Use this to explain why changes
                diverge from the specification or implementation plan, describe known limitations,
                or highlight specific areas you want the reviewer to focus on.

        Returns:
            A JSON string with:
            - `result`: Structured review with Summary and Findings (Critical/Important/Suggestions)
            - `conversation_id`: The conversation identifier for the review session.
        """
        diff = await task_git_service.get_task_all_changes(task)

        if not diff.files:
            return json.dumps({"result": "No changes to review — the task diff is empty.", "conversation_id": None})

        full_diff_content = "\n".join(f"--- {file.file_path} ---\n{file.diff_content}" for file in diff.files)

        role = CodeReviewAgentRole(task=task)

        prompt = f"""Please review the following task changes. Calibrate the depth and thoroughness of your review to the complexity of the changes — small, trivial changes warrant a quick lightweight review, while large or complex changes warrant a thorough deep review.

## Diff Summary

```
{diff.format_summary()}
```

## Full Unified Diff

```diff
{full_diff_content}
```
"""

        if context is not None:
            prompt += f"""
## Additional Context from Implementation Agent

{context}
"""

        sub_agent_result = await run_sub_agent(
            role=role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt=prompt,
            agent_config_service=agent_config_service,
            conversation_repo=conversation_repo,
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            parent_conversation_id=parent_conversation_id,
        )
        return json.dumps({"result": sub_agent_result.result, "conversation_id": sub_agent_result.conversation_id})

    return Tool(function=review_code_changes, name="review_code_changes")
