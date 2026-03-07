import json
from dataclasses import dataclass
from typing import Literal

from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines import AgentEngine
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles import AgentRoleType
from devboard.agents.roles.codebase_investigation import CodebaseInvestigationAgentRole
from devboard.db.models import Task
from devboard.db.models.codebase import Codebase

_active_investigation_sessions: set[str] = set()

CODEBASE_INVESTIGATION_PROMPT = """Investigate the codebase documentation and source code to answer the following user query.
Perform the minimum necessary analysis to quickly provide an answer that addresses the query scope and no more.
Your answer should be concise and to the point with no unnecessary preamble or superfluous details.
Query: {query}"""


@dataclass
class CodebaseInvestigationContext:
    codebase: Codebase
    working_dir: str  # Allows specifying worktree working dir for the codebase


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
        if session_id is not None:
            if session_id in _active_investigation_sessions:
                raise ModelRetry(
                    f"session_id '{session_id}' is already in use by a concurrent investigation. "
                    "Concurrent calls with the same session_id are not supported. "
                    "Either wait for the previous investigation to complete before making a follow-up call with this session_id, "
                    "or omit session_id to start independent parallel investigations."
                )
            _active_investigation_sessions.add(session_id)

        try:
            # Get the selected codebase
            codebase_config = codebase_map[codebase_name]
            working_dir = codebase_config.working_dir
            # Get investigation agent configuration
            config = agent_config_service.get_effective_config(AgentRoleType.INVESTIGATION)

            # Create investigation role with selected codebase
            investigation_role = CodebaseInvestigationAgentRole(
                codebase=codebase_config.codebase, worktree_dir=working_dir
            )

            # Create and run investigation agent
            if config.engine == AgentEngine.INTERNAL:
                # Lazy import to avoid circular dependency
                from devboard.agents.engines.internal.agent import InternalAgent

                # NOTE: Session resumption is not supported for InternalAgent. To support it, one would
                # need to store and return `investigation_agent.conversation_history` (a `list[ModelMessage]`)
                # keyed by an investigation ID (e.g. in-memory cache with TTL, or a `Conversation` DB
                # record via `AgentExecutionService`), and pass it back on subsequent calls.
                if config.model is None:
                    raise ValueError(
                        f"Error: Could not find language model '{config.model_id}' for internal investigation agent"
                    )
                investigation_agent = InternalAgent(
                    role=investigation_role,
                    model=config.model,
                )
            elif config.engine == AgentEngine.CLAUDE_CODE:
                # Lazy import to avoid circular dependency
                from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent

                investigation_agent = ClaudeCodeAgent(
                    role=investigation_role,
                    model=config.model,
                    working_dir=working_dir,
                    session_id=session_id,
                )
            else:
                raise ValueError(f"Error: Unsupported engine '{config.engine}' for investigation agent")

            # Execute investigation
            prompt = CODEBASE_INVESTIGATION_PROMPT.format(query=query)
            events = await investigation_agent.run(prompt)

            # Extract final text response from events
            # Look for the last agent message
            final_response = events[-1]
            if not (isinstance(final_response, TextMessage) and final_response.role == MessageRole.AGENT):
                raise ValueError(
                    f"Expected final response from investigation agent to be TextMessage, but got {final_response}"
                )

            # Extract session_id for ClaudeCodeAgent (populated during streaming from SystemMessage)
            result_session_id: str | None = None
            if config.engine == AgentEngine.CLAUDE_CODE:
                result_session_id = investigation_agent.session_id  # type: ignore[union-attr]

            return json.dumps({"result": final_response.text_content, "session_id": result_session_id})
        finally:
            if session_id is not None:
                _active_investigation_sessions.discard(session_id)

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
