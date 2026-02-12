"""MCP (Model Context Protocol) server implementation.

This module provides an MCP server that can be accessed over HTTP,
allowing AI clients to interact with DevBoard through the MCP protocol.
"""

from typing import Any, TypedDict

from fastmcp import FastMCP

from devboard.agents.tools.sub_agent_tools import (
    CodebaseInvestigationContext,
    create_multi_codebase_investigation_tool,
)
from devboard.db.repositories import CodebaseRepository, ProjectRepository, TaskRepository
from devboard.mcp.dependencies import create_agent_config_service, get_mcp_db_session

# Initialize MCP server
mcp = FastMCP("DevBoard MCP Server")


# ============================================================================
# Return Type Structures
# ============================================================================


class ProjectInfo(TypedDict):
    """Project information structure."""

    id: int
    name: str
    description: str
    created_at: str


class TaskInfo(TypedDict):
    """Task information structure."""

    id: int
    title: str
    status: str
    project_id: int
    codebase_id: int | None
    created_at: str


class CodebaseInfo(TypedDict):
    """Codebase information structure."""

    name: str
    description: str | None
    local_path: str


# ============================================================================
# Tool Implementations
# ============================================================================


@mcp.tool
async def get_projects() -> list[ProjectInfo]:
    """Get a list of all projects in DevBoard.

    Returns:
        List of projects with their details.
        Each project includes: id, name, description, created_at.
    """
    with get_mcp_db_session() as db:
        projects = ProjectRepository(db).get_all()

        return [
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at.isoformat(),
            }
            for project in projects
        ]


@mcp.tool
async def get_codebases() -> list[CodebaseInfo]:
    """Get a list of all codebases in DevBoard.

    This is useful for discovering available codebases before using investigate_codebase.

    Returns:
        List of codebases with their details.
        Each codebase includes: name, description, local_path.
    """
    with get_mcp_db_session() as db:
        codebases = CodebaseRepository(db).get_all()

        return [
            {
                "name": codebase.name,
                "description": codebase.description,
                "local_path": codebase.local_path,
            }
            for codebase in codebases
        ]


@mcp.tool
async def get_tasks(project_id: int) -> list[TaskInfo]:
    """Get a list of tasks for a specific project.

    Args:
        project_id: Project ID to get tasks for.

    Returns:
        List of tasks with their details.
        Each task includes: id, title, status, project_id, codebase_id,
        created_at.
    """
    with get_mcp_db_session() as db:
        tasks = TaskRepository(db).get_for_project(project_id)

        return [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status.value,
                "project_id": task.project_id,
                "codebase_id": task.codebase_id,
                "created_at": task.created_at.isoformat(),
            }
            for task in tasks
        ]


@mcp.tool
async def investigate_codebase(codebase_name: str, query: str) -> str:
    """Investigate a codebase to answer questions about implementation details, architecture, and code organization.

    This tool uses a specialized investigation agent to analyze the codebase and provide
    comprehensive answers with file paths, code references, and implementation details.

    Use this tool when you need detailed information about:
    - How specific features are implemented
    - Where certain functionality is located in the codebase
    - Architectural patterns and structure
    - Specific functions, classes, or modules
    - How workflows or processes work
    - Code organization and conventions

    Be specific about what you want to know and what level of detail is required.

    Note: Use get_codebases() to discover available codebase names if you don't know them.

    Examples:
    - investigate_codebase("DevBoard", "How is the agent system architecture organized?")
    - investigate_codebase("DevBoard", "Where is TaskPlanningRole implemented and what does it do?")
    - investigate_codebase("DevBoard", "What are the main database models and their relationships?")

    Args:
        codebase_name: The name of the codebase to investigate. Call get_codebases() to see available options.
        query: Specific question about the codebase. Be as detailed as possible
               about what you want to know.

    Returns:
        Comprehensive answer with file paths, code references, and implementation details.
    """
    try:
        with get_mcp_db_session() as db:
            # Get the codebase by name
            codebase = CodebaseRepository(db).get_by_name(codebase_name)

            if codebase is None:
                return f"Error: Codebase '{codebase_name}' not found"

            # Get agent config service
            agent_config_service = create_agent_config_service(db)

            # Create and use the investigation tool
            codebase_context = CodebaseInvestigationContext(
                codebase=codebase,
                working_dir=codebase.local_path,
            )
            investigation_tool = create_multi_codebase_investigation_tool(
                [codebase_context],
                agent_config_service,
            )

            # Run the investigation (with codebase name since it's now required)
            result = await investigation_tool.function(codebase_name=codebase.name, query=query)
            return result

    except Exception as e:
        return f"Error: Failed to investigate codebase: {str(e)}"


# ============================================================================
# TODO: Additional tools to be implemented
# ============================================================================


@mcp.tool
async def create_task(
    title: str,
    description: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Create a new task in DevBoard.

    Args:
        title: The task title.
        description: The task description.
        project_id: Optional project ID to associate the task with.

    Returns:
        A dictionary containing the created task details.
    """
    # TODO: Implement actual database operation to create task
    return {
        "success": False,
        "message": "Task creation endpoint - to be implemented with database access",
        "task": {
            "title": title,
            "description": description,
            "project_id": project_id,
        },
    }


@mcp.tool
async def get_codebase_info(codebase_id: str) -> dict[str, Any]:
    """Get information about a codebase.

    Args:
        codebase_id: The ID of the codebase to retrieve.

    Returns:
        A dictionary containing codebase information.
    """
    # TODO: Implement actual database query to fetch codebase info
    return {
        "codebase_id": codebase_id,
        "message": "Codebase info endpoint - to be implemented with database access",
    }


# ============================================================================
# Resources Scaffolding - Add your MCP resources below
# ============================================================================


@mcp.resource("devboard://project/{project_id}")
async def get_project_resource(project_id: str) -> str:
    """Get a project as an MCP resource.

    Args:
        project_id: The ID of the project to retrieve.

    Returns:
        A string representation of the project.
    """
    # TODO: Implement actual database query to fetch project details
    return f"Project {project_id} - to be implemented with database access"


@mcp.resource("devboard://task/{task_id}")
async def get_task_resource(task_id: str) -> str:
    """Get a task as an MCP resource.

    Args:
        task_id: The ID of the task to retrieve.

    Returns:
        A string representation of the task.
    """
    # TODO: Implement actual database query to fetch task details
    return f"Task {task_id} - to be implemented with database access"


# ============================================================================
# Prompts Scaffolding - Add your MCP prompts below
# ============================================================================


@mcp.prompt()
async def project_overview_prompt(project_id: str) -> str:
    """Generate a prompt for getting a project overview.

    Args:
        project_id: The ID of the project.

    Returns:
        A formatted prompt for AI assistants.
    """
    return f"""Please provide an overview of project {project_id} including:
- Project description and goals
- Current tasks and their status
- Associated codebases
- Recent activity

Note: This prompt template can be customized based on actual project data."""


@mcp.prompt()
async def task_planning_prompt(task_description: str) -> str:
    """Generate a prompt for planning a new task.

    Args:
        task_description: Description of the task to plan.

    Returns:
        A formatted prompt for AI assistants.
    """
    return f"""Please help plan the following task:

{task_description}

Consider:
1. Breaking down the task into smaller subtasks
2. Identifying dependencies
3. Estimating complexity
4. Suggesting implementation approach
"""
