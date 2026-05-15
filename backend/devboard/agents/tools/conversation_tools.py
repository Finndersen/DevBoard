"""Tools for inspecting conversations and agent configurations."""

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_assembly import assemble_agent_config
from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.conversation_history import create_conversation_history_service
from devboard.agents.engines.claude_code.client import ClaudeClient
from devboard.agents.events import (
    AgentRunCompletedEvent,
    AgentRunStartedEvent,
    ConversationEvent,
    LocalCommand,
    MessageRole,
    MetaMessage,
    SystemEvent,
    TextMessage,
    ThinkingEvent,
    ToolCall,
    ToolCallRequest,
    ToolResult,
)
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.task_service import TaskService

_MAX_TEXT_LEN = 500
_MAX_ARG_LEN = 200


def _truncate(text: str, max_len: int = _MAX_TEXT_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _format_tool_args(args: dict[str, Any] | None) -> str:
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        v_str = json.dumps(v) if not isinstance(v, str) else v
        parts.append(f"{k}={_truncate(v_str, _MAX_ARG_LEN)}")
    return ", ".join(parts)


def _fmt_ts(ts: Any) -> str:
    return ts.strftime("%Y-%m-%d %H:%M") if ts else "unknown"


def _format_events(
    events: list[ConversationEvent], include_thinking: bool, tool_result_max_length: int = _MAX_ARG_LEN
) -> str:
    lines = []
    for event in events:
        if isinstance(event, (ToolCallRequest, AgentRunStartedEvent, AgentRunCompletedEvent)):
            continue
        ts = _fmt_ts(event.timestamp)
        if isinstance(event, TextMessage):
            role = event.role.value.upper()
            lines.append(f"[{ts}] {role}: {_truncate(event.text_content)}")
        elif isinstance(event, ToolCall):
            args_str = _format_tool_args(event.tool_args)
            line = f"[{ts}] TOOL_CALL {event.tool_name}"
            if args_str:
                line += f": {args_str}"
            lines.append(line)
        elif isinstance(event, ToolResult):
            if tool_result_max_length == 0:
                continue  # Skip tool results entirely when tool_result_max_length is 0
            result = _truncate(event.result_content, tool_result_max_length)
            lines.append(f"  → RESULT: {result}")
        elif isinstance(event, SystemEvent):
            data_str = json.dumps(event.data) if event.data else ""
            line = f"[{ts}] SYSTEM [{event.sub_type}]"
            if data_str:
                line += f": {data_str}"
            lines.append(line)
        elif isinstance(event, ThinkingEvent):
            if include_thinking and event.thinking_text:
                lines.append(f"[{ts}] THINKING: {_truncate(event.thinking_text)}")
        elif isinstance(event, MetaMessage):
            lines.append(f"[{ts}] META [{event.meta_type}]: {_truncate(event.text_content)}")
        elif isinstance(event, LocalCommand):
            cmd = _truncate(event.command, _MAX_ARG_LEN)
            line = f"[{ts}] CMD [{event.command_type}]: {cmd}"
            if event.output:
                line += f" → {_truncate(event.output, _MAX_ARG_LEN)}"
            lines.append(line)
    if not lines:
        return "No conversation content found."
    return "\n".join(lines)


def create_list_conversations_tool(conversation_repo: ConversationRepository) -> Tool:
    """Create a tool for listing active top-level conversations with metadata."""

    async def list_conversations(
        parent_entity_type: str | None = None,
        parent_entity_id: int | None = None,
        agent_role: str | None = None,
        is_running: bool | None = None,
        max_results: int = 20,
    ) -> str:
        """List active top-level conversations with metadata.

        Args:
            parent_entity_type: Optional filter by parent entity type.
                Valid values: 'project', 'task', 'codebase', 'background_agent'
            parent_entity_id: Optional filter by parent entity ID.
            agent_role: Optional filter by agent role.
                Valid values: 'project', 'task_planning', 'task_implementation',
                'task_pr_review', 'investigation', 'code_review', 'step_execution', 'background_agent'
            is_running: Optional filter by whether the conversation has an active execution.
            max_results: Maximum number of conversations to return (default: 20).

        Returns:
            Formatted list of conversations with key metadata fields.
        """
        parsed_entity_type: ParentEntityType | None = None
        if parent_entity_type is not None:
            try:
                parsed_entity_type = ParentEntityType(parent_entity_type)
            except ValueError as e:
                valid = ", ".join(t.value for t in ParentEntityType)
                raise ModelRetry(f"Invalid parent_entity_type: '{parent_entity_type}'. Valid values: {valid}") from e

        parsed_agent_role: AgentRoleType | None = None
        if agent_role is not None:
            try:
                parsed_agent_role = AgentRoleType(agent_role)
            except ValueError as e:
                valid = ", ".join(r.value for r in AgentRoleType)
                raise ModelRetry(f"Invalid agent_role: '{agent_role}'. Valid values: {valid}") from e

        rows = conversation_repo.get_all_top_level(
            parent_entity_type=parsed_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=parsed_agent_role,
        )

        manager = get_execution_manager()
        results = []
        for row in rows:
            conv = row["conversation"]
            running = manager.has_active_execution(conv.id)
            if is_running is not None and running != is_running:
                continue
            results.append((row, running))

        results = results[:max_results]

        if not results:
            return "No conversations found matching the filters."

        lines = []
        for row, running in results:
            conv = row["conversation"]
            entity_type = conv.parent_entity_type.value
            entity_name = row["parent_entity_name"]
            project_name = row["project_name"]

            parent_desc = f'{entity_type} #{conv.parent_entity_id} "{entity_name}"'
            if project_name:
                parent_desc += f' (project: "{project_name}")'

            title_part = f' title="{conv.title}"' if conv.title else ""
            model_part = conv.model_id or "default"
            last_activity = _fmt_ts(conv.last_activity_at)

            lines.append(
                f"[{conv.id}]{title_part} {parent_desc}"
                f" | role: {conv.agent_role.value}"
                f" | engine: {conv.engine.value}"
                f" | model: {model_part}"
                f" | active: {'yes' if conv.is_active else 'no'}"
                f" | running: {'yes' if running else 'no'}"
                f" | last_activity: {last_activity}"
            )

        return "\n".join(lines)

    return Tool(function=list_conversations, name="list_conversations")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_view_conversation_details_tool(conversation_repo: ConversationRepository) -> Tool:
    """Create a tool for viewing metadata of a single conversation."""

    async def view_conversation_details(conversation_id: int) -> str:
        """View metadata for a single conversation.

        Args:
            conversation_id: The ID of the conversation to view.

        Returns:
            Formatted conversation metadata including all scalar fields.
        """
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ModelRetry(f"Conversation with ID {conversation_id} not found.")

        running = get_execution_manager().has_active_execution(conversation_id)

        lines = [
            f"ID: {conversation.id}",
            f"Title: {conversation.title or '(none)'}",
            f"Parent Entity Type: {conversation.parent_entity_type.value}",
            f"Parent Entity ID: {conversation.parent_entity_id}",
            f"Parent Conversation ID: {conversation.parent_conversation_id or '(none)'}",
            f"Agent Role: {conversation.agent_role.value}",
            f"Engine: {conversation.engine.value}",
            f"Model: {conversation.model_id or 'default'}",
            f"Is Active: {'yes' if conversation.is_active else 'no'}",
            f"Is Running: {'yes' if running else 'no'}",
            f"Created At: {_fmt_ts(conversation.created_at)}",
            f"Last Activity At: {_fmt_ts(conversation.last_activity_at)}",
        ]

        return "\n".join(lines)

    return Tool(function=view_conversation_details, name="view_conversation_details")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_view_conversation_content_tool(conversation_repo: ConversationRepository) -> Tool:
    """Create a tool for viewing the event history of a conversation."""

    async def view_conversation_content(
        conversation_id: int,
        include_thinking: bool = False,
        since_last_user_message: bool = False,
    ) -> str:
        """View conversation event history in a compact plain-text format.

        Args:
            conversation_id: The ID of the conversation to view.
            include_thinking: Whether to include agent thinking events (default: False).
            since_last_user_message: If True, only include events from the last user message
                onwards. Useful for inspecting a running agent's current turn.

        Returns:
            Token-efficient plain-text representation of conversation history.
            Includes user/agent messages, tool calls/results, and system events.
            Excludes ephemeral events (tool call requests, run start/end markers).
        """
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ModelRetry(f"Conversation with ID {conversation_id} not found.")

        try:
            history_service = create_conversation_history_service(conversation, conversation_repo)
        except HTTPException as e:
            raise ModelRetry(f"Cannot load conversation history: {e.detail}") from e

        history = await history_service.get_conversation_history()
        events = history.messages

        if since_last_user_message:
            last_user_idx = None
            for i in range(len(events) - 1, -1, -1):
                event = events[i]
                if isinstance(event, TextMessage) and event.role == MessageRole.USER:
                    last_user_idx = i
                    break
            if last_user_idx is not None:
                events = events[last_user_idx:]

        return _format_events(events, include_thinking)

    return Tool(function=view_conversation_content, name="view_conversation_content")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_inspect_conversation_tool(conversation_repo: ConversationRepository) -> Tool:
    """Create a tool for analyzing conversations using a Haiku sub-agent."""

    async def inspect_conversation(
        conversation_id: int,
        question: str | None = None,
        tool_result_max_length: int = 200,
        effort: Literal["low", "medium", "high"] | None = None,
    ) -> str:
        """Analyze a conversation using a Haiku sub-agent.

        Uses ClaudeClient with Haiku model to analyze conversation history.
        Can either provide a general summary or answer a specific question
        about the conversation.

        Args:
            conversation_id: The ID of the conversation to analyze.
            question: Optional specific question to ask about the conversation.
                If omitted, returns a concise summary of the conversation.
            tool_result_max_length: Maximum characters for tool result content
                in the formatted history (default: 200). Set to 0 to exclude
                tool results entirely.
            effort: Optional reasoning effort level for the analysis. Use to calibrate analysis depth based on question complexity:
                - `low`: Simple questions, straightforward summaries of conversation flow
                - `medium`: Moderate complexity, questions requiring understanding multiple interactions
                - `high`: Complex analysis, questions requiring synthesis across entire conversation or deep reasoning
                - `None` (default): Uses the `ClaudeClient`'s own default effort level

        Returns:
            Analysis or summary from the Haiku sub-agent.
        """
        # Load conversation
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ModelRetry(f"Conversation with ID {conversation_id} not found.")

        # Load conversation history
        try:
            history_service = create_conversation_history_service(conversation, conversation_repo)
        except HTTPException as e:
            raise ModelRetry(f"Cannot load conversation history: {e.detail}") from e

        history = await history_service.get_conversation_history()
        events = history.messages

        # Format conversation history
        formatted_history = _format_events(
            events, include_thinking=False, tool_result_max_length=tool_result_max_length
        )

        # Build system prompt
        system_prompt = (
            "You are analyzing a conversation transcript from an AI agent interaction. "
            "Review the provided conversation history and either answer the user's specific question "
            "or provide a concise summary of what happened. Focus on the key actions, outcomes, "
            "and any important context from the conversation."
        )

        # Build user message
        if question:
            user_message = (
                f"Please analyze this conversation and answer the following question: {question}\n\n{formatted_history}"
            )
        else:
            user_message = f"Please provide a concise summary of this conversation:\n\n{formatted_history}"

        # Create ClaudeClient and analyze
        client = ClaudeClient(
            system_prompt=system_prompt,
            model="haiku",
            cwd=str(Path.home() / ".devboard"),
            load_settings=False,
            effort=effort,
        )

        result = await client.run(user_message)
        return result.text_content

    return Tool(function=inspect_conversation, name="inspect_conversation")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_view_agent_config_tool(
    conversation_repo: ConversationRepository,
    document_repo: DocumentRepository,
    agent_config_service: AgentConfigService,
    integration_service: IntegrationService,
    task_service: TaskService,
) -> Tool:
    """Create a tool for viewing the assembled agent configuration for a conversation."""

    async def view_agent_config(conversation_id: int) -> str:
        """View the assembled agent configuration for a conversation.

        Returns the agent role, system prompt, context, custom instructions, and
        tool lists (names and descriptions only, without full input schemas).

        Args:
            conversation_id: The ID of the conversation to inspect.

        Returns:
            Formatted agent configuration including system prompt, context, and tools.
        """
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ModelRetry(f"Conversation with ID {conversation_id} not found.")

        config = await assemble_agent_config(
            conversation=conversation,
            document_repo=document_repo,
            agent_config_service=agent_config_service,
            integration_service=integration_service,
            task_service=task_service,
            conversation_repo=conversation_repo,
        )

        lines = [
            f"Agent Role: {config.agent_role}",
            f"Custom Instructions: {config.custom_instructions or '(none)'}",
            "",
            "=== Behaviour Guidelines ===",
            config.behaviour_guidelines,
            "",
            "=== Context Content ===",
            config.context_content or "(empty)",
        ]

        if config.role_tools:
            lines += ["", "=== Role Tools ==="]
            for tool in config.role_tools:
                desc = f": {tool.description}" if tool.description else ""
                lines.append(f"  - {tool.name}{desc}")

        if config.mcp_tools:
            lines += ["", "=== MCP Tools ==="]
            for tool in config.mcp_tools:
                server = f" (server: {tool.server_name})" if tool.server_name else ""
                desc = f": {tool.description}" if tool.description else ""
                lines.append(f"  - {tool.name}{desc}{server}")

        if config.builtin_tools:
            lines += ["", "=== Builtin Tools ==="]
            for tool in config.builtin_tools:
                lines.append(f"  - {tool.name}")

        return "\n".join(lines)

    return Tool(function=view_agent_config, name="view_agent_config")  # ty:ignore[invalid-argument-type, invalid-return-type]
