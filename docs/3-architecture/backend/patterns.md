# Backend Development Patterns

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Backend](./INDEX.md) > Patterns

## Overview

Development patterns and conventions for DevBoard backend. Focus on DevBoard-specific architectural decisions.

**Location**: `backend/devboard/`

## Code Organization

Modular structure separating concerns:

- **`api/`**: HTTP request handling and validation
- **`db/`**: Data persistence and models
- **`services/`**: Business logic implementation
- **`agents/`**: AI-powered assistance
- **`context_providers/`**: External context integration
- **`integrations/`**: External API clients
- **`config/`**: Configuration management

## API Design

RESTful principles with resource-based URLs:

```
/api/{resource}/              # Collection operations
/api/{resource}/{id}          # Individual resource operations
/api/{resource}/{id}/{sub}    # Sub-resource operations
```

HTTP methods: GET (retrieve), POST (create), PATCH (partial update), DELETE (remove)

## Dependency Injection

FastAPI dependency system for database sessions and service instances.

**Database Session**: `db: Session = Depends(get_db)` for automatic session management
**Service Factories**: Located in `backend/devboard/api/dependencies/` (repositories.py, services.py, agents.py, entities.py)

**Benefits**: Automatic resolution, easy testing with overrides, clear dependency graphs, lifecycle management

## Type Hinting

Comprehensive Python type hints throughout for IDE support and static analysis.

**Generic Types**: `BaseRepository[T]` for type-safe repositories

## Pydantic for Data Validation

Request/response schemas with automatic validation and serialization.

**Pattern**: `ProjectCreate` for input, `ProjectResponse` for output, `from_attributes = True` for ORM mode

**Benefits**: Auto-validation, JSON serialization, OpenAPI generation

## SQLAlchemy ORM Patterns

### Modern SQLAlchemy 2.0

`Mapped[]` annotations and `select()` statements.

**Model Definition**:
```python
class Project(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
```

**Query Pattern**: `stmt = select(Project).where(Project.id == id)` followed by `db.execute(stmt).scalar_one_or_none()`

### Generic Repository Pattern

`BaseRepository[T]` provides type-safe CRUD: `get(id)`, `get_all()`, `create(entity)`, `update(entity)`, `delete(id)`

**Specialized Repositories**: Extend base with entity-specific queries (e.g., `ProjectRepository.get_with_tasks()`)

## Error Handling

### HTTP Exception Patterns

Custom `HTTPException` with appropriate status codes: 404 (not found), 400 (bad request), 409 (conflict)

**Global Error Handlers** (`backend/devboard/api/main.py`): Structured responses with error type, message, path

### Service-Level Errors

Services raise specific exceptions (e.g., `DocumentConflictError`), routers convert to HTTP responses.

**Pattern**: Service raises domain exception, router catches and converts to `HTTPException`

## Async Patterns

### Background Task Execution + Event Queue

Agent execution runs as background asyncio tasks, decoupled from HTTP requests. Events stream via WebSocket.

**ConversationExecutionManager** (`backend/devboard/agents/execution_manager.py`):
- Process-level singleton tracking active executions per conversation
- `start_execution(conversation_id, coro_factory)` — raises `ConversationBusyError` if already active
- Maintains `asyncio.Queue` per execution for event buffering
- Manages interrupt flag (`asyncio.Event`) for graceful shutdown
- Schedules cleanup after 60s grace period

**Background execution coroutines** (`backend/devboard/agents/background_execution.py`):
- `run_agent_for_conversation(event_queue, interrupt_event, *, ...)` — executes agent, pushes events to queue
- Creates DB sessions via `SessionLocal()` (cannot use FastAPI `Depends()` in background tasks)
- Service factory: `create_execution_services(db)` in `backend/devboard/agents/execution_dependencies.py`

**Conversation message/approval pattern**: HTTP endpoint validates request, calls `conversation_execution_manager.start_execution()`, returns `{"conversation_id": N}` immediately. WebSocket endpoint (`/api/conversations/{id}/ws`) polls for executions and streams events from queue.

