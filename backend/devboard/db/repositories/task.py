"""Task repository for task data access operations."""

from sqlalchemy import select

from devboard.db.models import Task
from devboard.db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for task data access operations."""

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

    def create(self, task: Task) -> Task:
        """Create a new task.

        Args:
            task: Task instance to create

        Returns:
            Created task with assigned ID
        """
        self.db.add(task)
        self.db.flush()  # Get the ID without committing
        return task

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
            self.db.delete(task)
            return True
        return False
