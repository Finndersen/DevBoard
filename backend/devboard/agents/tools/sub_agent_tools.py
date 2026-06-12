from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.types import SubAgentResult
from devboard.agents.language_models import RECOMMENDED_AGENT_MODEL_TYPES, ModelType
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.agents.roles.code_review import CodeReviewAgentRole
from devboard.agents.roles.codebase_investigation import CodebaseInvestigationAgentRole
from devboard.db.models import ParentEntity, Task
from devboard.db.models.codebase import Codebase
from devboard.db.models.conversation import Conversation
from devboard.db.repositories import ConversationRepository
from devboard.integrations.types import FileDiff, StructuredDiff
from devboard.services.task_git.service import TaskGitService

if TYPE_CHECKING:
    from devboard.agents.execution.manager import ConversationExecutionManager

CODEBASE_INVESTIGATION_PROMPT = """Investigate the codebase documentation and source code to answer the following user query.
Perform the minimum necessary analysis to quickly provide an answer that addresses the query scope and no more.
Your answer should be concise and to the point with no unnecessary preamble or superfluous details.
Query: {query}"""


@dataclass
class CodebaseInvestigationContext:
    codebase: Codebase
    working_dir: str  # Allows specifying worktree working dir for the codebase


def create_sub_agent_conversation(
    role_type: AgentRoleType,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_entity: ParentEntity,
    parent_conversation_id: int | None = None,
    model_type: ModelType | None = None,
) -> Conversation:
    """Create a new sub-agent conversation record and commit it eagerly.

    Returns the Conversation object so the caller has the conversation_id immediately,
    before execution begins.

    When model_type is provided, resolves the model for that type and the effective engine
    instead of using the role's default model.

    ## NOTE: This is very similar to ConversationService.create_initial_conversation_for_parent_entity() which is annoying, but
    agent_config_service and conversation_repo are also needed elsewhere where this is called, so couldnt just be replaced by ConversationService
    """
    config = agent_config_service.get_effective_config(role_type)
    if model_type is not None:
        model_id = agent_config_service.get_model_id_for_type(model_type, config.engine)
    elif config.model is not None:
        model_id = config.model.id
    else:
        recommended_type = RECOMMENDED_AGENT_MODEL_TYPES.get(role_type)
        model_id = (
            agent_config_service.get_model_id_for_type(recommended_type, config.engine) if recommended_type else None
        )
    conversation = conversation_repo.create(
        parent_entity_type=parent_entity.entity_type,
        parent_entity_id=parent_entity.id,
        agent_role=role_type,
        engine=config.engine,
        model_id=model_id,
        is_active=False,
        parent_conversation_id=parent_conversation_id,
    )
    # Commit eagerly so that ClaudeCodeAgentExecutionService session_id updates don't fail
    conversation_repo.commit()
    return conversation


async def run_sub_agent(
    role: AgentRole,
    role_type: AgentRoleType,
    prompt: str,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_entity: ParentEntity,
    working_dir: str,
    execution_manager: ConversationExecutionManager,
    parent_conversation_id: int | None = None,
    conversation_id: int | None = None,
    effort: Literal["low", "medium", "high"] | None = None,
) -> SubAgentResult:
    """Execute a sub-agent with the given role and prompt.

    Convenience wrapper that creates a new conversation or resumes an existing one,
    then executes the sub-agent via the execution manager.
    """
    if conversation_id is None:
        conversation = create_sub_agent_conversation(
            role_type=role_type,
            agent_config_service=agent_config_service,
            conversation_repo=conversation_repo,
            parent_entity=parent_entity,
            parent_conversation_id=parent_conversation_id,
        )
    else:
        conversation = conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ModelRetry(f"conversation_id '{conversation_id}' not found.")
        if conversation.parent_conversation_id != parent_conversation_id:
            raise ModelRetry(f"conversation_id '{conversation_id}' does not belong to this conversation context.")

    try:
        return await execution_manager.run_sub_agent_execution(
            conversation=conversation,
            role=role,
            prompt=prompt,
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
            effort=effort,
        )
    except ConversationBusyError as err:
        raise ModelRetry(
            f"conversation_id '{conversation.id}' is already in use. "
            "Wait for it to complete or omit conversation_id to start a new conversation."
        ) from err


