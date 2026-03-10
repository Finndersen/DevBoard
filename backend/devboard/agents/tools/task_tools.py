"""Tools for querying and creating tasks within a project."""

import json
from datetime import datetime
from typing import Any, Literal

import toons
from pydantic_ai import ModelRetry, Tool

from devboard.db.models import Codebase, CustomFieldDefinition, CustomFieldType, Project, Task, TaskStatus
from devboard.services.task_service import TaskService

MAX_TASKS_LIMIT = 20


def _task_to_toon_record(task: Task) -> dict[str, Any]:
    """Convert a Task to a dict for TOON encoding."""
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "codebase": task.codebase.name,
        "branch": task.branch_name,
        "custom_fields": json.dumps(task.custom_fields or {}),
    }


def _format_tasks_as_toon(tasks: list[Task], total_count: int) -> str:
    """Format tasks as TOON-encoded output string."""
    if not tasks:
        return "No tasks found matching the filters."

    task_records = [_task_to_toon_record(task) for task in tasks]
    toon_output = toons.dumps(task_records)

    if total_count > len(tasks):
        return f"Showing {len(tasks)} of {total_count} tasks (limit reached):\n{toon_output}"

    return toon_output


def create_list_tasks_tool(project: Project, task_service: TaskService) -> Tool:
    """Create a tool for listing tasks belonging to the project.

    Args:
        project: The project to list tasks for
        task_service: Service for task operations
    """
    # Build codebase name mapping for Literal type hint
    codebase_names = tuple(cb.name for cb in project.codebases) if project.codebases else ()

    async def list_tasks(
        status_filter: list[str] | None = None,
        created_after_date: str | None = None,
        created_before_date: str | None = None,
        codebase_name: str | None = None,
    ) -> str:
        """List tasks belonging to this project with optional filtering.

        Use this tool to get an overview of tasks in the project, filtered by various criteria.

        Args:
            status_filter: Filter by one or more status values.
                Valid values: 'planning', 'implementing', 'pr_open', 'complete'
            created_after_date: Filter tasks created on or after this date (format: 'YYYY-MM-DD')
            created_before_date: Filter tasks created before this date (format: 'YYYY-MM-DD')
            codebase_name: Filter by codebase name. Choose from the available codebases.

        Returns:
            TOON-encoded list of tasks with fields: id, title, status, created_at, codebase, branch, custom_fields.
            Returns a message if no tasks match the filters.
        """
        # Parse status filter
        parsed_statuses: list[TaskStatus] | None = None
        if status_filter:
            try:
                parsed_statuses = [TaskStatus(s.lower()) for s in status_filter]
            except ValueError as e:
                raise ModelRetry(
                    f"Invalid status value: {e}. Valid values: {', '.join(s.value for s in TaskStatus)}"
                ) from e

        # Parse date filters
        parsed_created_after: datetime | None = None
        parsed_created_before: datetime | None = None
        try:
            if created_after_date:
                parsed_created_after = datetime.strptime(created_after_date, "%Y-%m-%d")
            if created_before_date:
                parsed_created_before = datetime.strptime(created_before_date, "%Y-%m-%d")
        except ValueError as e:
            raise ModelRetry(f"Invalid date format: {e}. Use format 'YYYY-MM-DD' (e.g., '2024-01-15')") from e

        # Query tasks
        tasks = task_service.get_tasks_filtered(
            project_id=project.id,
            status_filter=parsed_statuses,
            created_after=parsed_created_after,
            created_before=parsed_created_before,
            codebase_name=codebase_name,
        )

        total_count = len(tasks)
        limited_tasks = tasks[:MAX_TASKS_LIMIT]

        return _format_tasks_as_toon(limited_tasks, total_count)

    # Dynamically set the Literal annotation for codebase_name parameter if codebases exist
    if codebase_names:
        list_tasks.__annotations__["codebase_name"] = Literal[codebase_names]

    return Tool(function=list_tasks, name="list_tasks")


