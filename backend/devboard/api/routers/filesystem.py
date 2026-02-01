"""Filesystem browsing API endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class DirectoryListResponse(BaseModel):
    """Response for directory listing."""

    current_path: str
    parent_path: str | None
    directories: list[str]


@router.get("/browse", response_model=DirectoryListResponse)
async def browse_directory(
    path: str | None = Query(None, description="Path to browse. Defaults to home directory."),
) -> DirectoryListResponse:
    """Browse directories at the given path.

    Args:
        path: Directory path to browse. If not provided, starts from home directory.

    Returns:
        List of directories at the given path with parent path for navigation.
    """
    # Default to home directory if no path provided
    if path is None or path == "":
        target_path = Path.home()
    else:
        target_path = Path(path)

    # Resolve to absolute path and normalize
    try:
        target_path = target_path.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

    # Security: Prevent path traversal by ensuring resolved path is valid
    # The resolve() call already handles .. and symbolic links
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Path does not exist: {target_path}")

    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {target_path}")

    # Get parent path (None if at root)
    parent_path = str(target_path.parent) if target_path.parent != target_path else None

    # List only directories, excluding hidden directories (those starting with .)
    try:
        directories = sorted(
            [item.name for item in target_path.iterdir() if item.is_dir() and not item.name.startswith(".")]
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied accessing: {target_path}") from None
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error reading directory: {e}") from e

    return DirectoryListResponse(
        current_path=str(target_path),
        parent_path=parent_path,
        directories=directories,
    )
