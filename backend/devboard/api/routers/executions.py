"""Router for listing active background agent executions."""

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from devboard.agents.execution_manager import ExecutionStatus, conversation_execution_manager
from devboard.db.database import get_db
from devboard.db.models import ParentEntityType
from devboard.db.repositories import ConversationRepository, TaskRepository

router = APIRouter()


class ActiveExecutionItem(BaseModel):
    """A currently-running agent execution."""

    conversation_id: int
    status: ExecutionStatus
    started_at: datetime.datetime
    parent_entity_type: str
    agent_role: str
    task_id: int | None = None
    task_title: str | None = None


class ActiveExecutionsResponse(BaseModel):
    executions: list[ActiveExecutionItem]


@router.get("/active", response_model=ActiveExecutionsResponse)
async def list_active_executions(
    db: Session = Depends(get_db),
) -> ActiveExecutionsResponse:
    """List all currently running background agent executions.

    Returns execution metadata enriched with conversation and task information.
    """
    running = conversation_execution_manager.list_active_executions()
    if not running:
        return ActiveExecutionsResponse(executions=[])

    conversation_repo = ConversationRepository(db)
    task_repo = TaskRepository(db)

    items: list[ActiveExecutionItem] = []
    for execution in running:
        conversation = conversation_repo.get_by_id(execution.conversation_id)
        if not conversation:
            continue

        task_id: int | None = None
        task_title: str | None = None
        if conversation.parent_entity_type == ParentEntityType.TASK:
            task = task_repo.get_by_id(conversation.parent_entity_id)
            if task:
                task_id = task.id
                task_title = task.title

        items.append(
            ActiveExecutionItem(
                conversation_id=execution.conversation_id,
                status=execution.status,
                started_at=execution.started_at,
                parent_entity_type=conversation.parent_entity_type.value,
                agent_role=conversation.agent_role.value,
                task_id=task_id,
                task_title=task_title,
            )
        )

    return ActiveExecutionsResponse(executions=items)
