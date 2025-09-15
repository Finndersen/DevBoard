"""Task repository for task data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import Task
from devboard.db.models.document import DocumentType
from devboard.db.repositories.base import BaseRepository
from devboard.db.repositories.document import DocumentRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for task data access operations with document management."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)
        self.document_repo = DocumentRepository(db_session)

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

    def create(self, project_id: int, title: str, **kwargs) -> Task:
        """Create a new task with required documents.

        Args:
            project_id: ID of the project this task belongs to
            title: Task title
            **kwargs: Additional task fields

        Returns:
            Created task with assigned ID and documents
        """
        # Create required specification document
        specification_doc = self.document_repo.create(DocumentType.TASK_SPECIFICATION, "")

        # Create task with document references
        task = Task(project_id=project_id, title=title, specification_id=specification_doc.id, **kwargs)

        self.db.add(task)
        self.db.flush()  # Get the ID without committing
        return task

    def create_implementation_plan(self, task: Task) -> Task:
        """Create implementation plan document for a task if it doesn't exist.

        Args:
            task: Task instance to add implementation plan to

        Returns:
            Updated task with implementation plan
        """
        if task.implementation_plan_id is None:
            implementation_plan_doc = self.document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
            task.implementation_plan_id = implementation_plan_doc.id
            self.db.flush()
        return task

    def set_task_implementation_plan(self, task: Task, content: str) -> Task:
        """Create or update implementation plan document for a task.

        This method handles both creating a new implementation plan document
        if it doesn't exist and updating the content.

        Args:
            task: Task instance to set implementation plan for
            content: Implementation plan content

        Returns:
            Updated task with implementation plan
        """
        # Create implementation plan document if it doesn't exist
        if task.implementation_plan_id is None:
            implementation_plan_doc = self.document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, content)
            task.implementation_plan_id = implementation_plan_doc.id
            self.db.flush()
            self.db.refresh(task)  # Refresh to load the new relationship
        else:
            # Update existing implementation plan content
            self.document_repo.update_content(task.implementation_plan, content)
        
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

    def update_specification_content(self, task: Task, content: str) -> Task:
        """Update task specification content.

        Args:
            task: Task instance
            content: New specification content

        Returns:
            Updated task
        """
        self.document_repo.update_content(task.specification, content)
        return task

    def update_implementation_plan_content(self, task: Task, content: str) -> Task:
        """Update task implementation plan content.

        Args:
            task: Task instance
            content: New implementation plan content

        Returns:
            Updated task
        """
        if task.implementation_plan is None:
            self.create_implementation_plan(task)

        self.document_repo.update_content(task.implementation_plan, content)
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
