# Database Schema

**Navigation**: [Documentation Home](../INDEX.md) > [Architecture](./INDEX.md) > Database Schema

## Overview

DevBoard uses SQLAlchemy 2.0 with `Mapped[T]` type annotations and full async support. The schema implements projects, tasks, codebases, conversations, and configuration management.

**Location**: `backend/devboard/db/models/`

## Core Entity Models

### Project Model

**Purpose**: High-level containers for related work

**Key Fields**: `id`, `name`, `details`, `current_status`, timestamps

**Relationships**:
- `tasks`: One-to-many with Task
- `specification`: One-to-one with Document (project specification)
- `codebases`: Many-to-many with Codebase
- `context_resources`: Many-to-many with ContextProviderResource
- `conversation`: One-to-one with Conversation (polymorphic)

**Cascade**: Deleting project deletes specification and conversation

### Task Model

**Purpose**: Discrete units of work with lifecycle states

**Key Fields**: `id`, `title`, `description`, `project_id`, `state`, `branch_name`, timestamps

**State Enum**: DEFINING, DESIGNING, PLANNING, IMPLEMENTING, IN_REVIEW, COMPLETE

**Relationships**:
- `project`: Many-to-one with Project
- `specification`: One-to-one with Document
- `implementation_plan`: One-to-one with Document
- `context_resources`: Many-to-many with ContextProviderResource
- `conversation`: One-to-one with Conversation (polymorphic)

**Cascade**: Deleting task deletes specification, plan, and conversation

### Codebase Model

**Purpose**: Local or remote code repositories

**Key Fields**: `id`, `name`, `description`, `local_path`, `repository_url`, `default_branch`, `merge_method`, `branch_handling`, `max_worktrees`, `setup_command`, `created_at`

**Configuration Fields**:
- `default_branch`: Base branch for task branches (e.g., "origin/main")
- `merge_method`: How commits are combined during merge (squash, rebase, merge_commit)
- `branch_handling`: Where feature branches are finalized (local_merge, github_pr, manual)
- `max_worktrees`: Maximum worktree slots (null = unlimited, 0 = main repo only)
- `setup_command`: Shell command to run when workspace is allocated (e.g., "npm install")

**Relationships**:
- `projects`: Many-to-many with Project
- `architecture_document`: One-to-one with Document
- `conversation`: One-to-one with Conversation (polymorphic)

**Cascade**: Deleting codebase deletes architecture document and conversation

### Document Model

**Purpose**: Generic document storage with conflict detection

**Key Fields**: `id`, `content`, `content_hash`, `document_type`, timestamps

**Document Types**: project_specification, task_specification, implementation_plan, architecture_document

**Conflict Detection**: `content_hash` (SHA-256) enables optimistic locking to prevent concurrent edit conflicts

## Conversation System

### Conversation Model

**Purpose**: Container for agent conversations with polymorphic parent association

**Key Fields**:
- `id`, `parent_entity_type`, `parent_entity_id`, `parent_conversation_id`
- `agent_role`, `engine`, `model_id`, `external_session_id`
- timestamps

**Parent Entity Types**: PROJECT, TASK, CODEBASE

**Unique Constraint**: (`parent_entity_type`, `parent_entity_id`) ensures one conversation per entity

**Model Selection**: `model_id` nullable to support engines with own model selection (Claude Code, Gemini CLI). INTERNAL engine requires explicit `model_id` (enforced at service layer).

**Relationships**:
- `messages`: One-to-many with ConversationMessage
- `parent_conversation`: Self-referential for nested conversations

**Lazy Creation**: Created via `get_or_create_for_entity()` when accessing entity details

### ConversationMessage Model

**Purpose**: Unified message storage supporting PydanticAI message format

**Key Fields**: `id`, `conversation_id`, `message_type`, `pydantic_content`, `text_content`, `timestamp`

**Message Types**: USER_PROMPT, TEXT_RESPONSE, TOOL_CALL, TOOL_RESULT, STRUCTURED_RESPONSE

**Relationships**: `conversation`: Many-to-one with Conversation

## Configuration System

### Configuration Model

**Purpose**: Hierarchical configuration with JSON serialization

**Key Fields**: `key`, `value_json`, `schema_version`, `updated_at`

**Key Examples**:
- `llm.openai.api_key`: OpenAI API key
- `integration.github.token`: GitHub access token

**Multi-Source Resolution**: Environment variables override database, which overrides code defaults