def create_multi_codebase_investigation_tool(
    codebases: list[CodebaseInvestigationContext],
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_entity: ParentEntity,
    parent_conversation_id: int | None,
    execution_manager: ConversationExecutionManager,
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
        parent_entity: Parent entity (Task, Project, or Codebase) for sub-conversation records
        parent_conversation_id: ID of the invoking agent's conversation
        execution_manager: Manager for registering and running sub-agent executions

    Raises:
        ValueError: If codebases list is empty
    """
    if not codebases:
        raise ValueError("At least one codebase must be provided")

    # Create name -> codebase mapping for dispatch
    codebase_map: dict[str, CodebaseInvestigationContext] = {
        cb_config.codebase.name: cb_config for cb_config in codebases
    }

    async def investigate_codebase(
        codebase_name: str,
        query: str,
        conversation_id: int | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
    ) -> str:
        """Investigate a specific codebase to answer questions about implementation, architecture, patterns, and  functionality across multiple files.

        **ONLY use this tool for discovery questions that require searching across multiple files** — e.g. finding where
        functionality lives, understanding cross-cutting patterns, or tracing how data flows across components.

        **NEVER use this tool when you already know the file path** — read it directly with the `Read` tool instead.

        Use this tool for questions like:
        - Where is [functionality] implemented? Which files handle [feature]?
        - What patterns does this codebase use for [concern]?
        - How does [data/event] flow across the system?
        - Are there existing utilities or helpers for [task]?
        - What naming/structural conventions are used for [type of thing]?

        Guidelines:
        - Be specific about what you want to know and what level of detail is required.
        - Make your query targeted about one specific topic. You may call this tool multiple times in parallel for
          **independent** investigations (each with no `conversation_id`, or with **different** `conversation_id` values).
        - **IMPORTANT**: Do NOT make concurrent calls with the same `conversation_id`, this will fail.
        - Provide as much context as possible (e.g. reference specific file paths, class/function names) to help the investigation agent
          focus its analysis and provide more accurate and targeted answers.
        - Indicate specific directories or files to focus on if possible.

        Args:
            query: Specific question about the codebase. Be as detailed as possible about what you want to know.
            codebase_name: Name of the codebase to investigate. Choose from the available codebases.
            conversation_id: Optional conversation ID from a prior call to this tool. Provide it when continuing a previous
                investigation where the prior conversation already has relevant context, to resume rather than starting fresh.
            effort: Optional reasoning effort level for the investigation. Prefer lower effort levels — only escalate when the
                query genuinely requires it:
                - `low`: Discovery across a small number of files, locating where something is implemented.
                - `medium`: Questions requiring analysis across many files or discovery of cross-cutting patterns.
                - `high`: Complex architectural reasoning or understanding deep cross-component interactions. Reserve for the most
                  demanding investigations.
                - `None` (default): Uses the agent's configured default effort level

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
            parent_entity=parent_entity,
            working_dir=codebase_config.working_dir,
            execution_manager=execution_manager,
            parent_conversation_id=parent_conversation_id,
            conversation_id=conversation_id,
            effort=effort,
        )
        return json.dumps({"result": sub_agent_result.result, "conversation_id": sub_agent_result.conversation_id})

    # Dynamically set the Literal annotation for codebase_name parameter
    # This allows displaying the available codebase names as an enum to the LLM
    investigate_codebase.__annotations__["codebase_name"] = Literal[tuple(codebase_map.keys())]  # ty:ignore[invalid-type-form]

    return Tool(
        function=investigate_codebase,  # ty:ignore[invalid-argument-type]
        name="investigate_codebase",
    )  # ty:ignore[invalid-return-type]


