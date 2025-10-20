"""Registry for prompt actions.

Prompt actions are reusable, named operations that can be triggered to send
predefined prompts to agent conversations.
"""

from dataclasses import dataclass

from devboard.core.registry import Registry


@dataclass(frozen=True)
class PromptAction:
    """A reusable prompt action that can be triggered in conversations.

    Attributes:
        key: Unique identifier for the action (e.g., "task.create_implementation_plan")
        prompt_template: The prompt text to send to the agent
        description: Human-readable description for UI display
    """

    key: str
    prompt_template: str
    description: str


# Hardcoded prompt actions
_PROMPT_ACTIONS = [
    PromptAction(
        key="task.create_implementation_plan",
        prompt_template=(
            "The task specification is complete. Your goal is now to create a detailed technical implementation plan."
        ),
        description="Generate a technical implementation plan from the task specification",
    ),
    PromptAction(
        key="task.begin_implementation",
        prompt_template=(
            "The implementation plan has been approved. Your goal is to write the code to fulfill the plan."
        ),
        description="Start implementing the approved plan",
    ),
]


# Global registry instance
prompt_action_registry = Registry(_PROMPT_ACTIONS, key_attr="key")