def create_view_task_details_tool(project: Project, task_service: TaskService) -> Tool:
    """Create a tool for viewing detailed information about a specific task.

    Args:
        project: The project context (for security validation)
        task_service: Service for task operations
    """

    async def view_task_details(
        task_id: int,
        include_documents: list[str] | None = None,
    ) -> str:
        """View detailed information about a specific task.

        Use this tool to get full details about a task, including optionally its document contents.

        Args:
            task_id: The ID of the task to view
            include_documents: Optional list of document types to include.
                Valid values: 'specification', 'implementation_plan', 'change_summary'

        Returns:
            Formatted task details including metadata and requested document contents.
        """
        # Validate include_documents
        valid_doc_types = {"specification", "implementation_plan", "change_summary"}
        if include_documents:
            invalid_types = set(include_documents) - valid_doc_types
            if invalid_types:
                raise ModelRetry(f"Invalid document types: {invalid_types}. Valid types: {', '.join(valid_doc_types)}")

        # Fetch task with documents if needed
        task = task_service.get_task_by_id(task_id, with_documents=bool(include_documents))

        if not task:
            raise ModelRetry(f"Task with ID {task_id} not found.")

        # Security check: task must belong to this project
        if task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        # Format task metadata
        lines = [
            f"# Task #{task.id}: {task.title}\n",
            f"**Status:** {task.status.value}",
            f"**Created:** {task.created_at.isoformat()}",
            f"**Codebase:** {task.codebase.name}",
        ]

        lines.append(f"**Branch:** {task.branch_name}")
        lines.append(f"**Base Branch:** {task.base_branch}")
        if task.github_pr_number:
            lines.append(f"**GitHub PR:** #{task.github_pr_number}")
        if task.custom_fields:
            lines.append(f"**Custom Fields:** {task.custom_fields}")

        # Include requested documents
        if include_documents:
            lines.append("\n---\n")

            if "specification" in include_documents:
                spec_content = task.specification.content if task.specification else None
                lines.append("## Specification\n")
                lines.append(f"```markdown\n{spec_content or '<empty>'}\n```\n")

            if "implementation_plan" in include_documents:
                plan_content = task.implementation_plan.content if task.implementation_plan else None
                lines.append("## Implementation Plan\n")
                if plan_content:
                    lines.append(f"```markdown\n{plan_content}\n```\n")
                else:
                    lines.append("*No implementation plan created yet.*\n")

            if "change_summary" in include_documents:
                summary_content = task.change_summary.content if task.change_summary else None
                lines.append("## Change Summary\n")
                if summary_content:
                    lines.append(f"```markdown\n{summary_content}\n```\n")
                else:
                    lines.append("*No change summary created yet.*\n")

        return "\n".join(lines)

    return Tool(function=view_task_details, name="view_task_details")


def _build_codebase_name_schema(codebase_names: tuple[str, ...]) -> dict[str, Any]:
    """Build JSON schema for the codebase_name parameter."""
    schema: dict[str, Any] = {
        "type": "string",
        "description": "The name of the codebase for this task (required)",
    }
    if len(codebase_names) == 1:
        schema["const"] = codebase_names[0]
    elif len(codebase_names) > 1:
        schema["enum"] = list(codebase_names)
    return schema


def _build_custom_fields_schema(
    custom_field_definitions: list[CustomFieldDefinition],
) -> dict[str, Any] | None:
    """Build JSON schema for the custom_fields parameter based on field definitions.

    Returns None if no definitions exist (custom_fields will be omitted from schema).
    """
    if not custom_field_definitions:
        return None

    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_def in custom_field_definitions:
        field_schema: dict[str, Any] = {}

        if field_def.type == CustomFieldType.TEXT:
            field_schema["type"] = "string"
        elif field_def.type == CustomFieldType.BOOLEAN:
            field_schema["type"] = "boolean"
        elif field_def.type == CustomFieldType.ENUM:
            field_schema["type"] = "string"
            if field_def.options:
                field_schema["enum"] = field_def.options

        if field_def.description:
            field_schema["description"] = field_def.description

        properties[field_def.name] = field_schema

        if field_def.mandatory:
            required.append(field_def.name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required

    return schema


def _build_create_task_json_schema(
    codebase_names: tuple[str, ...],
    custom_field_definitions: list[CustomFieldDefinition],
) -> dict[str, Any]:
    """Build the full JSON schema for the create_task tool."""
    properties: dict[str, Any] = {
        "title": {
            "type": "string",
            "description": "The task title (required)",
        },
        "codebase_name": _build_codebase_name_schema(codebase_names),
        "specification_content": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Optional initial content for the task specification document",
            "default": None,
        },
        "base_branch": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Optional branch to base work off (defaults to codebase default branch)",
            "default": None,
        },
        "branch_name": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Optional working branch name (auto-generated from title if not provided)",
            "default": None,
        },
    }

    custom_fields_schema = _build_custom_fields_schema(custom_field_definitions)
    if custom_fields_schema:
        properties["custom_fields"] = {
            "anyOf": [custom_fields_schema, {"type": "null"}],
            "description": "Optional additional metadata as a dictionary",
            "default": None,
        }

    return {
        "type": "object",
        "properties": properties,
        "required": ["title", "codebase_name"],
        "additionalProperties": False,
    }


