"""Service for managing conversations across multiple agent engines.

Provides a unified interface for retrieving conversation messages regardless
of the underlying engine (PydanticAI, Claude Code, Gemini CLI).
"""

from devboard.agents.agent_engines import AgentEngine
from devboard.agents.claude_code.session import ClaudeCodeSessionService
from devboard.api.schemas.agent_conversation import ConversationMessage, MessageRole
from devboard.db.models import Conversation, MessageType
from devboard.db.repositories.conversation import ConversationRepository


class ConversationService:
    """Unified service for managing conversations across all engines."""

    def __init__(self, conversation_repo: ConversationRepository):
        """Initialize service with conversation repository.

        Args:
            conversation_repo: Repository for conversation database operations
        """
        self.conversation_repo = conversation_repo

    async def get_conversation_messages(
        self,
        conversation: Conversation,
    ) -> list[ConversationMessage]:
        """Retrieve messages for a conversation regardless of engine.

        For PydanticAI conversations, messages are queried from the database.
        For external engines (Claude Code, Gemini CLI), messages are loaded
        from their respective session storage by searching ~/.claude/projects.

        Args:
            conversation: The conversation to get messages for

        Returns:
            List of ConversationMessage instances in chronological order

        Raises:
            ValueError: If conversation is missing required fields
            NotImplementedError: If engine is not yet supported
        """
        if conversation.engine == AgentEngine.INTERNAL:
            # Query database for messages
            db_messages = self.conversation_repo.get_messages(
                conversation.id,
                exclude_tool_calls=True,  # Only return user/agent text messages
            )
            return [
                ConversationMessage(
                    id=msg.id,
                    role=MessageRole.USER if msg.message_type == MessageType.USER_PROMPT else MessageRole.AGENT,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
                for msg in db_messages
            ]

        elif conversation.engine == AgentEngine.CLAUDE_CODE:
            # Use ClaudeCodeSessionService to read JSONL
            if not conversation.external_session_id:
                raise ValueError("Claude Code conversation missing external_session_id")

            # Service searches across all project directories in ~/.claude/projects
            service = ClaudeCodeSessionService()
            return service.load_conversation_history(conversation.external_session_id)

        elif conversation.engine == AgentEngine.GEMINI_CLI:
            # Future: Implement Gemini session loading
            raise NotImplementedError("Gemini CLI not yet supported")

        else:
            raise ValueError(f"Unknown engine: {conversation.engine}")
