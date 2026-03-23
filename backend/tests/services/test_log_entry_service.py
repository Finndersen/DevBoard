"""Tests for LogEntryService auto-population and passthrough logic."""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus
from devboard.db.repositories.log_entry import LogEntryRepository
from devboard.db.repositories.task import TaskRepository
from devboard.services.log_entry_service import LogEntryService


class TestLogEntryServiceCreateLogEntry:
    @pytest.fixture
    def log_entry_repo(self, db_session: Session) -> LogEntryRepository:
        return LogEntryRepository(db_session)

    @pytest.fixture
    def task_repo(self, db_session: Session) -> TaskRepository:
        return TaskRepository(db_session)

    @pytest.fixture
    def service(self, log_entry_repo: LogEntryRepository, task_repo: TaskRepository) -> LogEntryService:
        return LogEntryService(log_entry_repo=log_entry_repo, task_repo=task_repo)

    def test_create_with_task_id_only_auto_populates_project_id(self, service: LogEntryService, test_task):
        """When only task_id is provided, project_id is resolved from the task."""
        log_entry = service.create_log_entry(
            source=LogEntrySource.DEVELOPER,
            type="blocker",
            content="Can't reproduce the race condition",
            task_id=test_task.id,
        )

        assert log_entry.task_id == test_task.id
        assert log_entry.project_id == test_task.project_id

    def test_create_with_both_ids_preserves_both(self, service: LogEntryService, test_task):
        """When both project_id and task_id are provided, both are stored as-is."""
        log_entry = service.create_log_entry(
            source=LogEntrySource.DEVELOPER,
            type="thought",
            content="Considering alternative approach",
            project_id=test_task.project_id,
            task_id=test_task.id,
        )

        assert log_entry.project_id == test_task.project_id
        assert log_entry.task_id == test_task.id

    def test_create_with_project_id_only_leaves_task_id_null(self, service: LogEntryService, test_task):
        """When only project_id is provided, task_id remains null."""
        log_entry = service.create_log_entry(
            source=LogEntrySource.DEVELOPER,
            type="decision",
            content="Going with approach A",
            project_id=test_task.project_id,
        )

        assert log_entry.project_id == test_task.project_id
        assert log_entry.task_id is None

    def test_create_with_neither_id_both_null(self, service: LogEntryService):
        """When neither id is provided, both remain null."""
        log_entry = service.create_log_entry(
            source=LogEntrySource.SYSTEM,
            type="system.startup",
            content="System started",
        )

        assert log_entry.project_id is None
        assert log_entry.task_id is None

    def test_create_with_invalid_task_id_raises_404(self, service: LogEntryService):
        """When task_id does not exist and no project_id is given, raises HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            service.create_log_entry(
                source=LogEntrySource.DEVELOPER,
                type="blocker",
                content="Some issue",
                task_id=999999,
            )

        assert exc_info.value.status_code == 404


class TestLogEntryServicePassthroughs:
    """Verify that query/update methods delegate correctly to the repository."""

    @pytest.fixture
    def log_entry_repo(self, db_session: Session) -> LogEntryRepository:
        return LogEntryRepository(db_session)

    @pytest.fixture
    def task_repo(self, db_session: Session) -> TaskRepository:
        return TaskRepository(db_session)

    @pytest.fixture
    def service(self, log_entry_repo: LogEntryRepository, task_repo: TaskRepository) -> LogEntryService:
        return LogEntryService(log_entry_repo=log_entry_repo, task_repo=task_repo)

    @pytest.fixture
    def log_entry(self, service: LogEntryService, test_task):
        return service.create_log_entry(
            source=LogEntrySource.DEVELOPER,
            type="blocker",
            content="Blocking issue",
            project_id=test_task.project_id,
        )

    def test_query_log_entries_filters_by_project_id(self, service: LogEntryService, test_task):
        """query_log_entries returns log entries matching project_id filter."""
        service.create_log_entry(
            source=LogEntrySource.DEVELOPER,
            type="thought",
            content="Log Entry A",
            project_id=test_task.project_id,
        )
        results = service.query_log_entries(project_id=test_task.project_id)
        assert len(results) >= 1
        assert all(e.project_id == test_task.project_id for e in results)

    def test_update_log_entry_status(self, service: LogEntryService, log_entry):
        """update_log_entry_status updates the log entry status."""
        updated = service.update_log_entry_status(log_entry.id, LogEntryStatus.RESOLVED)
        assert updated is not None
        assert updated.status == LogEntryStatus.RESOLVED

    def test_update_log_entry_pinned(self, service: LogEntryService, log_entry):
        """update_log_entry_pinned updates the pinned flag."""
        updated = service.update_log_entry_pinned(log_entry.id, True)
        assert updated is not None
        assert updated.pinned is True

    def test_update_log_entry_status_nonexistent_returns_none(self, service: LogEntryService):
        """update_log_entry_status returns None for unknown log entry id."""
        result = service.update_log_entry_status(999999, LogEntryStatus.RESOLVED)
        assert result is None

    def test_update_log_entry_pinned_nonexistent_returns_none(self, service: LogEntryService):
        """update_log_entry_pinned returns None for unknown log entry id."""
        result = service.update_log_entry_pinned(999999, True)
        assert result is None
