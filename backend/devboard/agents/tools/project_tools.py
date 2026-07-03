"""Tools for querying and editing projects."""

import json

from pydantic_ai import ModelRetry, Tool

from devboard.api.schemas import DocumentEdit
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.document_editor import DocumentEditorService
from devboard.services.task_service import TaskService


def create_list_projects_tool(project_repo: ProjectRepository) -> Tool:
    """Create a tool for listing all projects."""

    def list_projects() -> str:
        """List all projects and initiatives.

        Returns:
            JSON list of entries with id, name, description, type ('project' or 'initiative'),
            parent_project_id (set for initiatives), and codebase names.
        """
        projects = project_repo.get_all()
        return json.dumps(
            [
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "type": "initiative" if project.is_initiative else "project",
                    "parent_project_id": project.parent_project_id,
                    "codebases": [cb.name for cb in (project.codebases or [])],
                }
                for project in projects
            ]
        )

    return Tool(function=list_projects, name="list_projects")  # ty:ignore[invalid-argument-type, invalid-return-type]


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
        """Apply targeted find-replace edits to a project's specification document.

        Use this tool only to make incremental changes to content that already exists.
        To set or replace the full specification content, use `set_project_specification_content`.

        DOCUMENT EDITING RULES:
        1. Make precise find-replace edits using DocumentEdit objects
        2. Use exact text matches for 'find' - the text must exist exactly as written
        3. Use the MINIMUM necessary text to uniquely identify the location to replace
        4. Preserve markdown formatting and structure

        Args:
            project_id: The ID of the project whose specification to edit.
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
        """Set the full content of a project's specification document.

        Use this to write the initial specification or to replace it entirely.
        For incremental changes to existing content, use `edit_project_specification`.

        Args:
            project_id: The ID of the project whose specification to set.
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
