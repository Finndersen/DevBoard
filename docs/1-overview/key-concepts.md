# Key Concepts

**Navigation**: [Documentation Home](../INDEX.md) > [Overview](./INDEX.md) > Key Concepts

## Core Domain Concepts

This document defines the fundamental abstractions and domain entities that DevBoard uses to organize development work and context. Understanding these concepts is essential for using and developing DevBoard.

## 1. Project

A **high-level container** representing a significant development initiative, analogous to a Jira Epic or GitHub milestone.

**Purpose**: Organize related work, maintain project-level documentation, and provide AI agents with comprehensive project context.

**Key Characteristics**:
- **Project Specification**: Central living document containing project overview, goals, and status
- **Context Sources**: Links to external resources (Slack channels, Notion pages, GitHub repos, Jira boards)
- **Task Organization**: Contains and organizes related development tasks
- **AI Interaction**: Supports conversational Q&A about project status and context

**Lifecycle**: Projects are long-lived containers that persist throughout initiative development and beyond.

## 2. Task

A **discrete unit of work** representing a specific development deliverable, often corresponding to a Jira ticket or GitHub issue.

**Purpose**: Break down projects into manageable work items with clear specifications and implementation plans.

**Lifecycle States**:
- **Planning** → **Implementing** → [**PR Open** →] **Merged** → **Complete**

**Key Characteristics**:
- **Task Specification**: Detailed requirements document developed collaboratively with AI
- **Implementation Plan**: Technical execution plan created through agent interaction
- **External Links**: References to Jira tickets, GitHub PRs, and other relevant resources
- **Context Awareness**: Access to project context plus task-specific resources

**State Transitions**: Tasks progress through well-defined states with different agent roles supporting each phase.

## 3. Codebase

A **local or remote code repository** that represents a software system relevant to projects and tasks.

**Purpose**: Provide AI agents with access to code structure, architecture, and development patterns.

**Key Characteristics**:
- **Architecture Documentation**: Living `ARCHITECTURE.md` files maintained by AI agents
- **Local Integration**: Direct access to local file systems for code analysis
- **Multi-Project Sharing**: Same codebase can be referenced by multiple projects
- **Version Awareness**: Understanding of Git history and branching strategies

**Integration**: Codebases are registered in DevBoard and linked to projects/tasks for context.

## 4. Context Provider

An **intelligent abstraction** that gathers and processes information from external sources to provide relevant context to AI agents.

**Purpose**: Transform raw data from external tools into actionable context for project and task management.

**Provider Types**:
- **GitHub**: Pull requests, issues, commits, repository structure
- **Jira**: Tickets, projects, workflows, comments
- **Slack**: Conversations, channels, thread discussions
- **Codebase**: Local file analysis, architecture documentation
- **Web Pages**: Documentation sites, technical resources

**Context Strategies**:
- **Eager Loading**: Small resources loaded immediately into agent context
- **On-Demand**: Large resources queried specifically when needed

## 5. Integration

A **technical connector** that provides authenticated access to external service APIs.

**Purpose**: Handle the low-level communication with external tools, managing authentication, rate limits, and error conditions.

**Responsibilities**:
- **Authentication**: Secure credential management
- **API Communication**: Direct service interaction
- **Error Handling**: Graceful failure management
- **Rate Limiting**: Respect service constraints

**Distinction from Context Providers**: Integrations handle API communication; context providers process and normalize data.

## 6. External Resource

A **reference to external content** that can be shared across multiple projects and tasks.

**Purpose**: Avoid duplication while maintaining links to relevant external context sources.

**Characteristics**:
- **URI-Based**: Unique identifiers for external content (URLs, URIs)
- **Shareable**: Same resource can be linked to multiple projects/tasks
- **Describable**: Human or AI-generated descriptions for context

**Examples**: GitHub repository URLs, Jira ticket links, Slack thread URLs, documentation pages.

## 7. Conversation

A **first-class entity** linking an agent session to a parent entity (Project, Task, Codebase, or Background Agent).

**Purpose**: Track the full history of an agent interaction, including which role is active, which engine is driving it, and all messages exchanged.

**Key Characteristics**:
- **Polymorphic parent**: `parent_entity_type` + `parent_entity_id` link the conversation to a Project, Task, Codebase, or Background Agent
- **Agent configuration snapshot**: `agent_role` (AgentRoleType), `engine` (INTERNAL/CLAUDE_CODE/GEMINI_CLI), and `model_id` are captured at creation time
- **Session continuity**: `external_session_id` enables Claude Code and Gemini CLI engines to resume an existing external session
- **Active state**: `is_active` marks whether this is the current active conversation for the entity; previous conversations are archived on phase transition
- **Sub-conversations**: `parent_conversation_id` supports nested conversations for internal agent-to-agent delegation
- **Message history**: The full exchange is stored as a list of `ConversationMessage` records

