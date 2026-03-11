"""Helper functions for building task context content.

Provides a standardized build_task_context() function that task-related
agent roles use to build their context content consistently.
"""

from devboard.db.models import Task


def _format_project_metadata(task: Task) -> str:
    """Format project name and description."""
    return f"PROJECT: {task.project.name}\nDESCRIPTION: {task.project.description}"


def _format_project_specification(task: Task) -> str:
    """Format project specification document section."""
    return _format_document_section("PROJECT SPECIFICATION", task.project.specification.content)


def _format_task_metadata(task: Task) -> str:
    """Format task name and status metadata."""
    lines = [
        "## TASK DETAILS",
        f"NAME: {task.title}",
        f"STATUS: {task.status.value}",
    ]
    if task.github_pr_number:
        lines.append(f"ASSOCIATED PULL REQUEST: #{task.github_pr_number}")
    return "\n".join(lines)


def _format_codebase_info(task: Task) -> str:
    """Format codebase information block."""
    return f"""RELEVANT CODEBASE:
- Name: {task.codebase.name}
- Repository URL: {task.codebase.repository_url or "N/A"}
- Worktree directory: {task.get_current_workspace_dir()}
- Description: {task.codebase.description or "N/A"}"""


def _format_document_section(title: str, content: str | None) -> str:
    """Format a document section with markdown code block."""
    return f"""{title}:
```markdown
{content or "<EMPTY>"}
```"""


def _format_task_specification(task: Task) -> str:
    """Format task specification document section."""
    return _format_document_section("TASK SPECIFICATION", task.specification.content)


def _format_implementation_plan(task: Task) -> str:
    """Format implementation plan document section."""
    content = task.implementation_plan.content if task.implementation_plan else None
    return _format_document_section("IMPLEMENTATION PLAN", content)


def _format_custom_fields(task: Task) -> str:
    """Format task custom fields as key-value pairs."""
    if not task.custom_fields:
        return ""

    lines = ["TASK CUSTOM FIELDS:"]
    for field_name, value in task.custom_fields.items():
        # Format boolean values as Yes/No for readability
        if isinstance(value, bool):
            display_value = "Yes" if value else "No"
        else:
            display_value = str(value)
        lines.append(f"- {field_name}: {display_value}")

    return "\n".join(lines)


def build_task_context(
    task: Task,
    *,
    include_project_specification: bool = True,
    pr_status_content: str = "",
) -> str:
    """Build standardized task context for agent roles.

    Args:
        task: Task instance with eager-loaded relationships
        include_project_specification: Whether to include the full project specification document
        pr_status_content: Formatted PR status string (for PR review role)

    Returns:
        Formatted context string with consistent structure.
        PR number and implementation plan are automatically included if present.
    """
    sections = [_format_task_metadata(task)]
    sections.append(_format_project_metadata(task))

    if include_project_specification:
        sections.append(_format_project_specification(task))

    if pr_status_content:
        sections.append(f"PR STATUS:\n{pr_status_content}")

    sections.append(_format_task_specification(task))

    if task.implementation_plan:
        sections.append(_format_implementation_plan(task))

    if task.custom_fields:
        sections.append(_format_custom_fields(task))

    sections.append(_format_codebase_info(task))

    return "\n\n".join(sections)
