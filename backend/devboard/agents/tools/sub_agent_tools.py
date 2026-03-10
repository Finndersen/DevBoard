import json
from dataclasses import dataclass
from typing import Literal

from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines import AgentEngine
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.agents.roles.code_review import CodeReviewAgentRole
from devboard.agents.roles.codebase_investigation import CodebaseInvestigationAgentRole
from devboard.db.models import Task
from devboard.db.models.codebase import Codebase
from devboard.services.task_git.diff_service import TaskDiffService

_active_sub_agent_sessions: set[str] = set()
# Backwards-compatibility alias used by existing tests
_active_investigation_sessions = _active_sub_agent_sessions

CODEBASE_INVESTIGATION_PROMPT = """Investigate the codebase documentation and source code to answer the following user query.
Perform the minimum necessary analysis to quickly provide an answer that addresses the query scope and no more.
Your answer should be concise and to the point with no unnecessary preamble or superfluous details.
Query: {query}"""


@dataclass
class SubAgentResult:
    """Result of a sub-agent execution."""

    result: str
    session_id: str | None


@dataclass
class CodebaseInvestigationContext:
    codebase: Codebase
    working_dir: str  # Allows specifying worktree working dir for the codebase


async def run_sub_agent(
    role: AgentRole,
    role_type: AgentRoleType,
    prompt: str,
    agent_config_service: AgentConfigService,
    working_dir: str,
    session_id: str | None = None,
) -> SubAgentResult:
    """Execute a sub-agent with the given role and prompt.

    Args:
        role: The agent role instance defining the sub-agent's behaviour
        role_type: Role type used for engine/model config resolution
        prompt: The prompt to send to the sub-agent
        agent_config_service: For resolving effective engine/model config
        working_dir: Workspace directory (used by ClaudeCodeAgent)
        session_id: Optional session ID for resuming a prior ClaudeCodeAgent session

    Returns:
        SubAgentResult with the final text response and optional session_id
    """
    if session_id is not None:
        if session_id in _active_sub_agent_sessions:
            raise ModelRetry(
                f"session_id '{session_id}' is already in use by a concurrent investigation. "
                "Concurrent calls with the same session_id are not supported. "
                "Either wait for the previous investigation to complete before making a follow-up call with this session_id, "
                "or omit session_id to start independent parallel investigations."
            )
        _active_sub_agent_sessions.add(session_id)

    try:
        config = agent_config_service.get_effective_config(role_type)

        if config.engine == AgentEngine.INTERNAL:
            # Lazy import to avoid circular dependency
            from devboard.agents.engines.internal.agent import InternalAgent

            if config.model is None:
                raise ValueError(
                    f"Error: Could not find language model '{config.model_id}' for internal {role_type} agent"
                )
            agent = InternalAgent(role=role, model=config.model)
        elif config.engine == AgentEngine.CLAUDE_CODE:
            # Lazy import to avoid circular dependency
            from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent

            agent = ClaudeCodeAgent(
                role=role,
                model=config.model,
                working_dir=working_dir,
                session_id=session_id,
            )
        else:
            raise ValueError(f"Error: Unsupported engine '{config.engine}' for {role_type} agent")

        events = await agent.run(prompt)

        final_response = events[-1]
        if not (isinstance(final_response, TextMessage) and final_response.role == MessageRole.AGENT):
            raise ValueError(
                f"Expected final response from {role_type} agent to be TextMessage, but got {final_response}"
            )

        result_session_id: str | None = None
        if config.engine == AgentEngine.CLAUDE_CODE:
            result_session_id = agent.session_id  # type: ignore[union-attr]

        return SubAgentResult(result=final_response.text_content, session_id=result_session_id)
    finally:
        if session_id is not None:
            _active_sub_agent_sessions.discard(session_id)


