"""Utility for emitting system LogEntry events for entity lifecycle operations."""

from devboard.db.models.conversation import Conversation
from devboard.db.models.log_entry import LogEntry, LogEntrySource, LogEntryStatus
from devboard.db.models.project import Project
from devboard.db.models.task import Task
from devboard.db.repositories.log_entry import LogEntryRepository


class SystemEventEmitter:
    """Emits system LogEntry records for entity lifecycle events."""

    def __init__(self, log_entry_repo: LogEntryRepository):
        self.log_entry_repo = log_entry_repo

    def emit_task_created(self, task: Task) -> LogEntry:
        """Emit a task.created event."""
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="task.created",
            content=f"Task '{task.title}' was created",
            project_id=task.project_id,
            task_id=task.id,
            entry_metadata={"task_title": task.title, "branch_name": task.branch_name},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_task_completed(self, task: Task, method: str) -> LogEntry:
        """Emit a task.completed event.

        Args:
            task: The completed task
            method: Completion method — one of "transition", "local_merge", "pr_merge"
        """
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="task.completed",
            content=f"Task '{task.title}' was completed",
            project_id=task.project_id,
            task_id=task.id,
            entry_metadata={"task_title": task.title, "completion_method": method},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_task_deleted(self, task: Task) -> LogEntry:
        """Emit a task.deleted event."""
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="task.deleted",
            content=f"Task '{task.title}' was deleted",
            project_id=task.project_id,
            task_id=task.id,
            entry_metadata={"task_title": task.title},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_task_merged(self, task: Task, method: str) -> LogEntry:
        """Emit a task.merged event.

        Args:
            task: The merged task
            method: Merge method — one of "local_merge", "pr_merge"
        """
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="task.merged",
            content=f"Task '{task.title}' was merged",
            project_id=task.project_id,
            task_id=task.id,
            entry_metadata={"task_title": task.title, "merge_method": method},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_project_created(self, project: Project) -> LogEntry:
        """Emit a project.created event."""
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="project.created",
            content=f"Project '{project.name}' was created",
            project_id=project.id,
            entry_metadata={"project_name": project.name},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_project_updated(self, project: Project, changed_fields: list[str]) -> LogEntry:
        """Emit a project.updated event."""
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="project.updated",
            content=f"Project '{project.name}' was updated",
            project_id=project.id,
            entry_metadata={"project_name": project.name, "changed_fields": changed_fields},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_agent_run_completed(
        self,
        conversation: Conversation,
        status: str,
        error: str | None = None,
    ) -> LogEntry:
        """Emit an agent_run.completed event."""
        project_id: int | None = None
        task_id: int | None = None
        parent = conversation.get_parent_entity()
        if isinstance(parent, Task):
            task_id = parent.id
            project_id = parent.project_id
        elif isinstance(parent, Project):
            project_id = parent.id
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="agent_run.completed",
            content=f"Agent run {status} for conversation {conversation.id}",
            project_id=project_id,
            task_id=task_id,
            entry_metadata={
                "conversation_id": conversation.id,
                "agent_role": conversation.agent_role.value,
                "status": status,
                "error": error,
            },
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )

    def emit_project_deleted(self, project_id: int, project_name: str) -> LogEntry:
        """Emit a project.deleted event.

        Takes primitives since the entity is about to be deleted.
        """
        return self.log_entry_repo.create(
            source=LogEntrySource.SYSTEM,
            type="project.deleted",
            content=f"Project '{project_name}' was deleted",
            project_id=project_id,
            entry_metadata={"project_name": project_name},
            status=LogEntryStatus.ACTIVE,
            pinned=False,
        )
