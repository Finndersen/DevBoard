"""Tools for querying and creating tasks within a project."""

import json
from datetime import datetime
from typing import Any, Literal

import toons
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.language_models import ModelType
from devboard.agents.roles import AgentRoleType
from devboard.db.models import (
    Codebase,
    CustomFieldDefinition,
    CustomFieldType,
    ParentEntityType,
    Project,
    Task,
    TaskStatus,
)
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.services.task_service import TaskService

MAX_TASKS_LIMIT = 20


def _task_to_toon_record(task: Task, agent_running: bool = False) -> dict[str, Any]:
    """Convert a Task to a dict for TOON encoding.

    `parent_project_id` is null for tasks under a top-level project and set to the parent
    project's id when the task's project is an initiative.
    """
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status.value,
        "created_at": task.created_at.isoformat(),
        "project_id": task.project_id,
        "parent_project_id": task.project.parent_project_id,
        "codebase": task.codebase.name,
        "branch": task.branch_name,
        "agent_running": agent_running,
        "custom_fields": json.dumps(task.custom_fields or {}),
    }


def _format_tasks_as_toon(tasks: list[Task], limit: int, running_map: dict[int, bool] | None = None) -> str:
    """Format tasks as TOON-encoded output string."""
    if not tasks:
        return "No tasks found matching the filters."

    task_records = [_task_to_toon_record(task, (running_map or {}).get(task.id, False)) for task in tasks]
    toon_output = toons.dumps(task_records)

    if len(tasks) == limit:
        return f"{toon_output}\n\nNote: {limit} results returned (the limit). There may be additional tasks not shown — use filters or increase max_results to see more."

    return toon_output