def create_task_codebase_investigation_tool(
    task: Task,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
    working_dir: str,
    execution_manager: ConversationExecutionManager,
) -> Tool:
    """Create a codebase investigation tool for a task.

    Includes all codebases from the task's project:
    - Task's assigned codebase uses the provided working_dir (worktree or project dir)
    - Other project codebases use their main local_path
    """
    codebase_contexts: list[CodebaseInvestigationContext] = []

    # Task's own codebase uses the provided working_dir
    codebase_contexts.append(
        CodebaseInvestigationContext(
            codebase=task.codebase,
            working_dir=working_dir,
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
        parent_entity=task,
        parent_conversation_id=parent_conversation_id,
        execution_manager=execution_manager,
    )


def create_code_review_tool(
    task: Task,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
    working_dir: str,
    execution_manager: ConversationExecutionManager,
) -> Tool:
    """Create a code review tool that performs a self-review of all task changes.

    Args:
        task: The task being reviewed
        agent_config_service: AgentConfigService for getting configured LLM
        conversation_repo: Repository for creating conversation records
        parent_conversation_id: ID of the invoking agent's conversation
        execution_manager: Manager for registering and running sub-agent executions
    """

    async def review_code_changes(
        context: str | None = None, effort: Literal["low", "medium", "high"] | None = None
    ) -> str:
        """Perform a comprehensive code review of all changes made so far in this task.

        ONLY use this tool when explicitly asked to perform a code review. Do NOT use it proactively
        or as part of standard implementation workflow — code review plan steps are handled
        automatically via `execute_implementation_step`.

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
            effort: Optional reasoning effort level for the code review. Use to calibrate review depth based on change complexity:
                - `low`: Simple changes (few files, straightforward logic, minimal architectural impact)
                - `medium`: Moderate complexity (several files, some interdependencies, standard patterns)
                - `high`: Complex changes (many files, significant architectural decisions, cross-cutting concerns)
                - `None` (default): Uses the agent's configured default effort level

        Returns:
            A JSON string with:
            - `result`: Structured review with Summary and Findings (Critical/Important/Suggestions)
            - `conversation_id`: The conversation identifier for the review session.
        """
        diff = await TaskGitService.get_task_all_changes(task)

        if not diff.files:
            return json.dumps({"result": "No changes to review — the task diff is empty.", "conversation_id": None})

        role = CodeReviewAgentRole(task=task, working_dir=working_dir)
        prompt = build_code_review_prompt(diff, context)

        sub_agent_result = await run_sub_agent(
            role=role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt=prompt,
            agent_config_service=agent_config_service,
            conversation_repo=conversation_repo,
            parent_entity=task,
            working_dir=working_dir,
            execution_manager=execution_manager,
            parent_conversation_id=parent_conversation_id,
            effort=effort,
        )
        return json.dumps({"result": sub_agent_result.result, "conversation_id": sub_agent_result.conversation_id})

    return Tool(function=review_code_changes, name="review_code_changes")  # ty:ignore[invalid-argument-type, invalid-return-type]


# Files whose diff content is replaced with a stub — not useful to review line-by-line.
_EXCLUDED_DIFF_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(^|/)uv\.lock$"),
    re.compile(r"(^|/)poetry\.lock$"),
    re.compile(r"(^|/)Pipfile\.lock$"),
    re.compile(r"(^|/)package-lock\.json$"),
    re.compile(r"(^|/)yarn\.lock$"),
    re.compile(r"(^|/)pnpm-lock\.yaml$"),
    re.compile(r"(^|/)go\.sum$"),
    re.compile(r"(^|/)Cargo\.lock$"),
    re.compile(r"(^|/)Gemfile\.lock$"),
]

# Maximum characters to show per file before truncating (~10k chars ≈ 2.5k tokens).
_MAX_FILE_DIFF_CHARS = 10_000

# Maximum total diff characters across all files. When exceeded, newly created files
# are dropped from the diff (the agent can read them directly if needed).
# ~100k chars ≈ 25k tokens, leaving ample room for the rest of the prompt.
_MAX_TOTAL_DIFF_CHARS = 100_000


def _is_excluded_file(file_path: str) -> bool:
    return any(p.search(file_path) for p in _EXCLUDED_DIFF_PATTERNS)


def _strip_diff_header(diff_content: str) -> str:
    """Strip git diff header lines, returning only the hunks.

    Skips all lines before the first '@@' hunk marker or 'Binary files' line.
    If content already starts with @@, content is already stripped.
    Returns empty string if no @@ hunks or Binary files line found (pure rename, mode-only change).
    """
    if not diff_content:
        return ""

    lines = diff_content.split("\n")

    # If first line starts with @@, content is already stripped
    if lines and lines[0].startswith("@@"):
        return diff_content

    # Find first @@ hunk marker or Binary files line
    for i, line in enumerate(lines):
        if line.startswith("@@") or line.startswith("Binary files"):
            return "\n".join(lines[i:])

    # No hunks found (covers: pure rename, mode-only change)
    return ""


