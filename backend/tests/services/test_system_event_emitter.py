"""Tests for SystemEventEmitter — verifies correct LogEntry creation for each event type."""

import pytest
from sqlalchemy.orm import Session

from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus
from devboard.db.repositories.log_entry import LogEntryRepository
from devboard.services.system_event_emitter import SystemEventEmitter


@pytest.fixture
def log_entry_repo(db_session: Session) -> LogEntryRepository:
    return LogEntryRepository(db_session)


@pytest.fixture
def emitter(log_entry_repo: LogEntryRepository) -> SystemEventEmitter:
    return SystemEventEmitter(log_entry_repo=log_entry_repo)


class TestEmitTaskCreated:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_created(test_task)
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "task.created"

    def test_content_includes_task_title(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_created(test_task)
        assert test_task.title in entry.content

    def test_metadata(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_created(test_task)
        assert entry.entry_metadata == {"task_title": test_task.title, "branch_name": test_task.branch_name}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_created(test_task)
        assert entry.project_id == test_task.project_id
        assert entry.task_id == test_task.id

    def test_defaults(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_created(test_task)
        assert entry.status == LogEntryStatus.ACTIVE
        assert entry.pinned is False


class TestEmitTaskCompleted:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_completed(test_task, method="manual")
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "task.completed"

    def test_content_includes_task_title(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_completed(test_task, method="local_merge")
        assert test_task.title in entry.content

    def test_metadata_includes_completion_method(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_completed(test_task, method="pr_merge")
        assert entry.entry_metadata == {"task_title": test_task.title, "completion_method": "pr_merge"}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_completed(test_task, method="manual")
        assert entry.project_id == test_task.project_id
        assert entry.task_id == test_task.id


class TestEmitTaskDeleted:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_deleted(test_task)
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "task.deleted"

    def test_content_includes_task_title(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_deleted(test_task)
        assert test_task.title in entry.content

    def test_metadata(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_deleted(test_task)
        assert entry.entry_metadata == {"task_title": test_task.title}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_task_deleted(test_task)
        assert entry.project_id == test_task.project_id
        assert entry.task_id == test_task.id


class TestEmitProjectCreated:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_created(test_task.project)
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "project.created"

    def test_content_includes_project_name(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_created(test_task.project)
        assert test_task.project.name in entry.content

    def test_metadata(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_created(test_task.project)
        assert entry.entry_metadata == {"project_name": test_task.project.name}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_created(test_task.project)
        assert entry.project_id == test_task.project.id
        assert entry.task_id is None


class TestEmitProjectUpdated:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_updated(test_task.project, changed_fields=["name"])
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "project.updated"

    def test_content_includes_project_name(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_updated(test_task.project, changed_fields=["description"])
        assert test_task.project.name in entry.content

    def test_metadata_includes_changed_fields(self, emitter: SystemEventEmitter, test_task):
        fields = ["name", "description"]
        entry = emitter.emit_project_updated(test_task.project, changed_fields=fields)
        assert entry.entry_metadata == {"project_name": test_task.project.name, "changed_fields": fields}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_updated(test_task.project, changed_fields=[])
        assert entry.project_id == test_task.project.id
        assert entry.task_id is None


class TestEmitAgentRunCompleted:
    """Tests for emit_agent_run_completed.

    Conversation instances are mocked to keep the tests focused on emitter logic.
    """

    def _make_task_conversation(self, task) -> object:
        from unittest.mock import Mock

        from devboard.agents.roles import AgentRoleType

        conv = Mock()
        conv.id = 42
        conv.agent_role = AgentRoleType.TASK_IMPLEMENTATION
        conv.get_parent_entity.return_value = task
        return conv

    def _make_project_conversation(self, project) -> object:
        from unittest.mock import Mock

        from devboard.agents.roles import AgentRoleType

        conv = Mock()
        conv.id = 99
        conv.agent_role = AgentRoleType.PROJECT
        conv.get_parent_entity.return_value = project
        return conv

    def _make_codebase_conversation(self) -> object:
        from unittest.mock import Mock

        from devboard.agents.roles import AgentRoleType

        conv = Mock()
        conv.id = 7
        conv.agent_role = AgentRoleType.CODE_REVIEW
        conv.get_parent_entity.return_value = Mock(spec=[])  # not Task or Project — no FK derived
        return conv

    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_task_conversation(test_task)
        entry = emitter.emit_agent_run_completed(conversation=conv, status="completed")
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "agent_run.completed"

    def test_metadata_all_fields(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_task_conversation(test_task)
        entry = emitter.emit_agent_run_completed(
            conversation=conv,
            status="failed",
            error="Something went wrong",
        )
        assert entry.entry_metadata == {
            "conversation_id": 42,
            "agent_role": "task_implementation",
            "status": "failed",
            "error": "Something went wrong",
        }

    def test_error_is_none_when_not_provided(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_project_conversation(test_task.project)
        entry = emitter.emit_agent_run_completed(conversation=conv, status="completed")
        assert entry.entry_metadata["error"] is None

    def test_task_conversation_sets_both_fks(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_task_conversation(test_task)
        entry = emitter.emit_agent_run_completed(conversation=conv, status="completed")
        assert entry.project_id == test_task.project_id
        assert entry.task_id == test_task.id

    def test_project_conversation_omits_task_id(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_project_conversation(test_task.project)
        entry = emitter.emit_agent_run_completed(conversation=conv, status="interrupted")
        assert entry.project_id == test_task.project.id
        assert entry.task_id is None

    def test_codebase_conversation_omits_both_fks(self, emitter: SystemEventEmitter):
        conv = self._make_codebase_conversation()
        entry = emitter.emit_agent_run_completed(conversation=conv, status="completed")
        assert entry.project_id is None
        assert entry.task_id is None

    def test_defaults(self, emitter: SystemEventEmitter, test_task):
        conv = self._make_project_conversation(test_task.project)
        entry = emitter.emit_agent_run_completed(conversation=conv, status="completed")
        assert entry.status == LogEntryStatus.ACTIVE
        assert entry.pinned is False


class TestEmitProjectDeleted:
    def test_correct_source_and_type(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_deleted(project_id=test_task.project_id, project_name="My Project")
        assert entry.source == LogEntrySource.SYSTEM
        assert entry.type == "project.deleted"

    def test_content_includes_project_name(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_deleted(project_id=test_task.project_id, project_name="My Project")
        assert "My Project" in entry.content

    def test_metadata(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_deleted(project_id=test_task.project_id, project_name="My Project")
        assert entry.entry_metadata == {"project_name": "My Project"}

    def test_foreign_keys(self, emitter: SystemEventEmitter, test_task):
        entry = emitter.emit_project_deleted(project_id=test_task.project_id, project_name="My Project")
        assert entry.project_id == test_task.project_id
        assert entry.task_id is None
