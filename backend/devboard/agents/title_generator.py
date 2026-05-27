"""Title generation utility using Claude Code client with structured output.

This module provides utilities for generating task titles and branch names from
user prompts using a minimal 1-shot Haiku agent with structured JSON output.
"""

import time

import logfire
from pydantic import BaseModel, Field

from devboard.agents.engines.claude_code.client import ClaudeClient
from devboard.agents.language_models import ModelType
from devboard.services.project_directory import get_devboard_home


class TaskGenerationResult(BaseModel):
    """Result from generating a task title and branch name."""

    title: str = Field(max_length=80, description="Concise, descriptive task title")
    branch_name: str = Field(
        max_length=40,
        pattern=r"^[a-z0-9-]+$",
        description="Kebab-case branch name",
    )
    model_type: ModelType = Field(
        description="Recommended model type for this task: "
        "fast (trivial/mechanical: typo fixes, config changes, single-line edits), "
        "standard (moderate: multi-file changes, feature additions with clear scope), "
        "advanced (complex: architectural changes, large scope, deep reasoning required)"
    )


class ConversationTitleResult(BaseModel):
    """Result from generating a conversation title."""

    title: str = Field(max_length=60, description="Short, descriptive conversation title")


async def generate_task_title_and_branch(prompt: str) -> TaskGenerationResult:
    """Generate a task title, branch name, and recommended model type from a user prompt.

    Uses a minimal Haiku agent with structured JSON output to create:
    - A concise, descriptive task title (max 80 characters)
    - A kebab-case branch name (max 40 characters)
    - A recommended model type (fast/standard/advanced)

    Args:
        prompt: The user's task prompt/description

    Returns:
        TaskGenerationResult with title, branch_name, and model_type fields

    Example:
        >>> result = await generate_task_title_and_branch("Add user authentication to the API")
        >>> print(result.title)
        "Add user authentication to API"
        >>> print(result.branch_name)
        "add-user-authentication-api"
        >>> print(result.model_type)
        "advanced"
    """
    system_prompt = "You are a task title, branch name, and model type generator."

    user_message = f"""Generate a task title, branch name, and model type from the user prompt below.

Guidelines for title and branch name:
- Title should be concise and actionable (maximum 80 characters), starting with a verb when possible
- Branch name should be lowercase, kebab-case, maximum 40 characters, no prefixes like "feat/" or "fix/"
- Focus on the main action/outcome, not implementation details

Guidelines for model type selection:
- "fast": Trivial or mechanical changes only. Examples: typo fixes, simple config changes, single-line edits
- "standard": Moderate complexity. Examples: multi-file changes, feature additions with clear scope, refactoring
- "advanced": Complex tasks requiring deep reasoning. Examples: architectural changes, large scope, significant refactoring, complex bug fixes

Respond immediately using the structured output tool. Do not include any other text in your response.

## User Prompt

{prompt}"""

    try:
        client = ClaudeClient(
            system_prompt=system_prompt,
            model="haiku",
            cwd=str(get_devboard_home()),
            load_settings=False,
            sandbox_enabled=False,
            output_model=TaskGenerationResult,
            effort="low",
            load_extra_mcp_servers=False,
        )

        result = await client.run(user_message)

        if result.structured_output is not None:
            assert isinstance(result.structured_output, TaskGenerationResult)
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
    return TaskGenerationResult(title=fallback_title, branch_name=f"task-{timestamp}", model_type=ModelType.STANDARD)


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
            load_extra_mcp_servers=False,
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