def _format_file_diff(file_path: str, diff_content: str, additions: int, deletions: int) -> str:
    """Format one file's diff with per-file truncation applied."""
    header = f"--- {file_path} ---"

    # Strip git diff header lines, keeping only hunks
    body = _strip_diff_header(diff_content)

    # If no hunks (pure rename, mode-only change — but not binary), use placeholder
    if not body:
        return f"{header}\n[no content changes]"

    if len(body) <= _MAX_FILE_DIFF_CHARS:
        return f"{header}\n{body}"
    truncated = body[:_MAX_FILE_DIFF_CHARS]
    omitted_chars = len(body) - _MAX_FILE_DIFF_CHARS
    return f"{header}\n{truncated}\n[... {omitted_chars:,} characters truncated (+{additions}/-{deletions} total)]"


def build_code_review_prompt(diff: StructuredDiff, additional_context: str | None = None) -> str:
    """Build the prompt for a code review sub-agent.

    Context (project spec, task spec, implementation plan) is provided by the code review agent role
    via build_task_context(), so the prompt only contains the diff and optional context.

    Args:
        diff: The structured diff to review
        additional_context: Optional additional context or instructions for the reviewer
    """
    # Separate files into three buckets:
    # 1. Always-excluded (lock/generated files) → stub only
    # 2. New files → include diff if budget allows, otherwise stub with read hint
    # 3. Modified files → always include diff (with per-file truncation)
    excluded_stubs: list[str] = []
    new_file_sections: list[tuple[FileDiff, str]] = []  # (file, formatted_diff)
    modified_sections: list[str] = []

    for file in diff.files:
        header = f"--- {file.file_path} ---"
        if _is_excluded_file(file.file_path):
            excluded_stubs.append(
                f"{header}\n[Diff excluded: lock/generated file — +{file.additions}/-{file.deletions} lines]"
            )
        elif file.is_deleted:
            excluded_stubs.append(f"{header}\n[File deleted]")
        elif file.is_new_file:
            formatted = _format_file_diff(file.file_path, file.diff_content, file.additions, file.deletions)
            new_file_sections.append((file, formatted))
        else:
            modified_sections.append(
                _format_file_diff(file.file_path, file.diff_content, file.additions, file.deletions)
            )

    # Check whether new files fit within the global budget.
    modified_char_count = sum(len(s) for s in modified_sections)
    new_file_char_count = sum(len(fmt) for _, fmt in new_file_sections)
    budget_remaining = _MAX_TOTAL_DIFF_CHARS - modified_char_count

    if new_file_char_count <= budget_remaining:
        # Everything fits — include new files in full.
        all_sections = modified_sections + [fmt for _, fmt in new_file_sections] + excluded_stubs
        new_file_note = ""
    else:
        # Budget exceeded — drop new file diffs and tell the agent where to find them.
        dropped_paths = [f.file_path for f, _ in new_file_sections]
        dropped_list = "\n".join(f"  - {p}" for p in dropped_paths)
        new_file_note = (
            "\n\n> **Note:** The following newly created files were omitted from the diff to keep the prompt size "
            "manageable. Read them directly if needed:\n" + dropped_list
        )
        all_sections = modified_sections + excluded_stubs

    full_diff_content = "\n\n".join(all_sections)

    prompt = f"""**Read-only review:** produce written findings only. Do NOT edit files, run git, or otherwise modify the codebase — even to fix issues you identify. Report them instead.

Please review the following task changes. Calibrate the depth and thoroughness of your review to the complexity of the changes — small, trivial changes warrant a quick lightweight review, while large or complex changes warrant a thorough deep review.

## Diff Summary

```
{diff.format_summary()}
```

## Full Unified Diff

```diff
{full_diff_content}
```{new_file_note}
"""

    if additional_context is not None:
        prompt += f"""
## Additional Context

{additional_context}
"""

    return prompt
