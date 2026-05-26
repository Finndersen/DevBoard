"""BackgroundAgentRunner service for pre-execution setup of background agent runs."""

import json
from typing import Any, Literal

from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles import AgentRoleType
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from devboard.db.models.enums import EntityType
from devboard.db.models.log_entry import LogEntry
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.db.repositories.conversation import ConversationRepository

TriggerSource = Literal["manual", "schedule", "event"]


def _assemble_initial_message(
    triggered_by: TriggerSource,
    state: dict[str, Any],
    input_message: str | None,
    trigger_event: LogEntry | None,
) -> str:
    parts: list[str] = [f"Trigger type: {triggered_by}"]

    if trigger_event is not None:
        event_data: dict[str, Any] = {
            "type": trigger_event.type,
            "content": trigger_event.content,
            "source": trigger_event.source,
            "timestamp": trigger_event.timestamp.isoformat(),
        }
        if trigger_event.entry_metadata:
            event_data["metadata"] = trigger_event.entry_metadata
        parts.append(f"Triggering event:\n{json.dumps(event_data, indent=2)}")

    if input_message is not None:
        parts.append(f"Input message:\n{input_message}")

    parts.append(f"Current state:\n{json.dumps(state, indent=2)}")

    return "\n\n".join(parts)


class BackgroundAgentRunner:
    """Handles pre-execution setup for background agent runs.

    Creates the necessary Conversation and BackgroundAgentRun records,
    assembles the initial message, and fires off execution via the
    ConversationExecutionManager.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        agent_run_repo: BackgroundAgentRunRepository,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.agent_run_repo = agent_run_repo

    def trigger(
        self,
        agent: BackgroundAgent,
        triggered_by: TriggerSource,
        input_message: str | None = None,
        trigger_event: LogEntry | None = None,
    ) -> BackgroundAgentRun:
        """Set up and start a background agent run.

        Creates Conversation and BackgroundAgentRun records, assembles the
        initial message, and fires off execution as a background asyncio task.

        Returns:
            The created BackgroundAgentRun (contains run.id and run.conversation_id)
        """
        conversation = self.conversation_repo.create(
            parent_entity_type=EntityType.BACKGROUND_AGENT,
            parent_entity_id=agent.id,
            agent_role=AgentRoleType.BACKGROUND_AGENT,
            engine=agent.engine,
            model_id=agent.model_id,
        )

        run = self.agent_run_repo.create(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by=triggered_by,
            status=BackgroundAgentRunStatus.RUNNING,
            state_before=agent.state,
            trigger_event_id=trigger_event.id if trigger_event else None,
        )

        initial_message = _assemble_initial_message(
            triggered_by=triggered_by,
            state=agent.state,
            input_message=input_message,
            trigger_event=trigger_event,
        )

        try:
            get_execution_manager().start_agent_execution(conversation.id, initial_message)
        except ConversationBusyError:
            run.status = BackgroundAgentRunStatus.FAILED
            run.error = "Execution could not start: conversation already has an active execution"
            raise

        return run
