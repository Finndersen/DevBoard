"""Task-specific conversation service implementation."""

from typing import Any

from devboard.services.agent_conversation import AgentConversationService


class TaskConversationService(AgentConversationService):
    """Task-specific conversation service implementation."""

    async def _process_with_agent(
        self, agent_service, message: str, history: list, **kwargs
    ) -> tuple[Any, Any]:
        """Process message with task planning agent."""
        # Extract entity_id and pass as task_id
        entity_id = kwargs.pop("entity_id", None)
        return await agent_service.process_message_with_state(
            task_id=entity_id, message_history=history, user_message=message, **kwargs
        )

    async def _process_tool_approval_with_agent(
        self, agent_service, deferred_results: Any, history: list, **kwargs
    ) -> Any:
        """Process tool approval with task planning agent."""
        # Extract entity_id and pass as task_id
        entity_id = kwargs.pop("entity_id", None)
        return await agent_service.process_tool_approval_with_state(
            task_id=entity_id, deferred_results=deferred_results, message_history=history, **kwargs
        )


# Global service instance
task_conversation_service = TaskConversationService()
