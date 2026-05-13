"""Title generation utility using Claude Code client with structured output.

This module provides utilities for generating task titles and branch names from
user prompts using a minimal 1-shot Haiku agent with structured JSON output.
"""

import time

import logfire
from pydantic import BaseModel, Field

from devboard.agents.engines.claude_code.client import ClaudeClient
from devboard.services.project_directory import get_devboard_home


class TaskTitleResult(BaseModel):
    """Result from generating a task title and branch name."""

    title: str = Field(max_length=80, description="Concise, descriptive task title")
    branch_name: str = Field(
        max_length=40,
        pattern=r"^[a-z0-9-]+$",
        description="Kebab-case branch name",
    )


class ConversationTitleResult(BaseModel):
    """Result from generating a conversation title."""

    title: str = Field(max_length=60, description="Short, descriptive conversation title")


async def generate_task_title_and_branch(prompt: str) -> TaskTitleResult:
    """Generate a task title and branch name from a user prompt.

    Uses a minimal Haiku agent with structured JSON output to create:
    - A concise, descriptive task title (max 80 characters)
    - A kebab-case branch name (max 40 characters)

    Args:
        prompt: The user's task prompt/description

    Returns:
        TaskTitleResult with title and branch_name fields

    Example:
        >>> result = await generate_task_title_and_branch("Add user authentication to the API")
        >>> print(result.title)
        "Add user authentication to API"
        >>> print(result.branch_name)
        "add-user-authentication-api"
    """
    system_prompt = """You are a task title and branch name generator. Given a user prompt describing a task, generate:

1. A concise, descriptive task title (maximum 80 characters)
2. A kebab-case branch name (maximum 40 characters, no prefixes like "feat/" or "fix/")

Guidelines:
- Title should be clear and actionable, starting with a verb when possible
- Branch name should be lowercase, kebab-case, and descriptive
- Focus on the main action/outcome, not implementation details
- Keep both short but informative

Respond immediately using the structured output tool. Do not include any other text in your response."""

    try:
        client = ClaudeClient(
            system_prompt=system_prompt,
            model="haiku",
            cwd=str(get_devboard_home()),
            load_settings=False,
            sandbox_enabled=False,
            output_model=TaskTitleResult,
            effort="low",
        )

        result = await client.run(prompt)

        if result.structured_output is not None:
            assert isinstance(result.structured_output, TaskTitleResult)
            return result.structured_output

        logfire.warn(
            "Title generation: structured output missing, using fallback",
            prompt_preview=prompt[:100],
        )

    except Exception as e:
        logfire.error("Title generation failed, using fallback", error=str(e), prompt_preview=prompt[:100])

    # Fallback: generate generic title and branch name
    timestamp = int(time.time())
    fallback_title = prompt[:77] + "..." if len(prompt) > 80 else prompt
    return TaskTitleResult(title=fallback_title, branch_name=f"task-{timestamp}")


async def generate_conversation_title(prompt: str) -> str:
    """Generate a conversation title from a user prompt.

    Uses a minimal Haiku agent with structured JSON output to create
    a short, descriptive conversation title.

    Args:
        prompt: The user's initial conversation prompt/message

    Returns:
        A descriptive conversation title string

    Example:
        >>> title = await generate_conversation_title("Can you help me debug the login flow?")
        >>> print(title)
        "Debug login flow"
    """
    system_prompt = """You are a conversation title generator. Given a user prompt that starts a conversation, generate a short, descriptive title that captures the main topic or question.

Guidelines:
- Keep it concise (maximum 60 characters)
- Focus on the main topic/action
- Remove unnecessary words like "Can you help me", "I need to", etc.
- Use title case
- Make it specific enough to distinguish from other conversations

Respond immediately using the structured output tool. Do not include any other text in your response."""

    try:
        client = ClaudeClient(
            system_prompt=system_prompt,
            model="haiku",
            cwd=str(get_devboard_home()),
            load_settings=False,
            sandbox_enabled=False,
            output_model=ConversationTitleResult,
            effort="low",
        )

        result = await client.run(prompt)

        if result.structured_output is not None:
            assert isinstance(result.structured_output, ConversationTitleResult)
            return result.structured_output.title

        logfire.warn(
            "Conversation title generation: structured output missing, using fallback",
            prompt_preview=prompt[:100],
        )

    except Exception as e:
        logfire.error("Conversation title generation failed, using fallback", error=str(e), prompt_preview=prompt[:100])

    # Fallback: use first 57 chars of prompt
    fallback_title = prompt[:57] + "..." if len(prompt) > 60 else prompt
    return fallback_title
