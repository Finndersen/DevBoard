"""Task repository for task data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import Document, Task
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
        implementation_plan: "Document",
        status: TaskStatus = TaskStatus.DEFINING,
        codebase_id: int | None = None,
        remote_task_id: str | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            project_id: ID of the parent project
            title: Task title
            specification: Specification document instance
            implementation_plan: Implementation plan document instance
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
            implementation_plan_id=implementation_plan.id,
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

    def delete_by_id(self, task_id: int) -> bool:
        """Delete a task by its ID.

        Args:
            task_id: The task ID to delete

        Returns:
            True if task was deleted, False if not found
        """
        task = self.get_by_id(task_id)
        if task:
            # Documents will be cascade deleted via foreign key constraints
            self.db.delete(task)
            return True
        return False
