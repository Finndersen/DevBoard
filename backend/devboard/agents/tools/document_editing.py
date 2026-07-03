from pydantic_ai import ModelRetry, Tool

from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document
from devboard.db.models.project import Project
from devboard.db.models.task import Task
from devboard.db.repositories import DocumentRepository
from devboard.services.document_editor import DocumentEditorService
from devboard.services.system_event_emitter import SystemEventEmitter


def create_document_edit_tool(
    document: Document,
    document_repo: DocumentRepository,
    document_parent: Task | Project,
    requires_approval: bool = True,
    system_event_emitter: SystemEventEmitter | None = None,
) -> Tool:
    """Create an engine-agnostic document editing tool.

    The tool validates edits before applying them.

    Args:
        document: Document model to edit
        document_repo: Repository for document operations
        document_parent: The entity that owns the document (Task or Project)
        requires_approval: Whether to require approval before executing edits (default: True)
        system_event_emitter: Optional emitter for document.updated events
    """

    def edit_document_tool(edits: list[DocumentEdit], edit_summary: str) -> str:
        """
        Apply targeted find-replace edits to an EXISTING virtual document that already has content.
        This document DOES NOT exist on the file system, but is managed by the application.

        Use this tool only to make incremental changes to content that already exists.
        To write the initial content or fully replace it, use the corresponding set-content
        tool instead of this one.

        DOCUMENT EDITING RULES:
        1. Make precise find-replace edits using DocumentEdit objects
        2. Use exact text matches for 'find' - the text must exist exactly as written
        3. Use the MINIMUM necessary text to uniquely identify the location to replace
        4. Preserve markdown formatting and structure
        5. ONLY call this tool after discussing with the user and arriving at an understanding of the changes to be made

        Args:
            edits: List of find-replace edits to apply
            edit_summary: Concise summary/description of the edit being made
        """
        if not document.content:
            raise ModelRetry(
                f"{document.document_type.replace('_', ' ').title()} has no content yet. "
                f"Set the initial content first before applying edits."
            )

        # Create document editor service
        editor_service = DocumentEditorService()

        # Pre-validate edits can be applied
        edit_result = editor_service.apply_edits(document.content, edits)
        if not edit_result.success:
            raise ModelRetry(f"Failed to apply edits to document: {'; '.join(edit_result.errors)}")

        # Update document content and hash using repository
        document_repo.update_content(document, edit_result.content)
        # Commit immediately so the frontend can display updated content during the stream
        document_repo.commit()

        # Emit document.updated event if emitter is available
        if system_event_emitter:
            system_event_emitter.emit_document_updated(document_parent, document.document_type, edit_summary)

        return f"Edits applied successfully to {document.document_type}."

    return Tool(
        function=edit_document_tool,  # ty:ignore[invalid-argument-type]
        name=f"edit_{document.document_type}",
        requires_approval=requires_approval,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def create_set_document_content_tool(
    document: Document,
    document_repo: DocumentRepository,
    document_parent: Task | Project,
    requires_approval: bool | None = None,
    system_event_emitter: SystemEventEmitter | None = None,
) -> Tool:
    """Create an engine-agnostic tool for setting the content of a document.

    This tool can be used on both blank and non-blank documents:
    - For blank documents: No approval required by default (non-destructive)
    - For non-blank documents: Requires approval by default (destructive - replaces existing content)

    Args:
        document: Document model to set content for
        document_repo: Repository for document operations
        document_parent: The entity that owns the document (Task or Project)
        requires_approval: Whether to require approval. If None, uses smart logic:
            requires approval only if document already has content (default: None)
        system_event_emitter: Optional emitter for document.updated events
    """

    def set_document_content_tool(content: str, edit_summary: str) -> str:
        """Set the content of a virtual document.
        This document DOES NOT exist on the file system, but managed by the application.
        ONLY call this tool after discussing with the user and arriving at an understanding of the changes to be made.

        Args:
            content: The full content to set for the document
            edit_summary: Concise summary/description of the content being set

        Returns:
            Success message or error details
        """
        # Validate content is not empty
        if not content.strip():
            raise ModelRetry("Error: Content cannot be empty.")

        # Update document content and hash using repository
        document_repo.update_content(document, content)
        # Commit immediately so the frontend can display updated content during the stream
        document_repo.commit()

        # Emit document.updated event if emitter is available
        if system_event_emitter:
            system_event_emitter.emit_document_updated(document_parent, document.document_type, edit_summary)

        return f"Successfully set content for {document.document_type}."

    # Determine approval requirement: use provided value or smart logic based on content
    if requires_approval is None:
        requires_approval = bool(document.content and document.content.strip())

    return Tool(
        function=set_document_content_tool,  # ty:ignore[invalid-argument-type]
        name=f"set_{document.document_type}_content",
        requires_approval=requires_approval,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def build_project_context_document_tools(
    project: Project,
    document_repo: DocumentRepository,
    *,
    system_event_emitter: SystemEventEmitter | None = None,
    include_set_content: bool = False,
) -> list[Tool]:
    """Build the context-document editing tools scoped to a project's place in the hierarchy.

    Each tool is bound to a specific document, so the agent never supplies a project id it
    would have to guess. Tool names come from each document's type:

    - Top-level project → `edit_project_specification` (+ `set_project_specification_content`
      when include_set_content).
    - Initiative → `edit_initiative_context` (+ `set_initiative_context_content` when
      include_set_content) for its own document, plus `edit_project_specification` targeting the
      parent project's document so an initiative agent can also feed outcomes up to the parent.

    Args:
        project: The project (or initiative) the agent is scoped to.
        document_repo: Repository for document operations.
        system_event_emitter: Optional emitter for document.updated events.
        include_set_content: Whether to also expose a full-replace tool for the project's own
            document. The parent document is always edit-only.
    """
    tools: list[Tool] = []
    if include_set_content:
        tools.append(
            create_set_document_content_tool(
                project.specification,
                document_repo,
                document_parent=project,
                system_event_emitter=system_event_emitter,
            )
        )
    tools.append(
        create_document_edit_tool(
            project.specification,
            document_repo,
            document_parent=project,
            system_event_emitter=system_event_emitter,
        )
    )
    if project.parent is not None:
        tools.append(
            create_document_edit_tool(
                project.parent.specification,
                document_repo,
                document_parent=project.parent,
                system_event_emitter=system_event_emitter,
            )
        )
    return tools