### AgentRoleConfig Model

**Purpose**: Per-role agent configuration with custom instructions and MCP tool assignments

**Key Fields**: `id`, `role` (unique), `engine`, `model_id`, `custom_instructions`

**Role Enum**: PROJECT, TASK_PLANNING, TASK_IMPLEMENTATION, TASK_PR_REVIEW, INVESTIGATION

**Relationships**:
- `enabled_mcp_tools`: Many-to-many with MCPTool

**Get-or-Create Pattern**: Configuration is created with defaults on first access, ensuring every role always has a configuration record.

### MCPServerConfig Model

**Purpose**: MCP server connection configuration

**Key Fields**: `id`, `name`, `server_type`, `config_json`, `last_verified_at`, `last_verified_success`, `last_verified_error`

**Server Types**: STDIO, HTTP

**Relationships**:
- `tools`: One-to-many with MCPTool

### MCPTool Model

**Purpose**: Individual tools discovered from MCP servers

**Key Fields**: `id`, `server_id`, `name`, `description`, `input_schema`

**Relationships**:
- `server`: Many-to-one with MCPServerConfig
- `agent_role_configs`: Many-to-many with AgentRoleConfig

### ContextProviderResource Model

**Purpose**: External resource references with URI-based identification

**Key Fields**: `id`, `resource_uri`, `provider_type`, `description`, `created_at`

**Provider Types**: GitHub, Jira, Slack, Codebase, Webpage

**Relationships**:
- `projects`: Many-to-many with Project
- `tasks`: Many-to-many with Task

**Sharing**: Same resource can link to multiple projects/tasks

## Association Tables

### project_codebase_association

**Columns**: `project_id`, `codebase_id` (composite primary key)

### project_resource_association

**Columns**: `project_id`, `resource_id` (composite primary key)

### task_resource_association

**Columns**: `task_id`, `resource_id` (composite primary key)

### agent_role_config_mcp_tools

**Columns**: `agent_role_config_id`, `mcp_tool_id` (composite primary key)

**Purpose**: Associates MCP tools with agent role configurations

**Cascade**: Deletes propagate from both AgentRoleConfig and MCPTool

## Entity Relationships Summary

```
Project
  ├── has many Tasks
  ├── has one Specification (Document)
  ├── links to many Codebases (M:M)
  ├── links to many Context Resources (M:M)
  └── has one Conversation

Task
  ├── belongs to one Project
  ├── has one Specification (Document)
  ├── has one Implementation Plan (Document)
  ├── links to many Context Resources (M:M)
  └── has one Conversation

Codebase
  ├── has one Architecture Document (Document)
  ├── linked by many Projects (M:M)
  └── has one Conversation

Conversation
  ├── belongs to one Parent Entity (polymorphic: Project/Task/Codebase)
  ├── has many Messages
  └── optionally has Parent Conversation (nested)

ContextProviderResource
  ├── linked by many Projects (M:M)
  └── linked by many Tasks (M:M)

AgentRoleConfig
  └── links to many MCPTools (M:M)

MCPServerConfig
  └── has many MCPTools

MCPTool
  ├── belongs to one MCPServerConfig
  └── linked by many AgentRoleConfigs (M:M)
```

## Database Patterns

### Modern SQLAlchemy 2.0

- **Type Annotations**: `Mapped[T]` throughout
- **Select Statements**: `select()` instead of legacy `query()`
- **Relationship Management**: Bidirectional with `back_populates`
- **Generic Repository**: Type-safe `BaseRepository[T]`

### Migration Strategy

- **Alembic**: Database migration management
- **Version Control**: All migrations in Git
- **Auto-generation**: Schema changes tracked automatically
- **Production Safety**: Validation and rollback capabilities

### Conflict Detection

**Content Hashing**: SHA-256 for Document model
- Read returns content + hash
- Edit includes original hash
- Verify current hash matches before applying
- Reject if hashes don't match (concurrent modification)

### Lazy Initialization

**Conversation Creation**: Conversations created lazily via `get_or_create_for_entity()` when accessing entity details, ensuring every entity has conversation without explicit API calls.

## Database Migration Path

### Current: SQLite

- Development and single-user deployment
- File-based storage
- Async support
- Suitable for local-first architecture

### Future: PostgreSQL

- Multi-user deployment
- Production-grade features
- Better concurrent access
- Migration path via SQLAlchemy + Alembic
