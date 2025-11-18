"""Task repository for task data access operations."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from devboard.db.models import Document, Task
from devboard.db.models.base import task_context_resource_association
from devboard.db.models.task import TaskStatus
from devboard.db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for task data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(
        self,
        project_id: int,
        title: str,
        specification: "Document",
        implementation_plan: "Document | None" = None,
        status: TaskStatus = TaskStatus.DEFINING,
        codebase_id: int | None = None,
        remote_task_id: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            project_id: ID of the parent project
            title: Task title
            specification: Specification document instance
            implementation_plan: Optional implementation plan document instance
            status: Initial task status (defaults to DEFINING)
            codebase_id: Optional codebase ID
            remote_task_id: Optional remote task identifier

        Returns:
            Created Task instance
        """
        task = Task(
            project_id=project_id,
            title=title,
            specification_id=specification.id,
            implementation_plan_id=implementation_plan.id if implementation_plan else None,
            status=status,
            codebase_id=codebase_id,
            remote_task_id=remote_task_id,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def get_by_id(self, task_id: int) -> Task | None:
        """Get a task by its ID.

        Args:
            task_id: The task ID to search for

        Returns:
            Task instance if found, None otherwise
        """
        stmt = select(Task).where(Task.id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self) -> list[Task]:
        """Get all tasks.

        Returns:
            List of all tasks
        """
        stmt = select(Task)
        return list(self.db.execute(stmt).scalars().all())

    def get_for_project(self, project_id: int) -> list[Task]:
        """Get all tasks for a specific project.

        Args:
            project_id: The project ID to get tasks for

        Returns:
            List of tasks for the project
        """
        stmt = select(Task).where(Task.project_id == project_id)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, task: Task) -> Task:
        """Update an existing task.

        Args:
            task: Task instance to update

        Returns:
            Updated task
        """
        self.db.merge(task)
        return task

    def delete_task_context_resources(self, task: Task) -> int:
        """Delete all task-context resource associations for a task.

        Args:
            task: The task to clean up associations for

        Returns:
            Number of association rows deleted
        """
        stmt = delete(task_context_resource_association).where(task_context_resource_association.c.task_id == task.id)
        result = self.db.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]

    def delete(self, task: Task) -> None:
        """Delete a task entity.

        Args:
            task: Task instance to delete
        """
        self.db.delete(task)
        self.db.flush()