def create_list_tasks_tool(
    project: Project | None,
    task_service: TaskService,
    codebase_repo: CodebaseRepository | None = None,
) -> Tool:
    """Create a tool for listing tasks with optional filtering.

    Args:
        project: The project to scope tasks to, or None for global (all projects) access.
        task_service: Service for task operations.
        codebase_repo: Required when project is None, used to fetch all codebase names.
    """
    if project is not None:
        codebase_names = tuple(cb.name for cb in project.codebases) if project.codebases else ()
        default_project_id: int | None = project.id
    else:
        all_codebases = codebase_repo.get_all() if codebase_repo is not None else []
        codebase_names = tuple(cb.name for cb in all_codebases)
        default_project_id = None

    async def list_tasks(
        project_id: int | None = default_project_id,
        status_filter: list[str] | None = None,
        created_after_date: str | None = None,
        created_before_date: str | None = None,
        codebase_name: str | None = None,
        max_results: int = MAX_TASKS_LIMIT,
    ) -> str:
        """List tasks with optional filtering.

        Use this tool to get an overview of tasks, filtered by various criteria.
        Results are ordered by most recently updated first.

        Args:
            project_id: Filter by project ID. Defaults to the current project when scoped to one.
                Pass None to see tasks across all projects.
            status_filter: Filter by one or more status values.
                Valid values: 'planning', 'implementing', 'pr_open', 'complete'
            created_after_date: Filter tasks created on or after this date (format: 'YYYY-MM-DD')
            created_before_date: Filter tasks created before this date (format: 'YYYY-MM-DD')
            codebase_name: Filter by codebase name. Choose from the available codebases.
            max_results: Maximum number of tasks to return (default: 20).

        Returns:
            TOON-encoded list of tasks with fields: id, title, status, created_at, project_id,
            parent_project_id (set when the task's project is an initiative), codebase, branch,
            agent_running, custom_fields. Returns a message if no tasks match the filters.
        """
        parsed_statuses: list[TaskStatus] | None = None
        if status_filter:
            try:
                parsed_statuses = [TaskStatus(s.lower()) for s in status_filter]
            except ValueError as e:
                raise ModelRetry(
                    f"Invalid status value: {e}. Valid values: {', '.join(s.value for s in TaskStatus)}"
                ) from e

        parsed_created_after: datetime | None = None
        parsed_created_before: datetime | None = None
        try:
            if created_after_date:
                parsed_created_after = datetime.strptime(created_after_date, "%Y-%m-%d")
            if created_before_date:
                parsed_created_before = datetime.strptime(created_before_date, "%Y-%m-%d")
        except ValueError as e:
            raise ModelRetry(f"Invalid date format: {e}. Use format 'YYYY-MM-DD' (e.g., '2024-01-15')") from e

        tasks = task_service.get_tasks_filtered(
            project_id=project_id,
            status_filter=parsed_statuses,
            created_after=parsed_created_after,
            created_before=parsed_created_before,
            codebase_name=codebase_name,
            limit=max_results,
        )
        running_map = task_service.is_agents_running_for_tasks([t.id for t in tasks])
        return _format_tasks_as_toon(tasks, max_results, running_map)

    # Dynamically set the Literal annotation for codebase_name parameter if codebases exist
    if codebase_names:
        list_tasks.__annotations__["codebase_name"] = Literal[codebase_names]  # ty:ignore[invalid-type-form]

    return Tool(function=list_tasks, name="list_tasks")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_view_task_details_tool(
    project: Project | None,
    task_service: TaskService,
    conversation_repo: ConversationRepository | None = None,
) -> Tool:
    """Create a tool for viewing detailed information about a specific task.

    Args:
        project: The project context for security validation, or None for global (unrestricted) access.
        task_service: Service for task operations.
        conversation_repo: Optional repository for accessing conversation data.
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

        # Security check: task must belong to the scoped project (skipped for global access)
        if project is not None and task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        agent_running = task_service.is_task_agent_running(task.id)

        # Format task metadata
        lines = [
            f"# Task #{task.id}: {task.title}\n",
            f"**Status:** {task.status.value}",
            f"**Agent running:** {'yes' if agent_running else 'no'}",
            f"**Created:** {task.created_at.isoformat()}",
        ]

        # Project / initiative hierarchy — kept as distinct concepts even though both are Projects.
        task_project = task.project
        if task_project.is_initiative:
            lines.append(f"**Initiative:** {task_project.name} (#{task_project.id})")
            lines.append(f"**Project:** {task_project.parent_project_name} (#{task_project.parent_project_id})")
        else:
            lines.append(f"**Project:** {task_project.name} (#{task_project.id})")

        lines.append(f"**Codebase:** {task.codebase.name}")

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

        # Add Conversations section if conversation_repo is available
        if conversation_repo is not None:
            conversations = conversation_repo.get_active_conversations_for_entity(ParentEntityType.TASK, task.id)
            if conversations:
                lines.append("\n---\n")
                lines.append("## Conversations\n")
                for conv in conversations:
                    running = get_execution_manager().has_active_execution(conv.id)
                    last_activity = conv.last_activity_at.isoformat() if conv.last_activity_at else "N/A"
                    running_status = "running" if running else "inactive"
                    lines.append(
                        f"- **[{conv.id}]** {conv.agent_role.value} ({running_status}) — last activity: {last_activity}"
                    )

        return "\n".join(lines)

    return Tool(function=view_task_details, name="view_task_details")  # ty:ignore[invalid-argument-type, invalid-return-type]


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
    default_model_type: ModelType | None = None,
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
            "description": "Optional initial content for the task specification document. Should include: goal (what and why), relevant background/current state, functional requirements and constraints. May include critical implementation details essential to the task's outcome (e.g. specific data models, API contracts). Should NOT include routine implementation steps. Keep concise and scannable — use bullet points, tables, and diagrams where possible.",
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
        "model_type": {
            "enum": ["fast", "standard", "advanced"],
            "description": (
                "Agent model type for task planning conversation. "
                "fast: trivial/mechanical changes only (e.g. typo fixes, simple config). "
                "standard: moderate complexity (multi-file changes, feature additions). "
                "advanced: complex/architectural changes requiring deep reasoning."
            ),
            "default": default_model_type.value if default_model_type else "advanced",
        },
        "initial_prompt": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": (
                "Optional prompt sent to the task's planning agent conversation immediately after creation, "
                "launching autonomous agent execution. Use this to kick off any workflow: "
                "provide just a prompt to let the agent investigate and write the spec; "
                "provide both specification_content and a prompt like 'The spec is complete. Create the implementation plan.' "
                "to immediately begin planning; or omit to create the task for manual interaction later."
            ),
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
                type_schema["enum"] = field_def.options  # ty:ignore[invalid-assignment]
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
    include_task_id: bool = True,
) -> dict[str, Any]:
    """Build the full JSON schema for the edit_task tool."""
    properties: dict[str, Any] = {}

    if include_task_id:
        properties["task_id"] = {
            "type": "integer",
            "description": "The ID of the task to edit",
        }

    properties["title"] = {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "description": "New title for the task (leave null to keep unchanged)",
        "default": None,
    }

    edit_custom_fields_schema = _build_edit_custom_fields_schema(custom_field_definitions)
    if edit_custom_fields_schema:
        properties["custom_fields"] = {
            "anyOf": [edit_custom_fields_schema, {"type": "null"}],
            "description": "Custom field values to merge into the task. Set a key to null to remove it.",
            "default": None,
        }

    properties["specification_content"] = {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "description": "Full content to set for the task specification document. Should include: goal (what and why), relevant background/current state, functional requirements and constraints. May include critical implementation details essential to the task's outcome (e.g. specific data models, API contracts). Should NOT include routine implementation steps. Keep concise and scannable — use bullet points, tables, and diagrams where possible. Leave null to keep unchanged.",
        "default": None,
    }

    return {
        "type": "object",
        "properties": properties,
        "required": ["task_id"] if include_task_id else [],
        "additionalProperties": False,
    }


async def _apply_task_edits(
    task: Task,
    task_service: TaskService,
    document_repository: DocumentRepository,
    title: str | None = None,
    custom_fields: dict[str, Any] | None = None,
    specification_content: str | None = None,
    *,
    include_agent_running: bool = True,
) -> str:
    """Apply edits to a task and return a JSON result.

    Args:
        task: The task to edit
        task_service: Service for task operations
        document_repository: Repository for document operations
        title: New title (leave None to keep unchanged)
        custom_fields: Custom field values to merge (leave None to keep unchanged)
        specification_content: New specification content (leave None to keep unchanged)

    Returns:
        JSON string with updated task fields
    """
    if title is None and custom_fields is None and specification_content is None:
        raise ModelRetry("No fields to update. Provide at least one of: title, custom_fields, specification_content.")
    if specification_content is not None and not specification_content.strip():
        raise ModelRetry("specification_content cannot be empty or whitespace.")

    try:
        updated_task = task
        if title is not None or custom_fields is not None:
            updated_task = task_service.update_task(task, title=title, custom_fields=custom_fields)

        spec_updated = False
        if specification_content is not None:
            document_repository.update_content(task.specification, specification_content)
            document_repository.commit()
            spec_updated = True

        result: dict[str, Any] = {
            "task_id": updated_task.id,
            "title": updated_task.title,
            "custom_fields": updated_task.custom_fields,
        }
        if spec_updated:
            result["specification_updated"] = True
        if include_agent_running:
            result["agent_running"] = task_service.is_task_agent_running(updated_task.id)

        return json.dumps(result)
    except ModelRetry:
        raise
    except Exception as e:
        raise ModelRetry(f"Failed to update task: {e}") from e


def create_edit_task_tool(
    project: Project,
    task_service: TaskService,
    document_repository: DocumentRepository,
) -> Tool:
    """Create a tool for editing task metadata and specification within a project.

    Args:
        project: The project context (for security validation)
        task_service: Service for task operations
        document_repository: Repository for document operations
    """

    async def edit_task(
        task_id: int,
        title: str | None = None,
        custom_fields: dict[str, Any] | None = None,
        specification_content: str | None = None,
    ) -> str:
        """Edit metadata fields and/or specification content of an existing task within the current project."""
        if title is None and custom_fields is None and specification_content is None:
            raise ModelRetry(
                "No fields to update. Provide at least one of: title, custom_fields, specification_content."
            )

        task = task_service.get_task_by_id(task_id, with_documents=bool(specification_content))

        if not task:
            raise ModelRetry(f"Task with ID {task_id} not found.")

        if task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        return await _apply_task_edits(
            task=task,
            task_service=task_service,
            document_repository=document_repository,
            title=title,
            custom_fields=custom_fields,
            specification_content=specification_content,
        )

    json_schema = _build_edit_task_json_schema(task_service.get_custom_fields(), include_task_id=True)

    return Tool.from_schema(
        function=edit_task,
        name="edit_task",
        description="Edit metadata fields (title, custom fields) and/or specification content of an existing task within the current project.",
        json_schema=json_schema,
    )


def create_edit_own_task_tool(
    task: Task,
    task_service: TaskService,
    document_repository: DocumentRepository,
) -> Tool:
    """Create a tool for editing the current task's metadata and specification.

    The task is pre-bound at creation time, so no task_id parameter is exposed.

    Args:
        task: The pre-bound task to edit
        task_service: Service for task operations
        document_repository: Repository for document operations
    """

    async def edit_task(
        title: str | None = None,
        custom_fields: dict[str, Any] | None = None,
        specification_content: str | None = None,
    ) -> str:
        """Edit metadata fields and/or specification content of the current task."""
        return await _apply_task_edits(
            task=task,
            task_service=task_service,
            document_repository=document_repository,
            title=title,
            custom_fields=custom_fields,
            specification_content=specification_content,
        )

    json_schema = _build_edit_task_json_schema(task_service.get_custom_fields(), include_task_id=False)

    return Tool.from_schema(
        function=edit_task,
        name="edit_task",
        description="Edit metadata fields (title, custom fields) and/or specification content of the current task. Use specification_content to set or replace the full task specification — works whether or not the specification has been set before.",
        json_schema=json_schema,
    )


def create_create_task_tool(
    project: Project,
    task_service: TaskService,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository | None = None,
) -> Tool:
    """Create a tool for creating new tasks within a project.

    Args:
        project: The project to create tasks in
        task_service: Service for task creation
        agent_config_service: Service for agent configuration
        conversation_repo: Optional repository for conversation access (required for initial_prompt)
    """
    # Build codebase name -> Codebase mapping for lookup
    codebase_map: dict[str, Codebase] = {cb.name: cb for cb in project.codebases} if project.codebases else {}
    codebase_names = tuple(codebase_map.keys())

    # Resolve dynamic default model_type from TASK_PLANNING role config
    config = agent_config_service.get_effective_config(AgentRoleType.TASK_PLANNING)
    default_model_type = config.model.model_type if config.model else ModelType.ADVANCED

    async def create_task(
        title: str,
        codebase_name: str,
        specification_content: str | None = None,
        base_branch: str | None = None,
        branch_name: str | None = None,
        model_type: str = default_model_type.value,
        custom_fields: dict[str, Any] | None = None,
        initial_prompt: str | None = None,
    ) -> str:
        """Create a new task within the current project.

        Use this tool to create a new task for tracking work to be done.
        Optionally provide initial_prompt to immediately launch agent execution on the task's planning conversation.
        """
        # Fail fast: validate initial_prompt requirements before creating task
        if initial_prompt is not None and conversation_repo is None:
            raise ModelRetry("initial_prompt is not supported in this context")

        # Look up codebase from the pre-built map
        codebase = codebase_map.get(codebase_name)
        if not codebase:
            available = ", ".join(codebase_map.keys())
            raise ModelRetry(f"Codebase '{codebase_name}' not found. Available codebases: {available}")

        resolved_base_branch = base_branch or codebase.default_branch

        # Resolve model_type to model_id
        try:
            model_type_enum = ModelType(model_type)
            engine = config.engine
            model_id_override = agent_config_service.get_model_id_for_type(model_type_enum, engine)
        except ValueError as e:
            raise ModelRetry(f"Invalid model_type: {e}") from e

        try:
            task = await task_service.create_task(
                project_id=project.id,
                title=title,
                base_branch=resolved_base_branch,
                codebase_id=codebase.id,
                specification_content=specification_content or "",
                branch_name=branch_name,
                custom_fields=custom_fields,
                model_id_override=model_id_override,
            )
        except Exception as e:
            raise ModelRetry(f"Failed to create task: {e}") from e

        active_conversation_id = None

        if initial_prompt is not None:
            assert conversation_repo is not None  # Already validated above
            try:
                conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task.id)
                # Commit before starting background execution so the new DB session
                # opened by the execution manager can see the task and conversation.
                conversation_repo.commit()
                get_execution_manager().start_agent_execution(conversation.id, initial_prompt)
                active_conversation_id = conversation.id
            except Exception as e:
                raise ModelRetry(f"Failed to start agent execution: {e}") from e

        result: dict[str, Any] = {
            "task_id": task.id,
            "title": task.title,
            "status": task.status.value,
            "branch_name": task.branch_name,
            "base_branch": task.base_branch,
            "codebase_name": codebase.name,
            "agent_running": active_conversation_id is not None,
        }
        if active_conversation_id is not None:
            result["active_conversation_id"] = active_conversation_id
        return json.dumps(result)

    json_schema = _build_create_task_json_schema(codebase_names, task_service.get_custom_fields(), default_model_type)

    return Tool.from_schema(
        function=create_task,
        name="create_task",
        description=(
            "Create a new task within the current project. "
            "Patterns: (1) provide specification_content + initial_prompt (e.g. 'The spec is complete. Create the implementation plan.') "
            "to create with spec and immediately begin planning; "
            "(2) provide specification_content only — task created with spec for manual review; "
            "(3) provide initial_prompt only with a task description — the planning agent will investigate, write the spec, and handle the workflow; "
            "(4) provide just title + codebase_name — minimal task shell for later manual work."
        ),
        json_schema=json_schema,
    )