**Workflow action pattern**: Workflow actions run synchronously within the HTTP request handler. Each action's `run()` method performs procedural steps (state transitions, DB changes) and returns either a prompt string or `None`. If a prompt is returned, the endpoint starts a background agent execution on the task's active conversation and returns `{"conversation_id": N}`. If `None`, returns `{"status": "completed"}`.

## Configuration Management

### Multi-Source Resolution

Hierarchical configuration: environment variables > database > code defaults

**Pattern**: ConfigService checks sources in precedence order, tracks source per field (`environment`, `database`, `default`)

**Implementation**: `backend/devboard/services/config_service.py`

## DevBoard-Specific Patterns

### Event-Based Agent Architecture

**ConversationEvent Model**: Base for all agent interaction events (`ConversationMessage`, `ToolCall`, `ToolResult`, `ToolCallRequest`)

**Event Streaming**: Agent generates events during execution. Service persists to database and streams to frontend via NDJSON.

**Pattern**: PydanticAI messages converted to ConversationEvents in `agent_conversation.py`, streamed asynchronously

### Tool Approval Workflow

**Two-Phase Execution**: Agent pauses on tool requiring approval, returns `ToolCallRequest` events. Frontend approves/denies, agent resumes.

**Pattern**: Agent checks tool.requires_approval, if true, yields approval request and pauses. `POST /approve-tools` starts a new background execution with the approval decisions; the agent resumes via the same WebSocket connection.

**Implementation**: `backend/devboard/agents/base_agent.py`, `backend/devboard/services/agent_conversation.py`

### Graceful Agent Interruption

**Interrupt flag**: Each execution has an `asyncio.Event` set via `POST /conversations/{id}/interrupt`.

**Agent checking**: Both PydanticAI (`engines/internal/`) and Claude Code (`engines/claude_code/`) engines check the interrupt flag and raise `AgentInterruptedError`.

- **PydanticAI**: Checks after each streaming event, raises on interrupt
- **Claude Code**: Spawns monitor task that calls `client.interrupt()` (native SDK signal) when flag is set

**On interrupt**: `ConversationExecutionManager` catches `AgentInterruptedError`, marks status as INTERRUPTED, pushes None sentinel to queue, WebSocket sends `execution_completed` with `status: "interrupted"`.

### Context Assembly Strategy

**Multi-Source Context**: Projects/tasks gather context from specification documents, linked resources (GitHub PR, Jira ticket, etc.), and codebases.

**Loading Strategy**: Eager vs on-demand based on context size. Parallel fetching with asyncio for performance.

**Pattern**: `ContextAssemblyService` determines what to load, uses context providers to fetch, transforms to text for agent prompts.

**Implementation**: `backend/devboard/services/context_assembly.py`

### Document Editing with Conflict Detection

**Find-and-Replace Pattern**: `edit_document(old_string, new_string)` tool for precise edits.

**Optimistic Locking**: Content hashing (`original_hash`) for conflict detection. Returns 409 if hash doesn't match.

**Pattern**: Frontend reads document with hash, agent edits, service validates hash before applying, returns conflict if changed.

**Implementation**: `backend/devboard/services/document_editor.py`

### Polymorphic Conversation System

**Single Conversation Model**: All entities (projects, tasks, codebases) use same `Conversation` model with polymorphic `entity_type`/`entity_id`.

**Pattern**: `ConversationRepository` retrieves conversation for any entity type, agent router unified across entities.

**Benefits**: Single API endpoint set (`/api/conversations/{id}/...`), consistent frontend handling, shared event history

**Implementation**: `backend/devboard/models/conversation.py`, `backend/devboard/api/routers/conversations.py`

### Context Provider Abstraction

**URI-Based Resources**: Resources identified by URI (e.g., `github://owner/repo/pulls/123`, `jira://project/TICKET-456`)

**Provider Registration**: Each provider handles specific URI schemes, transforms external data to normalized text.

**Pattern**: `ContextProviderRegistry` routes URIs to providers, providers use integrations for API calls, return formatted context text.

**Implementation**: `backend/devboard/context_providers/`, `backend/devboard/integrations/`

## Testing Patterns

Pytest fixtures for test setup (`backend/tests/`).

**Database Fixtures**: Test database with sample data
**Repository Testing**: Test data access independently
**Router Testing**: TestClient with mocked dependencies