def _build_edit_custom_fields_schema(
    custom_field_definitions: list[CustomFieldDefinition],
) -> dict[str, Any] | None:
    """Build JSON schema for the custom_fields parameter in the edit tool (all nullable, none required).

    Returns None if no definitions exist.
    """
    if not custom_field_definitions:
        return None

    properties: dict[str, Any] = {}

    for field_def in custom_field_definitions:
        if field_def.type == CustomFieldType.TEXT:
            type_schema: dict[str, Any] = {"type": "string"}
        elif field_def.type == CustomFieldType.BOOLEAN:
            type_schema = {"type": "boolean"}
        elif field_def.type == CustomFieldType.ENUM:
            type_schema = {"type": "string"}
            if field_def.options:
                type_schema["enum"] = field_def.options
        else:
            type_schema = {"type": "string"}

        field_schema: dict[str, Any] = {"anyOf": [type_schema, {"type": "null"}]}

        if field_def.description:
            field_schema["description"] = field_def.description

        properties[field_def.name] = field_schema

    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def _build_edit_task_json_schema(
    custom_field_definitions: list[CustomFieldDefinition],
) -> dict[str, Any]:
    """Build the full JSON schema for the edit_task tool."""
    properties: dict[str, Any] = {
        "task_id": {
            "type": "integer",
            "description": "The ID of the task to edit",
        },
        "title": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "New title for the task (leave null to keep unchanged)",
            "default": None,
        },
    }

    edit_custom_fields_schema = _build_edit_custom_fields_schema(custom_field_definitions)
    if edit_custom_fields_schema:
        properties["custom_fields"] = {
            "anyOf": [edit_custom_fields_schema, {"type": "null"}],
            "description": "Custom field values to merge into the task. Set a key to null to remove it.",
            "default": None,
        }

    return {
        "type": "object",
        "properties": properties,
        "required": ["task_id"],
        "additionalProperties": False,
    }


def create_edit_task_tool(
    project: Project,
    task_service: TaskService,
) -> Tool:
    """Create a tool for editing task metadata within a project.

    Args:
        project: The project context (for security validation)
        task_service: Service for task operations
    """

    async def edit_task(
        task_id: int,
        title: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> str:
        """Edit metadata fields of an existing task within the current project."""
        if title is None and custom_fields is None:
            raise ModelRetry("No fields to update. Provide at least one of: title, custom_fields.")

        task = task_service.get_task_by_id(task_id)

        if not task:
            raise ModelRetry(f"Task with ID {task_id} not found.")

        if task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        try:
            updated_task = task_service.update_task(task, title=title, custom_fields=custom_fields)
            return json.dumps(
                {
                    "task_id": updated_task.id,
                    "title": updated_task.title,
                    "custom_fields": updated_task.custom_fields,
                }
            )
        except Exception as e:
            raise ModelRetry(f"Failed to update task: {e}") from e

    json_schema = _build_edit_task_json_schema(task_service.get_custom_fields())

    return Tool.from_schema(
        function=edit_task,
        name="edit_task",
        description="Edit metadata fields (title, custom fields) of an existing task within the current project.",
        json_schema=json_schema,
    )


def create_create_task_tool(
    project: Project,
    task_service: TaskService,
) -> Tool:
    """Create a tool for creating new tasks within a project.

    Args:
        project: The project to create tasks in
        task_service: Service for task creation
    """
    # Build codebase name -> Codebase mapping for lookup
    codebase_map: dict[str, Codebase] = {cb.name: cb for cb in project.codebases} if project.codebases else {}
    codebase_names = tuple(codebase_map.keys())

    async def create_task(
        title: str,
        codebase_name: str,
        specification_content: str | None = None,
        base_branch: str | None = None,
        branch_name: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> str:
        """Create a new task within the current project.

        Use this tool to create a new task for tracking work to be done.
        """
        # Look up codebase from the pre-built map
        codebase = codebase_map.get(codebase_name)
        if not codebase:
            available = ", ".join(codebase_map.keys())
            raise ModelRetry(f"Codebase '{codebase_name}' not found. Available codebases: {available}")

        resolved_base_branch = base_branch or codebase.default_branch

        try:
            task = task_service.create_task(
                project_id=project.id,
                title=title,
                base_branch=resolved_base_branch,
                codebase_id=codebase.id,
                specification_content=specification_content or "",
                branch_name=branch_name,
                custom_fields=custom_fields,
            )
            return json.dumps(
                {
                    "task_id": task.id,
                    "title": task.title,
                    "status": task.status.value,
                    "branch_name": task.branch_name,
                    "base_branch": task.base_branch,
                    "codebase_name": codebase.name,
                }
            )
        except Exception as e:
            raise ModelRetry(f"Failed to create task: {e}") from e

    json_schema = _build_create_task_json_schema(codebase_names, task_service.get_custom_fields())

    return Tool.from_schema(
        function=create_task,
        name="create_task",
        description="Create a new task within the current project. Use this tool to create a new task for tracking work to be done.",
        json_schema=json_schema,
    )
