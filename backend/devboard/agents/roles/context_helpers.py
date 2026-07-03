"""Helper functions for building task context content.

Provides a standardized build_task_context() function that task-related
agent roles use to build their context content consistently.
"""

import logfire

from devboard.db.models import Project, Task


def _format_project_context(project: Project, *, header: str, include_specification: bool) -> str:
    """Format a project (or initiative) block: id, name, description, and optionally its document.

    The document heading reflects the entity kind — "Initiative Context" for an initiative,
    "Project Specification" for a top-level project — so the two concepts stay distinct to the agent.
    The ID is included so agents can reference the correct entity.
    """
    lines = [f"# {header}", f"ID: {project.id}", f"Name: {project.name}", f"Description: {project.description}"]
    section = "\n".join(lines)
    if include_specification:
        doc_title = "Initiative Context" if project.is_initiative else "Project Specification"
        section += "\n\n" + _format_document_section(f"## {doc_title}", project.specification.content)
    return section


def _extract_first_paragraph(content: str | None) -> str:
    """Extract first substantive (non-heading) paragraph from document content."""
    if not content:
        return ""
    for para in content.split("\n\n"):
        stripped = para.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _format_initiative_summary(initiative: Project) -> str:
    """Format a brief initiative spec overview (first paragraph only) for implementation agents."""
    spec_content = initiative.specification.content if initiative.specification else None
    overview = _extract_first_paragraph(spec_content)
    if not overview:
        return ""
    return f"## Initiative Overview\n{overview}"


def _format_task_metadata(task: Task) -> str:
    """Format task name and status metadata."""
    lines = [
        "# Task",
        f"ID: {task.id}",
        f"Name: {task.title}",
        f"Status: {task.status.value}",
    ]
    if task.github_pr_number:
        lines.append(f"PR: #{task.github_pr_number}")
    return "\n".join(lines)


def _format_codebase_info(task: Task, working_dir: str) -> str:
    """Format codebase information block."""
    info = f"""# Codebase
- Name: {task.codebase.name}
- Repository URL: {task.codebase.repository_url or "N/A"}
- Worktree directory: {working_dir}
- Description: {task.codebase.description or "N/A"}"""
    if task.codebase.developer_context:
        info += f"\n\n## Developer Context\n{task.codebase.developer_context}"
    return info


def _format_document_section(title: str, content: str | None) -> str:
    """Format a document section with XML-style document tags."""
    return f"""{title}
<document>\n
{content or "<EMPTY>"}\n
</document>"""


def _format_task_specification(task: Task) -> str:
    """Format task specification document section."""
    return _format_document_section("## Task Specification", task.specification.content)


def _format_implementation_plan(task: Task) -> str:
    """Format implementation plan document section."""
    content = task.implementation_plan.content if task.implementation_plan else None
    return _format_document_section("## Implementation Plan", content)


def _format_implementation_plan_structured(
    task: Task,
    *,
    include_step_outcomes: bool = False,
    include_step_status: bool = True,
) -> str:
    """Format structured implementation plan with steps summary.

    Args:
        task: Task with structured implementation plan
        include_step_outcomes: If True, include full step outcomes for completed steps.
            If False (default), outcomes are omitted entirely.
        include_step_status: If True (default), include step status in brackets.
            If False, omit status from the step summary line.
    """
    plan = task.implementation_plan_structured
    if not plan:
        return "## Implementation Plan\n<No structured plan>"

    lines = ["## Implementation Plan"]

    if plan.overview:
        lines.append(f"\nOverview: {plan.overview}")

    lines.append("\nSteps:")
    for step in plan.steps:
        deps = f" (depends on: {', '.join(str(d) for d in step.dependencies)})" if step.dependencies else ""
        status_part = f"[{step.status}] " if include_step_status else ""
        lines.append(f"\n{step.step_number}. {status_part}{step.title} [{step.type}]{deps}")
        if include_step_outcomes and step.outcome:
            quoted = "\n".join(f"> {line}" for line in step.outcome.splitlines())
            lines.append(f"\n   Outcome:\n{quoted}")

    return "\n".join(lines)


