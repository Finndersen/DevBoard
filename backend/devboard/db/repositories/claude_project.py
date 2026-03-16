"""Repository for Claude Code project path cache."""

from sqlalchemy import delete, select

from devboard.db.models.claude_project import ClaudeProjectPathCache
from devboard.db.repositories.base import BaseRepository


class ClaudeProjectCacheRepository(BaseRepository[ClaudeProjectPathCache]):
    def get_all(self) -> dict[str, str]:
        """Return all cached {encoded_path: path} entries."""
        rows = self.db.execute(select(ClaudeProjectPathCache)).scalars().all()
        return {row.encoded_path: row.path for row in rows}

    def set_path(self, encoded_path: str, path: str) -> None:
        """Insert or update a path mapping."""
        existing = self.db.get(ClaudeProjectPathCache, encoded_path)
        if existing:
            existing.path = path
        else:
            self.db.add(ClaudeProjectPathCache(encoded_path=encoded_path, path=path))

    def delete_encoded_paths(self, encoded_paths: set[str]) -> None:
        """Remove stale entries for directories that no longer exist."""
        if encoded_paths:
            self.db.execute(
                delete(ClaudeProjectPathCache).where(ClaudeProjectPathCache.encoded_path.in_(encoded_paths))
            )
