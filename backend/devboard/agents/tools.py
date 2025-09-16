import logfire
from pydantic_ai import ApprovalRequired, RunContext, Tool

from devboard.agents.deps import BaseDeps
from devboard.api.schemas import DocumentEdit
from devboard.db.models.document import Document
from devboard.db.repositories.document import DocumentRepository
from devboard.services.document_editor import DocumentEditorService


def create_document_edit_tool(document: Document, document_repo: DocumentRepository) -> Tool:
    """Create a document editing tool.
    First, the edits are validated to ensure they can be applied. If validation passes,
    the tool will request approval before applying the edits.

    Args:
        document: Document model to edit
        document_repo: Repository for document operations
    """

    def edit_document_tool(ctx: RunContext[BaseDeps], edits: list[DocumentEdit], reasoning: str = "") -> str:
        """Edit document with the provided edits.

        Args:
            edits: List of find-replace edits to apply
            reasoning: Optional CONCISE reasoning for why these edits are being made

        Returns:
            Success message or error details
        """
        with logfire.span(
            "base_agent.document_edit_tool",
            document_type=document.document_type,
            document_id=document.id,
            edit_count=len(edits),
            reasoning_length=len(reasoning),
        ):
            # Create document editor service
            editor_service = DocumentEditorService()

            # Pre-validate edits can be applied
            edit_result = editor_service.apply_edits(document.content, edits)
            if not edit_result.success:
                error_msg = f"Failed to apply edits to document: {'; '.join(edit_result.errors)}"
                logfire.error(
                    "Edit validation failed",
                    document_type=document.document_type,
                    document_id=document.id,
                    errors=edit_result.errors,
                )
                # Return error immediately, no deferral needed
                return error_msg

            if not ctx.tool_call_approved:
                # This will show the edits to the user for approval
                raise ApprovalRequired()

            # Update document content and hash using repository
            document_repo.update_content(document, edit_result.content)

            logfire.info(
                "Document edits applied successfully",
                document_type=document.document_type,
                document_id=document.id,
            )

            return f"Edits applied successfully to {document.document_type}."

    return Tool(
        function=edit_document_tool,
        name=f"edit_{document.document_type}",
        requires_approval=True,
    )


async def get_relevant_context(ctx: RunContext[BaseDeps], resource_uri: str, query: str) -> str:
    """Get focused context from an ON_DEMAND resource.

    Use this tool when you need specific information from a resource that's
    only available as a description in the on_demand_resources list.

    Args:
        resource_uri: The URI of the resource to query (must be from on_demand_resources)
        query: Specific question about the resource

    Returns:
        Focused context relevant to your query
    """
    with logfire.span(
        "qa_agent.get_relevant_context",
        resource_uri=resource_uri,
        query_length=len(query),
    ):
        try:
            # Verify the resource is available
            available_uris = [res.uri for res in ctx.deps.on_demand_resources]
            if resource_uri not in available_uris:
                logfire.warn(
                    "Resource not available",
                    resource_uri=resource_uri,
                    available_count=len(available_uris),
                )
                return f"Error: Resource {resource_uri} not available for this project"

            result = await ctx.deps.context_service.get_on_demand_context(resource_uri, query)
            logfire.info("On-demand context retrieved", result_length=len(result))
            return result
        except Exception as e:
            logfire.error(
                "Error getting on-demand context",
                resource_uri=resource_uri,
                error=str(e),
                exc_info=e,
            )
            return f"Error retrieving context: {e}"