Role is selected dynamically based on parent entity type and state when a conversation starts.

## 8. Event Log (LogEntry)

An **append-only system event record** capturing agent actions, state transitions, tool calls, and developer activity.

**Purpose**: Provide a unified audit trail of everything that happens in the system, and serve as the trigger source for event-driven Background Agents.

**Key Characteristics**:
- **Source**: `source` field distinguishes `DEVELOPER`, `SYSTEM`, and `AGENT` entries
- **Typed events**: `type` (string) categorizes the event (e.g., `task.state_changed`, `agent.tool_call`)
- **Scope**: `project_id` and/or `task_id` scope entries to a specific project or task
- **Metadata**: `entry_metadata` (JSON) carries structured event-specific data
- **Status lifecycle**: `status` tracks ACTIVE / RESOLVED / SUPERSEDED entries; `pinned` marks important entries
- **Events view**: Drives the `/events` view in the frontend for monitoring agent activity
- **Trigger source**: Background Agents can subscribe to event type patterns and fire automatically when matching entries are created

## 9. Document

A **generic versioned text store** (Markdown) backing task specifications, implementation plans, project specifications, and change summaries.

**Purpose**: Provide a consistent, conflict-safe storage layer for all structured text content that agents and users collaboratively edit.

**Key Characteristics**:
- **Document types**: `document_type` is one of `PROJECT_SPECIFICATION`, `TASK_SPECIFICATION`, `TASK_IMPLEMENTATION_PLAN`, or `CHANGE_SUMMARY`
- **Content storage**: `content` holds the full Markdown text
- **Conflict detection**: `content_hash` (MD5, 32 hex chars) enables optimistic concurrency — callers pass the hash of the content they last read; if it doesn't match the stored hash, a conflict is reported and the update is rejected
- **Timestamps**: `created_at` and `updated_at` track document history

Documents are owned by their parent entity (Project or Task) and updated by agents as work progresses through lifecycle states.

## 10. Background Agent

A **user-defined autonomous agent** that runs independently of the task workflow, with persistent JSON state across runs.

**Purpose**: Enable recurring or event-driven automation (monitoring, reporting, triage) that operates outside the standard task lifecycle.

**Key Characteristics**:
- **Trigger types**: Manual (on-demand), scheduled (cron expression via `BackgroundAgentScheduleTrigger`), or event-based (matches LogEntry `event_type_pattern` via `BackgroundAgentEventTrigger`)
- **Persistent state**: `state` (JSON dict) persists across runs, enabling agents to track what they've processed or accumulate data over time
- **Run records**: Each execution creates a `BackgroundAgentRun` with `state_before` / `state_after` snapshots, status, token usage, and any error
- **Engine support**: Runs on any supported engine (INTERNAL, CLAUDE_CODE, GEMINI_CLI) with optional `model_id`
- **MCP tools**: Each Background Agent can have a specific set of MCP tools assigned

See `docs/4-ai-agents/background-agents.md` for full detail.

## 11. MCP Server

An **external tool server** managed via the DevBoard database, providing additional tools to agents via the Model Context Protocol.

**Purpose**: Extend the capabilities available to agents by connecting to external MCP-compatible tool servers without hardcoding tool logic into DevBoard.

**Key Characteristics**:
- **Server types**: `STDIO` (subprocess launched by DevBoard) or `HTTP` (remote server accessed over the network)
- **Tool catalogue**: Available tools are discovered and cached as `MCPTool` records linked to the server config
- **Per-agent assignment**: MCP tools can be assigned to individual Background Agents or enabled per agent role (via Settings → Agents)
- **Engine scope**: Only INTERNAL engine agents use assigned MCP tools directly; Claude Code and Gemini CLI manage their own MCP configuration externally

See `docs/5-integrations/mcp-server.md` for configuration details.

## Relationships Between Concepts

- **Projects contain Tasks**: One-to-many relationship for organizing work
- **Projects and Tasks link to External Resources**: Many-to-many relationship for context
- **Projects and Tasks reference Codebases**: Many-to-many relationship for code context
- **Context Providers use Integrations**: Providers depend on integrations for API access
- **External Resources are accessed via Context Providers**: Providers fetch and process resource content
- **Conversations belong to Projects, Tasks, Codebases, or Background Agents**: Polymorphic parent association
- **Conversations store ConversationMessages**: One-to-many message history per conversation
- **LogEntries are scoped to Projects and/or Tasks**: Used for audit trail and as Background Agent event triggers
- **Documents are owned by Projects or Tasks**: Each document type is linked to its parent entity
- **Background Agents produce BackgroundAgentRuns**: Each run snapshots state and links to a Conversation
- **MCP Servers expose MCPTools**: Tools are assigned to agent roles or individual Background Agents