def create_multi_codebase_investigation_tool(
    codebases: list[CodebaseInvestigationContext],
    agent_config_service: AgentConfigService,
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

    Raises:
        ValueError: If codebases list is empty
    """
    if not codebases:
        raise ValueError("At least one codebase must be provided")

    # Create name -> codebase mapping for dispatch
    codebase_map: dict[str, CodebaseInvestigationContext] = {
        cb_config.codebase.name: cb_config for cb_config in codebases
    }

    async def investigate_codebase(codebase_name: str, query: str, session_id: str | None = None) -> str:
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
          **independent** investigations (each with no `session_id`, or with **different** `session_id` values).
        - **IMPORTANT**: Do NOT make concurrent calls with the same `session_id`. Concurrent calls sharing a `session_id`
          will fail. When continuing a previous investigation session, calls must be sequential — wait for the previous
          call to return before making a follow-up call with the same `session_id`.
        - Provide as much context as possible (e.g. reference specific file paths, class/function names) to help the investigation agent
          focus its analysis and provide more accurate and targeted answers.
        - Indicate specific directories or files to focus on if possible.

        Args:
            query: Specific question about the codebase. Be as detailed as possible about what you want to know.
            codebase_name: Name of the codebase to investigate. Choose from the available codebases.
            session_id: Optional session ID from a prior call to this tool. Provide it when continuing a previous
                investigation where the prior session already has relevant context, to resume rather than starting fresh.

        Returns:
            A JSON string with two keys:
            - `result`: The investigation answer with file paths, code references, and implementation details.
            - `session_id`: An opaque session identifier to pass back on follow-up calls, or null if unavailable.
        """
        codebase_config = codebase_map[codebase_name]
        working_dir = codebase_config.working_dir
        investigation_role = CodebaseInvestigationAgentRole(codebase=codebase_config.codebase, worktree_dir=working_dir)
        prompt = CODEBASE_INVESTIGATION_PROMPT.format(query=query)
        sub_agent_result = await run_sub_agent(
            role=investigation_role,
            role_type=AgentRoleType.INVESTIGATION,
            prompt=prompt,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
            session_id=session_id,
        )
        return json.dumps({"result": sub_agent_result.result, "session_id": sub_agent_result.session_id})

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

    return create_multi_codebase_investigation_tool(codebase_contexts, agent_config_service)


def create_code_review_tool(
    task: Task,
    agent_config_service: AgentConfigService,
    task_diff_service: TaskDiffService,
) -> Tool:
    """Create a code review tool that performs a self-review of all task changes.

    Args:
        task: The task being reviewed
        agent_config_service: AgentConfigService for getting configured LLM
        task_diff_service: Service for retrieving the full task diff
    """

    async def review_code_changes() -> str:
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

        Returns:
            A JSON string with:
            - `result`: Structured review with Summary and Findings (Critical/Important/Suggestions)
            - `session_id`: Always null (code review is single-shot)
        """
        working_dir = task.get_current_workspace_dir()
        diff = await task_diff_service.get_task_all_changes(task)

        if not diff.files:
            return json.dumps({"result": "No changes to review — the task diff is empty.", "session_id": None})

        full_diff_content = "\n".join(f"--- {file.file_path} ---\n{file.diff_content}" for file in diff.files)

        role = CodeReviewAgentRole(codebase=task.codebase, worktree_dir=working_dir)

        assert task.implementation_plan is not None, "Task must have an implementation plan for code review"

        prompt = f"""Please review the following task changes.

## Task Specification

```
{task.specification.content}
```

## Implementation Plan

```
{task.implementation_plan.content}
```

## Diff Summary

```
{diff.format_summary()}
```

## Full Unified Diff

```diff
{full_diff_content}
```
"""

        sub_agent_result = await run_sub_agent(
            role=role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt=prompt,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
        )
        return json.dumps({"result": sub_agent_result.result, "session_id": sub_agent_result.session_id})

    return Tool(function=review_code_changes, name="review_code_changes")