def build_execution_graph_context(task: Task, *, include_step_status: bool = True) -> str:
    """Build execution graph context showing step ordering and parallelism.

    Args:
        task: Task with structured implementation plan
        include_step_status: If True (default), include step status in brackets.
            If False, omit status from the execution graph entries.
    """
    plan = task.implementation_plan_structured
    if not plan or not plan.steps:
        return ""

    lines = ["EXECUTION GRAPH:"]

    # Compute topological layers for parallel execution groups
    steps_by_number = {s.step_number: s for s in plan.steps}
    remaining = set(steps_by_number.keys())
    layers: list[list[int]] = []

    while remaining:
        resolved = {n for layer in layers for n in layer}
        ready = [n for n in remaining if all(d in resolved for d in (steps_by_number[n].dependencies or []))]
        if not ready:
            logfire.warn(
                "Execution graph has unresolvable dependencies, falling back to sorted order", remaining=remaining
            )
            ready = sorted(remaining)
        layers.append(sorted(ready))
        remaining -= set(ready)

    for i, layer in enumerate(layers, start=1):
        step_summaries: list[str] = []
        for n in layer:
            step = steps_by_number[n]
            status_part = f" [{step.status}]" if include_step_status else ""
            step_summaries.append(f"Step {n}: {step.title}{status_part}")
        parallel_note = " (can run in parallel)" if len(layer) > 1 else ""
        lines.append(f"  Layer {i}{parallel_note}:")
        for summary in step_summaries:
            lines.append(f"    - {summary}")

    return "\n".join(lines)


def _format_custom_fields(task: Task) -> str:
    """Format task custom fields as key-value pairs."""
    if not task.custom_fields:
        return ""

    lines = ["## Custom Fields"]
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
    working_dir: str,
    global_context: str | None = None,
    include_project_specification: bool = True,
    include_step_outcomes: bool = False,
    include_implementation_plan: bool = True,
    include_step_status: bool = True,
) -> str:
    """Build standardized task context for agent roles.

    Args:
        task: Task instance with eager-loaded relationships
        working_dir: Working directory path for the task's codebase
        global_context: Optional workspace-level global context to prepend
        include_project_specification: Whether to include the full project specification document
        include_step_outcomes: Whether to include full step outcomes in the structured plan
        include_implementation_plan: Whether to include the implementation plan section
        include_step_status: Whether to include step status in the structured plan summary

    Returns:
        Formatted context string with consistent structure.
        PR number and implementation plan are automatically included if present.
    """
    sections = []

    if global_context:
        sections.append(f"# Global Context\n<document>\n{global_context}\n</document>")

    sections.append("You are working on a task associated with a project and a codebase repository.")

    project = task.project
    if project.parent is not None:
        sections.append(
            _format_project_context(
                project.parent, header="Parent Project", include_specification=include_project_specification
            )
        )
        sections.append(
            _format_project_context(project, header="Initiative", include_specification=include_project_specification)
        )
    else:
        sections.append(
            _format_project_context(project, header="Project", include_specification=include_project_specification)
        )

    if task.custom_fields:
        sections.append(_format_custom_fields(task))

    if not include_project_specification and project.parent is not None:
        summary = _format_initiative_summary(project)
        if summary:
            sections.append(summary)

    sections.append(_format_codebase_info(task, working_dir))
    sections.append(_format_task_metadata(task))
    sections.append(_format_task_specification(task))

    # Prefer structured plan, fall back to Document plan
    if include_implementation_plan:
        if task.implementation_plan_structured:
            sections.append(
                _format_implementation_plan_structured(
                    task,
                    include_step_outcomes=include_step_outcomes,
                    include_step_status=include_step_status,
                )
            )
        elif task.implementation_plan:
            sections.append(_format_implementation_plan(task))

    if task.change_summary:
        sections.append(_format_document_section("## Change Summary", task.change_summary.content))

    return "\n\n---\n\n".join(sections)
