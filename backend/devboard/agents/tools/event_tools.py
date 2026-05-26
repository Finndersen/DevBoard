"""Tools for querying and creating log entry events."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field
from pydantic_ai import ModelRetry, Tool

from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.services.log_entry_service import LogEntryService


def create_query_events_tool(log_entry_service: LogEntryService, background_agent: BackgroundAgent) -> Tool:
    """Create a tool for querying log entries with filtering."""

    async def query_events(
        project_id: Annotated[
            int | None,
            Field(description="Filter by project ID. Defaults to the agent's own project if omitted."),
        ] = None,
        task_id: Annotated[int | None, Field(description="Filter by task ID.")] = None,
        type_pattern: Annotated[
            str | None,
            Field(description='Filter by event type using glob-style wildcards (e.g., "task.*", "*.completed").'),
        ] = None,
        since: Annotated[
            str | None,
            Field(description="Return only events after this ISO 8601 datetime (e.g., '2024-01-15T10:00:00Z')."),
        ] = None,
        until: Annotated[str | None, Field(description="Return only events before this ISO 8601 datetime.")] = None,
        status: Annotated[
            str | None,
            Field(
                description='Filter by event lifecycle status. Values: "active" (open), "resolved" (closed), "superseded" (replaced by a newer event).'
            ),
        ] = None,
        source: Annotated[
            str | None,
            Field(
                description='Filter by who created the event. Values: "developer" (user actions), "system" (automated), "agent" (AI agent).'
            ),
        ] = None,
        pinned: Annotated[
            bool | None, Field(description="Filter by pinned status. Pinned events are highlighted for attention.")
        ] = None,
        limit: Annotated[int, Field(description="Maximum number of events to return.")] = 50,
        offset: Annotated[int, Field(description="Number of events to skip for pagination.")] = 0,
    ) -> str:
        """Query the event stream with optional filters.

        The event stream is a structured log of activities across the DevBoard system.
        Events have dot-notation types (e.g., "task.started", "build.failed"), a source
        (developer/system/agent), a lifecycle status (active/resolved/superseded), and
        optional project/task associations. Results are returned newest-first as a CSV table.
        """
        # Auto-inject project_id if not provided
        if project_id is None:
            project_id = background_agent.project_id

        # Parse ISO datetime strings
        parsed_since: datetime | None = None
        if since is not None:
            try:
                parsed_since = datetime.fromisoformat(since)
            except ValueError as e:
                raise ModelRetry(f"Invalid 'since' datetime format: {since}. Expected ISO format.") from e

        parsed_until: datetime | None = None
        if until is not None:
            try:
                parsed_until = datetime.fromisoformat(until)
            except ValueError as e:
                raise ModelRetry(f"Invalid 'until' datetime format: {until}. Expected ISO format.") from e

        # Parse status enum
        parsed_status: LogEntryStatus | None = None
        if status is not None:
            try:
                parsed_status = LogEntryStatus(status)
            except ValueError as e:
                valid = ", ".join(s.value for s in LogEntryStatus)
                raise ModelRetry(f"Invalid status: '{status}'. Valid values: {valid}") from e

        # Parse source enum
        parsed_source: LogEntrySource | None = None
        if source is not None:
            try:
                parsed_source = LogEntrySource(source)
            except ValueError as e:
                valid = ", ".join(s.value for s in LogEntrySource)
                raise ModelRetry(f"Invalid source: '{source}'. Valid values: {valid}") from e

        # Query log entries
        entries = log_entry_service.query_log_entries(
            project_id=project_id,
            task_id=task_id,
            type_pattern=type_pattern,
            since=parsed_since,
            until=parsed_until,
            status=parsed_status,
            source=parsed_source,
            pinned=pinned,
            limit=limit,
            offset=offset,
        )

        if not entries:
            return "Found 0 events matching the filters."

        # Format as CSV-style table
        overflow_note = (
            f"\n\nNote: {limit} results returned (the limit). There may be additional events not shown — increase limit or use offset to paginate."
            if len(entries) == limit
            else ""
        )
        lines = [f"Found {len(entries)} events (showing {len(entries)}):"]
        lines.append("id,timestamp,type,source,status,project_id,task_id,pinned,content")

        for entry in entries:
            # Truncate content to ~200 chars
            content = entry.content
            if len(content) > 200:
                content = content[:200] + "..."

            # Escape quotes and newlines in content for CSV
            content = content.replace('"', '""').replace("\n", "\\n")

            timestamp_str = entry.timestamp.isoformat()
            project_id_str = str(entry.project_id) if entry.project_id is not None else ""
            task_id_str = str(entry.task_id) if entry.task_id is not None else ""
            pinned_str = "true" if entry.pinned else "false"

            lines.append(
                f"{entry.id},{timestamp_str},{entry.type},{entry.source.value},"
                f'{entry.status.value},{project_id_str},{task_id_str},{pinned_str},"{content}"'
            )

        return "\n".join(lines) + overflow_note

    return Tool(function=query_events, name="query_events")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_create_event_tool(
    log_entry_service: LogEntryService,
    background_agent: BackgroundAgent,
    agent_run_repo: BackgroundAgentRunRepository,
    conversation_id: int | None,
) -> Tool:
    """Create a tool for emitting new log entry events."""

    async def create_event(
        event_type: Annotated[
            str,
            Field(
                description='Dot-notation type identifier for the event (e.g., "task.started", "analysis.complete", "alert.threshold_exceeded"). Use a consistent, descriptive naming scheme.'
            ),
        ],
        content: Annotated[
            str,
            Field(
                description="Human-readable description of the event. This is the primary text visible to users and other agents."
            ),
        ],
        project_id: Annotated[
            int | None,
            Field(description="Project to associate the event with. Defaults to the agent's own project if omitted."),
        ] = None,
        task_id: Annotated[int | None, Field(description="Task to associate the event with, if relevant.")] = None,
        metadata: Annotated[
            dict[str, Any] | None,
            Field(
                description="Arbitrary structured data to attach to the event. Agent identity (agent_id, agent_name, agent_run_id) is automatically merged in."
            ),
        ] = None,
        pinned: Annotated[
            bool,
            Field(
                description="Pin this event to flag it for attention. Use sparingly for significant milestones or alerts."
            ),
        ] = False,
    ) -> str:
        """Emit a new event into the shared event stream.

        Events are written with source='agent' and status='active'. The agent's identity
        (agent_id, agent_name, agent_run_id) is automatically added to the event metadata.
        """
        # Auto-inject project_id if not provided
        if project_id is None:
            project_id = background_agent.project_id

        # Resolve the current agent run ID from the conversation
        agent_run_id: int | None = None
        if conversation_id is not None:
            run = agent_run_repo.get_by_conversation_id(conversation_id)
            if run is not None:
                agent_run_id = run.id

        # Merge metadata with agent identity
        merged_metadata = {
            "agent_id": background_agent.id,
            "agent_name": background_agent.name,
            "agent_run_id": agent_run_id,
            **(metadata or {}),
        }

        # Create the log entry with source=AGENT
        entry = log_entry_service.create_log_entry(
            source=LogEntrySource.AGENT,
            type=event_type,
            content=content,
            project_id=project_id,
            task_id=task_id,
            entry_metadata=merged_metadata,
            status=LogEntryStatus.ACTIVE,
            pinned=pinned,
        )

        return f"Event created successfully with ID {entry.id}"

    return Tool(function=create_event, name="create_event")  # ty:ignore[invalid-argument-type, invalid-return-type]
