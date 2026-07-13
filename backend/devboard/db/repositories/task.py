"""Task repository for task data access operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from devboard.db.models import Codebase, Conversation, Document, Initiative, ParentEntityType, Task, TaskStatus
from devboard.db.models.implementation_plan import ImplementationPlan
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
        base_branch: str,
        codebase_id: int,
        branch_name: str,
        implementation_plan: "Document | None" = None,
        status: TaskStatus = TaskStatus.PLANNING,
        custom_fields: dict[str, Any] | None = None,
    ) -> Task:
        """Create a new task.

        Args:
            project_id: ID of the parent project
            title: Task title
            specification: Specification document instance
            base_branch: Base branch for git operations
            codebase_id: Codebase ID
            implementation_plan: Optional implementation plan document instance
            status: Initial task status (defaults to PLANNING)
            branch_name: Git branch name
            custom_fields: Optional custom field values as a JSON-compatible dict

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
            branch_name=branch_name,
            base_branch=base_branch,
            custom_fields=custom_fields,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def get_by_id(self, task_id: int, *, with_documents: bool = False) -> Task | None:
        """Get a task by its ID.

        Args:
            task_id: The task ID to search for
            with_documents: If True, eager load document relationships

        Returns:
            Task instance if found, None otherwise
        """
        stmt = select(Task).where(Task.id == task_id)
        if with_documents:
            stmt = stmt.options(
                joinedload(Task.specification),
                joinedload(Task.implementation_plan),
                joinedload(Task.change_summary),
                joinedload(Task.implementation_plan_structured).joinedload(ImplementationPlan.steps),
            )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(self) -> list[Task]:
        """Get all tasks."""
        return self.get_list()

    def get_for_project(self, project_id: int) -> list[Task]:
        """Get all tasks for a specific project."""
        return self.get_list(project_id=project_id)

    def get_list(
        self,
        *,
        project_id: int | None = None,
        statuses: list[TaskStatus] | None = None,
        with_project: bool = False,
        include_initiative_tasks: bool = False,
        order_by_updated_desc: bool = False,
        limit: int | None = None,
    ) -> list[Task]:
        """Get tasks with optional filtering.

        Args:
            project_id: Optional project ID to filter by
            statuses: Optional list of task statuses to filter by
            with_project: If True, eager load the project relationship
            include_initiative_tasks: If True and project_id is set, also include tasks
                from initiatives under the given project_id
            order_by_updated_desc: If True, order results by updated_at descending
            limit: Optional maximum number of results to return
        """
        stmt = select(Task)
        if project_id is not None:
            if include_initiative_tasks:
                stmt = stmt.where(
                    or_(
                        Task.project_id == project_id,
                        Task.initiative.has(Initiative.project_id == project_id),
                    )
                )
            else:
                stmt = stmt.where(Task.project_id == project_id)
        if statuses:
            stmt = stmt.where(Task.status.in_(statuses))
        if with_project:
            stmt = stmt.options(joinedload(Task.project))
        if order_by_updated_desc:
            stmt = stmt.order_by(Task.updated_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all())

    def update(self, task: Task) -> Task:
        """Update an existing task.

        Args:
            task: Task instance to update

        Returns:
            Updated task
        """
        self.db.merge(task)
        return task

    def delete_implementation_plan_structured(self, task: Task) -> None:
        """Delete the structured implementation plan for a task if it exists.

        Args:
            task: Task whose structured plan should be deleted
        """
        if task.implementation_plan_structured:
            self.db.delete(task.implementation_plan_structured)
            self.db.flush()

    def delete(self, task: Task) -> None:
        """Delete a task entity.

        Args:
            task: Task instance to delete
        """
        self.db.delete(task)
        self.db.flush()

    def get_tasks_with_active_conversations(self, codebase_id: int | None = None) -> list[Task]:
        """Get tasks that have active conversations.

        Args:
            codebase_id: Optional codebase ID to filter by
        """

        stmt = (
            select(Task)
            .join(Conversation, Conversation.parent_entity_id == Task.id)
            .where(
                Conversation.parent_entity_type == ParentEntityType.TASK,
                Conversation.is_active == True,  # noqa: E712
            )
        )

        if codebase_id is not None:
            stmt = stmt.where(Task.codebase_id == codebase_id)

        return list(self.db.execute(stmt).scalars().all())

    def get_tasks_with_open_prs(self, codebase_ids: list[int]) -> list[Task]:
        """Get tasks that have a GitHub PR number set, filtered by codebase IDs."""
        stmt = select(Task).where(
            Task.github_pr_number.isnot(None),
            Task.codebase_id.in_(codebase_ids),
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_status(self, project_id: int | None = None) -> dict[TaskStatus, int]:
        """Count tasks grouped by status, optionally filtered by project."""
        stmt = select(Task.status, func.count(Task.id)).group_by(Task.status)
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        rows = self.db.execute(stmt).all()
        return {row[0]: row[1] for row in rows}

    def get_archived_paginated(
        self,
        project_id: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]:
        """Get paginated COMPLETE tasks ordered by created_at descending.

        Returns the page of tasks and the total count of matching tasks.
        """
        base_stmt = select(Task).where(Task.status == TaskStatus.COMPLETE)
        if project_id is not None:
            base_stmt = base_stmt.where(Task.project_id == project_id)

        total: int = self.db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

        offset = (page - 1) * page_size
        data_stmt = (
            base_stmt.options(joinedload(Task.project), joinedload(Task.initiative))
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        tasks = list(self.db.execute(data_stmt).unique().scalars().all())
        return tasks, total

    def get_tasks_filtered(
        self,
        project_id: int | None = None,
        status_filter: list[TaskStatus] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        codebase_name: str | None = None,
        limit: int | None = None,
    ) -> list[Task]:
        stmt = select(Task)
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)

        if status_filter:
            stmt = stmt.where(Task.status.in_(status_filter))

        if created_after:
            stmt = stmt.where(Task.created_at >= created_after)
        if created_before:
            stmt = stmt.where(Task.created_at <= created_before)

        if codebase_name:
            stmt = stmt.join(Codebase, Task.codebase_id == Codebase.id).where(Codebase.name == codebase_name)

        stmt = stmt.options(joinedload(Task.codebase)).order_by(Task.updated_at.desc())

        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.db.execute(stmt).unique().scalars().all())
