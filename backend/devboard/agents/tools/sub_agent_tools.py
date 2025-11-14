from typing import Literal

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.engines.claude_code import ClaudeCodeAgent
from devboard.agents.engines.internal.agent import InternalAgent
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles.codebase_investigation import CodebaseInvestigationRole
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models.codebase import Codebase

CODEBASE_INVESTIGATION_PROMPT = """Investigate the codebase documentation and source code to answer the following user query.
Perform the minimum necessary analysis to quickly provide an answer that addresses the query scope and no more.
Your answer should be concise and to the point with no unnecessary preamble or superfluous details.
Query: {query}"""


def create_codebase_investigation_tool(
    codebases: list[Codebase],
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
        codebases: List of Codebase model instances. Must contain at least one codebase.
        agent_config_service: AgentConfigService for getting configured LLM

    Raises:
        ValueError: If codebases list is empty
    """
    if not codebases:
        raise ValueError("At least one codebase must be provided")

    # Create name -> codebase mapping for dispatch
    codebase_map: dict[str, Codebase] = {cb.name: cb for cb in codebases}

    async def investigate_codebase(codebase_name: str, query: str) -> str:
        """Investigate a specific codebase to answer questions about implementation details, architecture, and code organization.

        Use this tool when you need detailed information about:
        - How specific features are implemented
        - Where certain functionality is located in the codebase
        - Architectural patterns and structure
        - Specific functions, classes, or modules
        - How workflows or processes work
        - Code organization and conventions

        Be specific about what you want to know and what level of detail is required.

        Args:
            query: Specific question about the codebase. Be as detailed as possible about what you want to know.
            codebase_name: Name of the codebase to investigate. Choose from the available codebases.

        Returns:
            Comprehensive answer with file paths, code references, and implementation details.
        """
        # Get the selected codebase
        codebase = codebase_map[codebase_name]

        # TODO: Create more generic interface for constructing an Agent from a Role type
        # Get investigation agent configuration
        config = agent_config_service.get_effective_config(AgentRoleType.INVESTIGATION)

        # Get language model for investigation agent
        language_model = agent_config_service.llm_registry.get(config.model_id)
        if language_model is None:
            raise ValueError(f"Error: Could not find language model '{config.model_id}' for investigation agent")

        # Create investigation role with selected codebase (role is stateless and reusable)
        investigation_role = CodebaseInvestigationRole(codebase=codebase)

        # Create and run investigation agent
        if config.engine == AgentEngine.INTERNAL:
            investigation_agent = InternalAgent(
                role=investigation_role,
                model=language_model,
            )
        elif config.engine == AgentEngine.CLAUDE_CODE:
            investigation_agent = ClaudeCodeAgent(
                role=investigation_role,
                model=language_model,
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

        return final_response.text_content

    # Dynamically set the Literal annotation for codebase_name parameter
    # This allows displaying the available codebase names as an enum to the LLM
    investigate_codebase.__annotations__["codebase_name"] = Literal[tuple(codebase_map.keys())]

    return Tool(
        function=investigate_codebase,
        name="investigate_codebase",
    )
