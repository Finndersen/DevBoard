"""Tests for LogEntryRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Project, Task
from devboard.db.models.document import DocumentType
from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus
from devboard.db.repositories import LogEntryRepository, ProjectRepository
from devboard.db.repositories.document import DocumentRepository


class TestLogEntryRepository:
    """Tests for LogEntryRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> LogEntryRepository:
        return LogEntryRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session, document_repository: DocumentRepository):
        """Create a test project."""
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(name="Test Project", description="", specification=spec_doc)
        db_session.flush()
        return project

    @pytest.fixture
    def project2(self, db_session: Session, document_repository: DocumentRepository):
        """Create a second test project."""
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(name="Test Project 2", description="", specification=spec_doc)
        db_session.flush()
        return project

    # ---- create ----

    def test_create_persists_all_fields(self, repo: LogEntryRepository, project: Project, db_session: Session):
        """Create a log entry and verify all fields are persisted correctly."""
        ts = datetime(2026, 3, 22, 10, 0, 0, tzinfo=UTC)
        meta = {"agent_id": 7, "run": "abc"}

        log_entry = repo.create(
            source=LogEntrySource.DEVELOPER,
            type="blocker",
            content="Cannot reproduce the race condition",
            project_id=project.id,
            entry_metadata=meta,
            status=LogEntryStatus.ACTIVE,
            pinned=True,
            timestamp=ts,
        )
        db_session.flush()

        assert log_entry.id is not None
        assert log_entry.source == LogEntrySource.DEVELOPER
        assert log_entry.type == "blocker"
        assert log_entry.content == "Cannot reproduce the race condition"
        assert log_entry.project_id == project.id
        assert log_entry.task_id is None
        assert log_entry.entry_metadata == meta
        assert log_entry.status == LogEntryStatus.ACTIVE
        assert log_entry.pinned is True
        assert log_entry.timestamp == ts

    def test_create_defaults(self, repo: LogEntryRepository, db_session: Session):
        """Create a log entry with minimal args and check defaults."""
        log_entry = repo.create(
            source=LogEntrySource.SYSTEM,
            type="task.created",
            content="Task created",
        )
        db_session.flush()

        assert log_entry.id is not None
        assert log_entry.project_id is None
        assert log_entry.task_id is None
        assert log_entry.entry_metadata is None
        assert log_entry.status == LogEntryStatus.ACTIVE
        assert log_entry.pinned is False
        assert log_entry.timestamp is not None

    # ---- get_by_id ----

    def test_get_by_id_returns_log_entry(self, repo: LogEntryRepository, db_session: Session):
        """get_by_id returns the log entry when it exists."""
        log_entry = repo.create(source=LogEntrySource.AGENT, type="thought", content="Thinking…")
        db_session.flush()

        result = repo.get_by_id(log_entry.id)
        assert result is not None
        assert result.id == log_entry.id
        assert result.type == "thought"

    def test_get_by_id_returns_none_when_missing(self, repo: LogEntryRepository):
        """get_by_id returns None for an unknown ID."""
        assert repo.get_by_id(999999) is None

    # ---- query — project / task filtering ----

    def test_query_by_project_id(
        self, repo: LogEntryRepository, project: Project, project2: Project, db_session: Session
    ):
        """query filters by project_id correctly."""
        repo.create(source=LogEntrySource.SYSTEM, type="ev.a", content="A", project_id=project.id)
        repo.create(source=LogEntrySource.SYSTEM, type="ev.b", content="B", project_id=project2.id)
        db_session.flush()

        results = repo.query(project_id=project.id)
        assert len(results) == 1
        assert results[0].content == "A"

    def test_query_by_task_id(self, repo: LogEntryRepository, project: Project, test_task: Task, db_session: Session):
        """query filters by task_id correctly."""
        repo.create(source=LogEntrySource.DEVELOPER, type="thought", content="task log entry", task_id=test_task.id)
        repo.create(source=LogEntrySource.DEVELOPER, type="thought", content="project log entry", project_id=project.id)
        db_session.flush()

        results = repo.query(task_id=test_task.id)
        assert len(results) == 1
        assert results[0].content == "task log entry"

    # ---- query — type pattern ----

    def test_query_by_exact_type(self, repo: LogEntryRepository, db_session: Session):
        """query filters by exact type slug."""
        repo.create(source=LogEntrySource.SYSTEM, type="task.created", content="c1")
        repo.create(source=LogEntrySource.SYSTEM, type="task.completed", content="c2")
        repo.create(source=LogEntrySource.DEVELOPER, type="blocker", content="c3")
        db_session.flush()

        results = repo.query(type_pattern="blocker")
        assert len(results) == 1
        assert results[0].content == "c3"

    def test_query_by_wildcard_type_pattern(self, repo: LogEntryRepository, db_session: Session):
        """query with '*' wildcard matches multiple type slugs."""
        repo.create(source=LogEntrySource.SYSTEM, type="task.created", content="c1")
        repo.create(source=LogEntrySource.SYSTEM, type="task.completed", content="c2")
        repo.create(source=LogEntrySource.DEVELOPER, type="blocker", content="c3")
        db_session.flush()

        results = repo.query(type_pattern="task.*")
        assert len(results) == 2
        contents = {r.content for r in results}
        assert contents == {"c1", "c2"}

    # ---- query — date range ----

    def test_query_by_since(self, repo: LogEntryRepository, db_session: Session):
        """query with 'since' excludes older log entries."""
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
        repo.create(source=LogEntrySource.SYSTEM, type="old", content="old", timestamp=now - timedelta(hours=2))
        repo.create(source=LogEntrySource.SYSTEM, type="new", content="new", timestamp=now)
        db_session.flush()

        results = repo.query(since=now - timedelta(hours=1))
        assert len(results) == 1
        assert results[0].content == "new"

    def test_query_by_until(self, repo: LogEntryRepository, db_session: Session):
        """query with 'until' excludes newer log entries."""
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
        repo.create(source=LogEntrySource.SYSTEM, type="old", content="old", timestamp=now - timedelta(hours=2))
        repo.create(source=LogEntrySource.SYSTEM, type="new", content="new", timestamp=now)
        db_session.flush()

        results = repo.query(until=now - timedelta(hours=1))
        assert len(results) == 1
        assert results[0].content == "old"

    # ---- query — status / source / pinned ----

    def test_query_by_status(self, repo: LogEntryRepository, db_session: Session):
        """query filters by status."""
        repo.create(source=LogEntrySource.DEVELOPER, type="t", content="active", status=LogEntryStatus.ACTIVE)
        repo.create(source=LogEntrySource.DEVELOPER, type="t", content="resolved", status=LogEntryStatus.RESOLVED)
        db_session.flush()

        results = repo.query(status=LogEntryStatus.RESOLVED)
        assert len(results) == 1
        assert results[0].content == "resolved"

    def test_query_by_source(self, repo: LogEntryRepository, db_session: Session):
        """query filters by source."""
        repo.create(source=LogEntrySource.DEVELOPER, type="t", content="dev")
        repo.create(source=LogEntrySource.AGENT, type="t", content="agent")
        repo.create(source=LogEntrySource.SYSTEM, type="t", content="sys")
        db_session.flush()

        results = repo.query(source=LogEntrySource.AGENT)
        assert len(results) == 1
        assert results[0].content == "agent"

    def test_query_by_pinned(self, repo: LogEntryRepository, db_session: Session):
        """query filters by pinned flag."""
        repo.create(source=LogEntrySource.DEVELOPER, type="blocker", content="pinned", pinned=True)
        repo.create(source=LogEntrySource.DEVELOPER, type="thought", content="not pinned", pinned=False)
        db_session.flush()

        results = repo.query(pinned=True)
        assert len(results) == 1
        assert results[0].content == "pinned"

    # ---- query — pagination ----

    def test_query_pagination_limit(self, repo: LogEntryRepository, db_session: Session):
        """query respects the limit parameter."""
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
        for i in range(5):
            repo.create(
                source=LogEntrySource.SYSTEM,
                type="ev",
                content=f"ev{i}",
                timestamp=now + timedelta(seconds=i),
            )
        db_session.flush()

        results = repo.query(limit=3)
        assert len(results) == 3

    def test_query_pagination_offset(self, repo: LogEntryRepository, db_session: Session):
        """query respects the offset parameter for pagination."""
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
        for i in range(5):
            repo.create(
                source=LogEntrySource.SYSTEM,
                type="ev",
                content=f"ev{i}",
                timestamp=now + timedelta(seconds=i),
            )
        db_session.flush()

        page1 = repo.query(limit=2, offset=0)
        page2 = repo.query(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert {r.content for r in page1}.isdisjoint({r.content for r in page2})

    # ---- query — ordering ----

    def test_query_ordered_by_timestamp_ascending(self, repo: LogEntryRepository, db_session: Session):
        """query returns log entries ordered by timestamp ascending."""
        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=UTC)
        repo.create(source=LogEntrySource.SYSTEM, type="t", content="third", timestamp=now + timedelta(seconds=2))
        repo.create(source=LogEntrySource.SYSTEM, type="t", content="first", timestamp=now)
        repo.create(source=LogEntrySource.SYSTEM, type="t", content="second", timestamp=now + timedelta(seconds=1))
        db_session.flush()

        results = repo.query()
        contents = [r.content for r in results]
        assert contents == ["first", "second", "third"]

    # ---- update_status ----

    def test_update_status(self, repo: LogEntryRepository, db_session: Session):
        """update_status changes the log entry's status and returns the updated log entry."""
        log_entry = repo.create(source=LogEntrySource.DEVELOPER, type="blocker", content="stuck")
        db_session.flush()

        updated = repo.update_status(log_entry.id, LogEntryStatus.RESOLVED)
        assert updated is not None
        assert updated.id == log_entry.id
        assert updated.status == LogEntryStatus.RESOLVED

    def test_update_status_not_found(self, repo: LogEntryRepository):
        """update_status returns None when the log entry does not exist."""
        result = repo.update_status(999999, LogEntryStatus.RESOLVED)
        assert result is None

    # ---- update_pinned ----

    def test_update_pinned(self, repo: LogEntryRepository, db_session: Session):
        """update_pinned changes the pinned flag and returns the updated log entry."""
        log_entry = repo.create(source=LogEntrySource.DEVELOPER, type="decision", content="Use SQLite", pinned=False)
        db_session.flush()

        updated = repo.update_pinned(log_entry.id, True)
        assert updated is not None
        assert updated.id == log_entry.id
        assert updated.pinned is True

    def test_update_pinned_not_found(self, repo: LogEntryRepository):
        """update_pinned returns None when the log entry does not exist."""
        result = repo.update_pinned(999999, True)
        assert result is None
