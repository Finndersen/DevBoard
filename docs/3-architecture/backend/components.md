# Backend Components

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Backend](./INDEX.md) > Components

## Overview

Layered architecture: API routers, services (business logic), repositories (data access), agents (AI), context providers, integrations.

**Location**: `backend/devboard/`

## API Routers

**Location**: `backend/devboard/api/routers/`

Handle request parsing, validation, delegate to services.

- **projects.py**: Project CRUD, resource linking, task listing, specification access
- **tasks.py**: Task lifecycle, state transitions (`DEFINING → DESIGNING → PLANNING → IMPLEMENTING → IN_REVIEW → COMPLETE`)
- **conversations.py**: Unified conversation endpoints for all entity types (projects, tasks, codebases). Message sending/streaming, tool approval workflows.
- **codebases.py**: Codebase registration, architecture document operations, local path validation
- **configurations.py**: Configuration CRUD, multi-source resolution, field-level source tracking
- **settings.py**: System settings, integration testing, health checks
- **agents.py**: Agent management endpoints
- **tool_approvals.py**: Tool approval workflow endpoints

See [API Reference](./api-reference.md) for complete endpoint documentation.

## Services

**Location**: `backend/devboard/services/`

Core business logic orchestrating repositories and external systems.

### Context Assembly Service

**File**: `context_assembly.py`

Multi-source context gathering for agents. Determines loading strategy (eager vs on-demand), parallel context fetching, context transformation.

**Key Operations**:
- Assemble project context: specification + resources + codebases
- Assemble task context: specification + plan + project context + resources
- Load external resources via context providers
- Cache with TTL

### Document Editor Service

**File**: `document_editor.py`

Find-and-replace document editing with conflict detection. Content hashing for optimistic locking, atomic updates.

**Key Operations**: Apply edits with conflict checking, full replacement, generate hashes, validate applicability

### Configuration Service

**File**: `config_service.py`

Multi-source configuration resolution (environment > database > defaults). Pydantic schema validation, agent configuration management.

**Key Operations**: Get configuration with source tracking, update database configs, validate schemas, resolve LLM provider configs

### Other Services

- **resource_service.py**: Context resource management, URI-based identification, resource sharing
- **template_service.py**: Document template loading, variable interpolation
- **conversation_service.py**: Conversation lifecycle management, conversation replacement
- **integration_service.py**: External integration management
- **project_service.py**: Project business logic
- **task_service.py**: Task business logic including state transition methods (`transition_to_planning()`, `transition_to_implementing()`)
- **codebase_investigation.py**: Codebase analysis and investigation

## Repositories

**Location**: `backend/devboard/db/repositories/`

Database abstraction with type-safe CRUD operations.

### Base Repository

**File**: `base.py`

Generic CRUD with transaction management: `get(id)`, `get_all()`, `create(entity)`, `update(entity)`, `delete(id)`

### Specialized Repositories

Each entity extends `BaseRepository[T]`:

- **ProjectRepository**: Project-specific queries (tasks, resources, specification)
- **TaskRepository**: State filtering
- **ConversationRepository**: Polymorphic conversation retrieval
- **CodebaseRepository**: Architecture document access
- **ConfigurationRepository**: Key pattern queries
- **DocumentRepository**: Document operations
- **ContextProviderResourceRepository**: Context provider resource management

## Agents

**Location**: `backend/devboard/agents/`

AI-powered agent system with role-based architecture and pluggable execution engines.

### Core Agent Components

**Base Agent** (`base_agent.py`): Abstract interface for all agents. Defines `run(prompt)`, `stream_events(prompt)` methods.

**Base Agent Conversation** (`base_agent_conversation.py`): Conversation service base class for managing agent interactions.

**Agent Configuration Service** (`agent_config_service.py`): Manages agent configuration and engine selection.

**Events** (`events.py`): Event type definitions (ConversationMessage, ToolCall, ToolResult, ToolCallRequest).

**Language Models** (`language_models.py`): Multi-provider LLM management (OpenAI, Anthropic, Google). Intelligent fallback handling, model configuration.

**Tools** (`tools.py`): Engine-agnostic tool definitions converted for each execution engine.

**Workflow Actions** (`workflow_actions/`): Reusable, named operations combining task state transitions with agent interactions. Base class in `base.py`, task-specific actions in `task_workflows.py`, registry in `registry.py`.

### Agent Engines

**Location**: `backend/devboard/agents/engines/`

**Agent Engines Registry** (`agent_engines.py`): Engine selection and registration.

**Internal Engine** (`internal/`): PydanticAI-based implementation with native tool execution. Files: `agent.py`, `agent_conversation.py`, `deps.py`, `utils.py`.

**Claude Code Engine** (`claude_code/`): Claude Code CLI integration with virtual tool calling. Files: `agent.py`, `agent_conversation.py`, `client.py`, `message_parser.py`, `session.py`, `tool_approval_manager.py`, `virtual_tools.py`.

**Gemini CLI** (`gemini_cli.py`): Gemini CLI integration.

### Agent Roles

**Location**: `backend/devboard/agents/roles/`

**Base Role** (`base.py`): Abstract role class defining system prompts, tools, and context assembly.

**ProjectQARole** (`project_qa.py`): Project Q&A and specification editing.

**TaskSpecificationRole** (`task_specification.py`): Task requirement gathering during SPECIFICATION phase.

**TaskPlanningRole** (`task_planning.py`): Implementation planning during PLANNING phase.

**TaskImplementationRole** (`task_implementation.py`): Code implementation assistance during IMPLEMENTATION phase.

**Types** (`types.py`): Role type definitions.

## Context Providers

**Location**: `backend/devboard/context_providers/`

Abstract retrieval from external sources, normalize for agent consumption.

- **base.py**: Abstract base class for context providers
- **registry.py**: Provider registration and lookup
- **github.py**: PR analysis (diffs, comments), issue tracking, repo structure, commit history
- **jira.py**: Ticket info, project context, workflow status, custom fields
- **slack.py**: Channel conversations, thread discussions, decision history
- **codebase.py**: Local filesystem analysis, architecture documents, code structure
- **webpage.py**: Web scraping, HTML to markdown, documentation parsing

**Pattern**: Each provider implements `get_context(uri)` returning normalized text content.

## Integrations

**Location**: `backend/devboard/integrations/`

Direct external API communication, authentication, rate limiting, error handling.

- **base.py**: Abstract base class for integrations
- **registry.py**: Integration registration and lookup
- **github.py**: GitHub API client wrapper, authentication management, rate limiting
- **jira.py**: Jira API integration, OAuth/token auth, ticket/project access
- **slack.py**: Slack SDK wrapper, bot token management, message/thread access
- **codebase.py**: Local codebase integration, file operations
- **shell.py**: Shell command execution integration

**Pattern**: Integration layer handles API specifics. Context providers use integrations to fetch and transform data.
