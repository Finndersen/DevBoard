"""Tools for sending prompts to task agents and monitoring their execution status."""

from pydantic_ai import ModelRetry, Tool

from devboard.agents.conversation_history import create_conversation_history_service
from devboard.agents.events import TextMessage
from devboard.agents.execution.registry import get_execution_manager
from devboard.db.models import ParentEntityType, Project, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository, NoActiveConversationError
from devboard.services.task_service import TaskService


def create_send_task_agent_prompt_tool(
    project: Project,
    task_service: TaskService,
    conversation_repo: ConversationRepository,
) -> Tool:
    """Create a tool for sending a prompt to a task's agent conversation.

    Args:
        project: The project context (for security validation)
        task_service: Service for task operations
        conversation_repo: Repository for conversation access
    """

    async def send_task_agent_prompt(task_id: int, message: str) -> str:
        """Send a prompt to the active conversation of a task's agent, starting background execution.

        Use this tool to instruct a task agent to perform work (e.g. write a specification,
        create an implementation plan). The execution starts immediately in the background
        and this tool returns without waiting for it to complete.

        Args:
            task_id: The ID of the task whose agent to send the prompt to
            message: The prompt/instruction to send to the task agent

        Returns:
            Confirmation string with task_id, conversation_id, and status.
        """
        # Error handling strategy: raise ModelRetry for incorrect tool usage (task not found,
        # wrong project, invalid state), return error string for expected operational conditions
        # (no conversation set up, agent busy) so the LLM can decide how to respond.
        task = task_service.get_task_by_id(task_id)

        if not task:
            raise ModelRetry(f"Task with ID {task_id} not found.")

        if task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        if task.status == TaskStatus.COMPLETE:
            raise ModelRetry(f"Task {task_id} is already complete and cannot receive new agent prompts.")

        try:
            conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)
        except NoActiveConversationError:
            return f"Error: No active conversation found for task {task_id}. The task may not have an agent conversation set up."

        # Note: small check-then-act race window, acceptable for this low-concurrency context.
        if get_execution_manager().has_active_execution(conversation.id):
            return f"Error: Task {task_id} agent is already running (conversation {conversation.id}). Wait for it to finish before sending another prompt."

        get_execution_manager().start_agent_execution(conversation.id, message)

        return (
            f"Task agent prompt sent successfully.\n"
            f"task_id: {task_id}\n"
            f"conversation_id: {conversation.id}\n"
            f"status: running"
        )

    return Tool(function=send_task_agent_prompt, name="send_task_agent_prompt")


def create_get_task_agent_status_tool(
    project: Project,
    task_service: TaskService,
    conversation_repo: ConversationRepository,
) -> Tool:
    """Create a tool for checking a task agent's execution status and recent messages.

    Args:
        project: The project context (for security validation)
        task_service: Service for task operations
        conversation_repo: Repository for conversation access
    """

    async def get_task_agent_status(task_id: int, max_messages: int = 10) -> str:
        """Check the execution status of a task's agent and return recent text messages.

        Use this tool to monitor whether a task agent is still running or has finished,
        and to read its recent responses after sending it a prompt.

        Args:
            task_id: The ID of the task to check
            max_messages: Maximum number of recent messages to return (default: 10)

        Returns:
            Formatted string with status, agent role, and recent conversation messages.
        """

        task = task_service.get_task_by_id(task_id)

        if not task:
            raise ModelRetry(f"Task with ID {task_id} not found.")

        if task.project_id != project.id:
            raise ModelRetry(f"Task with ID {task_id} does not belong to this project.")

        try:
            conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)
        except NoActiveConversationError:
            return f"Error: No active conversation found for task {task_id}."

        status = "running" if get_execution_manager().has_active_execution(conversation.id) else "idle"

        history_service = create_conversation_history_service(conversation, conversation_repo)
        all_events = (await history_service.get_conversation_history()).messages

        text_messages = [e for e in all_events if isinstance(e, TextMessage)][-max_messages:]

        lines = [
            f"task_id: {task_id}",
            f"conversation_id: {conversation.id}",
            f"agent_role: {conversation.agent_role.value}",
            f"status: {status}",
            f"recent_messages ({len(text_messages)}):",
        ]

        for msg in text_messages:
            role_label = "user" if msg.role.value == "user" else "assistant"
            timestamp_str = msg.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
            lines.append(f"\n[{role_label}] @ {timestamp_str}")
            lines.append(msg.text_content)

        return "\n".join(lines)

    return Tool(function=get_task_agent_status, name="get_task_agent_status")
