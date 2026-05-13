"""Custom exceptions for agent execution."""


class AgentInterruptedError(Exception):
    """Raised by agents when an interrupt flag is detected during execution."""


class ConversationBusyError(Exception):
    """Raised when an agent execution is already active for a conversation."""

    def __init__(self, conversation_id: int):
        self.conversation_id = conversation_id
        super().__init__(f"Conversation {conversation_id} already has an active execution")


class SubAgentRateLimitError(Exception):
    """Raised when a sub-agent hits an API rate limit."""

    def __init__(self, message: str):
        super().__init__(message)
