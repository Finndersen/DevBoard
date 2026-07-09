"""Tools for querying and editing projects."""

import json

from pydantic_ai import ModelRetry, Tool

from devboard.api.schemas import DocumentEdit
from devboard.db.models import Project
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.document_editor import DocumentEditorService
from devboard.services.project_service import ProjectService
from devboard.services.task_service import TaskService


def create_list_projects_tool(project_repo: ProjectRepository) -> Tool:
    """Create a tool for listing all top-level projects (excludes initiatives)."""

    def list_projects() -> str:
        """List all top-level projects (not initiatives).

        Returns:
            JSON list of entries with id, name, description, and codebase names.
            To list child initiatives of a project, use `list_project_initiatives`.
        """
        projects = project_repo.get_all(root_only=True)
        return json.dumps(
            [
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "codebases": [cb.name for cb in (project.codebases or [])],
                }
                for project in projects
            ]
        )

    return Tool(function=list_projects, name="list_projects")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_list_project_initiatives_tool(project: Project, project_repo: ProjectRepository) -> Tool:
    """Create a tool for listing child initiatives of the agent's own project."""

    def list_project_initiatives() -> str:
        """List all child initiatives of this project.

        Returns:
            JSON list of entries with id, name, description, and status for each initiative.
        """
        initiatives = project_repo.get_all(parent_project_id=project.id)
        return json.dumps(
            [
                {
                    "id": initiative.id,
                    "name": initiative.name,
                    "description": initiative.description,
                    "status": "complete" if initiative.complete else "active",
                }
                for initiative in initiatives
            ]
        )

    return Tool(function=list_project_initiatives, name="list_project_initiatives")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_view_project_details_tool(
    project_repo: ProjectRepository,
    task_service: TaskService,
) -> Tool:
    """Create a tool for viewing full details of a specific project."""

    def view_project_details(project_id: int) -> str:
        """View full details of a project or initiative, including its document and task summary.

        Args:
            project_id: The ID of the project or initiative to view.

        Returns:
            JSON with metadata, `type` ('project' or 'initiative'), parent project (for
            initiatives), child initiatives (for top-level projects), document content, linked
            codebase names, and task summary.
        """
        project = project_repo.get_by_id(project_id)
        if not project:
            raise ModelRetry(f"Project with ID {project_id} not found.")

        active_tasks, recent_completed = task_service.get_project_task_summaries(project_id)

        parent_project = {"id": project.parent.id, "name": project.parent.name} if project.parent is not None else None
        initiatives = [{"id": i.id, "name": i.name} for i in project.initiatives]

        return json.dumps(
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "type": "initiative" if project.is_initiative else "project",
                "parent_project": parent_project,
                "initiatives": initiatives,
                "codebases": [cb.name for cb in (project.codebases or [])],
                "specification_content": project.specification.content if project.specification else None,
                "active_tasks": [{"id": t.id, "title": t.title, "status": t.status.value} for t in active_tasks],
                "recent_completed_tasks": [
                    {"id": t.id, "title": t.title, "status": t.status.value} for t in recent_completed
                ],
            }
        )

    return Tool(function=view_project_details, name="view_project_details")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_edit_project_specification_tool(
    project_repo: ProjectRepository,
    document_repo: DocumentRepository,
) -> Tool:
    """Create a tool for applying targeted find-replace edits to a project's specification."""

    def edit_project_specification(
        project_id: int,
        edits: list[DocumentEdit],
        reasoning: str = "",
    ) -> str:
        """Apply targeted find-replace edits to a project or initiative's specification document.

        Use this tool only to make incremental changes to content that already exists.
        To set or replace the full specification content, use `set_project_specification_content`.

        DOCUMENT EDITING RULES:
        1. Make precise find-replace edits using DocumentEdit objects
        2. Use exact text matches for 'find' - the text must exist exactly as written
        3. Use the MINIMUM necessary text to uniquely identify the location to replace
        4. Preserve markdown formatting and structure

        Args:
            project_id: The ID of the project or initiative whose specification to edit.
            edits: List of find-replace edits to apply.
            reasoning: Optional CONCISE reasoning for why these edits are being made.
        """
        project = project_repo.get_by_id(project_id)
        if not project:
            raise ModelRetry(f"Project with ID {project_id} not found.")

        spec = project.specification
        if not spec or not spec.content:
            raise ModelRetry(
                f"Project '{project.name}' (ID {project_id}) has no specification content yet. "
                "Set the initial content first using `set_project_specification_content`."
            )

        editor_service = DocumentEditorService()
        edit_result = editor_service.apply_edits(spec.content, edits)
        if not edit_result.success:
            raise ModelRetry(
                f"Failed to apply edits to the specification of project '{project.name}' (ID {project_id}). "
                f"Confirm you are editing the intended project and that the text exists in its current "
                f"specification. Errors: {'; '.join(edit_result.errors)}"
            )

        document_repo.update_content(spec, edit_result.content)
        document_repo.commit()

        return "Edits applied successfully to project specification."

    return Tool(
        function=edit_project_specification,  # ty:ignore[invalid-argument-type]
        name="edit_project_specification",
        requires_approval=True,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def create_set_project_specification_content_tool(
    project_repo: ProjectRepository,
    document_repo: DocumentRepository,
) -> Tool:
    """Create a tool for setting the full content of a project's specification."""

    def set_project_specification_content(project_id: int, content: str) -> str:
        """Set the full content of a project or initiative's specification document.

        Use this to write the initial specification or to replace it entirely.
        For incremental changes to existing content, use `edit_project_specification`.

        Args:
            project_id: The ID of the project or initiative whose specification to set.
            content: The full content to set for the specification.
        """
        if not content.strip():
            raise ModelRetry("Content cannot be empty.")

        project = project_repo.get_by_id(project_id)
        if not project:
            raise ModelRetry(f"Project with ID {project_id} not found.")

        if not project.specification:
            raise ModelRetry("Project has no specification document.")

        document_repo.update_content(project.specification, content)
        document_repo.commit()

        return "Successfully set project specification content."

    return Tool(
        function=set_project_specification_content,  # ty:ignore[invalid-argument-type]
        name="set_project_specification_content",
        requires_approval=True,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def create_complete_project_tool(project: Project, project_service: ProjectService) -> Tool:
    """Create a tool for marking the agent's own project or initiative as complete."""

    def complete_project(summary: str) -> str:
        """Mark this project or initiative as complete.

        Call this only after performing all cleanup: updating the parent project spec
        with key outcomes and decisions (for initiatives), summarising accomplishments,
        and ensuring no critical follow-up work is unrecorded.

        Args:
            summary: Brief description of what was accomplished, recorded in the event log.
        """
        project_service.complete_project(project, summary)
        entity_type = "Initiative" if project.is_initiative else "Project"
        return f"{entity_type} '{project.name}' has been marked as complete."

    return Tool(
        function=complete_project,  # ty:ignore[invalid-argument-type]
        name="complete_project",
        requires_approval=True,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def create_create_initiative_tool(project: Project, project_service: ProjectService) -> Tool:
    """Create a tool for creating a child initiative under the agent's own project."""

    def create_initiative(name: str, description: str) -> str:
        """Create a new initiative (sub-project) under this project.

        An initiative groups related tasks under a focused sub-goal with its own
        context document. Use this when the user describes significant multi-step work
        that warrants its own scoped context — typically 3+ tasks with a clear sub-goal,
        or a discovery/investigation phase that will generate structured follow-up work.

        Args:
            name: Short name for the initiative.
            description: One-sentence description of the initiative's goal.
        """
        initiative = project_service.create_project(
            name=name,
            description=description,
            parent_project_id=project.id,
        )
        return f"Initiative '{initiative.name}' (ID: {initiative.id}) created under project '{project.name}'."

    return Tool(
        function=create_initiative,  # ty:ignore[invalid-argument-type]
        name="create_initiative",
        requires_approval=True,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]
