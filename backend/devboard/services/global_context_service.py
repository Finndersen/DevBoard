"""Global context service — reads/writes the workspace-level markdown context file."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from devboard.services.project_directory import get_devboard_home


@dataclass
class GlobalContextData:
    content: str
    content_hash: str
    updated_at: datetime


def _md5(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


class GlobalContextService:
    def __init__(self) -> None:
        self._path: Path = get_devboard_home() / "docs" / "global_context.md"

    def get(self) -> GlobalContextData:
        if not self._path.exists():
            return GlobalContextData(
                content="",
                content_hash=_md5(""),
                updated_at=datetime.now(UTC),
            )
        content = self._path.read_text(encoding="utf-8")
        updated_at = datetime.fromtimestamp(self._path.stat().st_mtime, tz=UTC)
        return GlobalContextData(content=content, content_hash=_md5(content), updated_at=updated_at)

    def update(self, content: str) -> GlobalContextData:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(content, encoding="utf-8")
        updated_at = datetime.fromtimestamp(self._path.stat().st_mtime, tz=UTC)
        return GlobalContextData(content=content, content_hash=_md5(content), updated_at=updated_at)
