"""Tools for conversation context management: refocus and branch."""

from pydantic_ai import Tool

from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.system_message_tags import wrap_system_message
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService


def create_refocus_conversation_tool(
    conversation: Conversation,
    conversation_service: ConversationService,
    conversation_repo: ConversationRepository,
) -> Tool:
    """Create a tool that refocuses the conversation by starting a fresh seeded one."""

    async def refocus_conversation(context_summary: str, title: str, continuation_prompt: str) -> str:
        """Compact and refocus the conversation to continue with only relevant context.

        Creates a fresh conversation seeded with the provided context summary.
        The current conversation is archived and the agent continues seamlessly in the new one.
        Before calling this, save any important decisions or status to project/initiative documents.

        Args:
            context_summary: Focused summary of context relevant to the current topic
            title: Title for the new conversation
            continuation_prompt: What the agent should continue doing in the new conversation
        """
        new_conversation = conversation_service.create_seeded_conversation(conversation, title)
        conversation_repo.archive_conversation(conversation.id)
        conversation_repo.db.flush()

        seeded_message = f"{wrap_system_message(context_summary, 'continuation_context')}\n\n{continuation_prompt}"
        get_execution_manager().start_agent_execution(new_conversation.id, seeded_message)

        return f"REFOCUSED conversation_id={new_conversation.id}"

    return Tool(function=refocus_conversation, name="refocus_conversation")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_branch_conversation_tool(
    conversation: Conversation,
    conversation_service: ConversationService,
) -> Tool:
    """Create a tool that branches the conversation into a parallel investigation."""

    async def branch_conversation(context_summary: str, title: str, prompt: str) -> str:
        """Create a parallel conversation branch to independently investigate a specific topic.

        The branch runs autonomously with the provided context.
        This conversation continues independently.
        Use inspect_conversation to check on the branch later.

        Args:
            context_summary: Relevant context for the branched conversation
            title: Title for the branch conversation
            prompt: What the branched conversation should investigate/address
        """
        new_conversation = conversation_service.create_seeded_conversation(conversation, title)

        seeded_message = f"{wrap_system_message(context_summary, 'continuation_context')}\n\n{prompt}"
        get_execution_manager().start_agent_execution(new_conversation.id, seeded_message)

        return f"Branch conversation created (ID: {new_conversation.id}, title: '{title}'). Use inspect_conversation to check on it later."

    return Tool(function=branch_conversation, name="branch_conversation")  # ty:ignore[invalid-argument-type, invalid-return-type]
