"""Tools for viewing and updating codebase configuration."""

import json

from pydantic_ai import ModelRetry, Tool

from devboard.db.models import Codebase
from devboard.db.repositories.codebase import CodebaseRepository


def _resolve_codebase(codebase_name: str, codebases: list[Codebase]) -> Codebase:
    available_names = [cb.name for cb in codebases]
    if not available_names:
        raise ModelRetry("No codebases are accessible in this context.")

    for cb in codebases:
        if cb.name == codebase_name:
            return cb

    raise ModelRetry(f"Codebase '{codebase_name}' not found. Available codebases: {', '.join(available_names)}")


def create_view_codebase_details_tool(
    codebases: list[Codebase],
    _codebase_repo: CodebaseRepository,
) -> Tool:
    """Create a tool for viewing full details of a codebase.

    Args:
        codebases: The codebases accessible to this agent.
        _codebase_repo: Repository for codebase data access (unused — view reads from in-memory objects).
    """

    async def view_codebase_details(codebase_name: str) -> str:
        """View full configuration details of a codebase.

        Args:
            codebase_name: Name of the codebase to view.

        Returns:
            JSON string with all codebase fields.
        """
        codebase = _resolve_codebase(codebase_name, codebases)
        return json.dumps(
            {
                "id": codebase.id,
                "name": codebase.name,
                "description": codebase.description,
                "repository_url": codebase.repository_url,
                "local_path": codebase.local_path,
                "default_branch": codebase.default_branch,
                "merge_method": codebase.merge_method,
                "branch_handling": codebase.branch_handling,
                "max_worktrees": codebase.max_worktrees,
                "setup_command": codebase.setup_command,
                "developer_context": codebase.developer_context,
            }
        )

    return Tool(function=view_codebase_details, name="view_codebase_details")


def create_update_codebase_tool(
    codebases: list[Codebase],
    codebase_repo: CodebaseRepository,
) -> Tool:
    """Create a tool for updating codebase configuration properties.

    Args:
        codebases: The codebases accessible to this agent.
        codebase_repo: Repository for codebase data access.
    """

    async def update_codebase(
        codebase_name: str,
        description: str | None = None,
        setup_command: str | None = None,
        developer_context: str | None = None,
    ) -> str:
        """Update configuration properties of a codebase.

        Only the fields explicitly provided will be updated.

        Args:
            codebase_name: Name of the codebase to update.
            description: New description for the codebase.
            setup_command: New setup command (run after cloning/switching branches).
            developer_context: New developer context documentation for agents.

        Returns:
            JSON string with the codebase id, name, and updated field values.
        """
        if description is None and setup_command is None and developer_context is None:
            raise ModelRetry(
                "No fields to update. Provide at least one of: description, setup_command, developer_context."
            )

        codebase = _resolve_codebase(codebase_name, codebases)

        updated_fields: dict[str, str | None] = {}
        for field, value in [
            ("description", description),
            ("setup_command", setup_command),
            ("developer_context", developer_context),
        ]:
            if value is not None:
                setattr(codebase, field, value)
                updated_fields[field] = value

        codebase_repo.update(codebase)
        codebase_repo.db.commit()
        codebase_repo.db.refresh(codebase)

        return json.dumps({"id": codebase.id, "name": codebase.name, **updated_fields})

    return Tool(function=update_codebase, name="update_codebase")
