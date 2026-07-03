"""Conversation history service for the Codex engine.

Codex manages its own thread history internally via the codex CLI process.
DevBoard does not store Codex conversation events in the database, so this
service returns empty history and relies on the Codex thread ID for context.
"""

from devboard.agents.conversation_history import ConversationHistory, ConversationHistoryService


class CodexConversationHistoryService(ConversationHistoryService):
    """Returns empty conversation history for Codex conversations.

    Codex maintains its own thread state via the CLI subprocess. History
    is not retrievable by DevBoard — the thread ID stored as external_session_id
    is sufficient for Codex to resume context on subsequent turns.
    """

    async def get_conversation_history(self) -> ConversationHistory:
        return ConversationHistory()
