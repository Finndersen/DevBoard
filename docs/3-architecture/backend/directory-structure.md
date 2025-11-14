# Backend Directory Structure

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Backend](./INDEX.md) > Directory Structure

**Location**: `/backend/devboard/`

## Structure

```
backend/
├── devboard/                      # Main package
│   ├── api/                      # FastAPI layer
│   │   ├── main.py               # Application entry point
│   │   ├── dependencies/         # Dependency injection (conversations.py, entities.py, repositories.py, services.py)
│   │   ├── routers/             # Endpoints (agents.py, codebases.py, configurations.py, conversations.py, projects.py, settings.py, tasks.py, tool_approvals.py)
│   │   ├── schemas/             # Pydantic request/response (agent_conversation.py, claude_code_todo.py, codebase.py, common.py, conversation.py, document.py, integration.py, project.py, prompt_action.py, resource.py, task.py)
│   │   └── streaming.py         # Streaming response helper
│   ├── agents/                  # AI agents
│   │   ├── base_agent.py       # Abstract base agent
│   │   ├── base_agent_conversation.py  # Conversation service base
│   │   ├── agent_config_service.py     # Agent configuration
│   │   ├── events.py           # Event type definitions
│   │   ├── language_models.py  # Multi-provider LLM
│   │   ├── tools.py            # Tool definitions
│   │   ├── engines/            # Agent execution engines
│   │   │   ├── agent_engines.py        # Engine registry
│   │   │   ├── claude_code/    # Claude Code CLI integration (agent.py, agent_conversation.py, client.py, message_parser.py, session.py, tool_approval_manager.py, virtual_tools.py)
│   │   │   ├── gemini_cli.py   # Gemini CLI integration
│   │   │   └── internal/       # PydanticAI implementation (agent.py, agent_conversation.py, deps.py, utils.py)
│   │   └── roles/              # Role implementations (base.py, project_qa.py, task_specification.py, task_planning.py, task_implementation.py, types.py)
│   ├── workflow_actions/        # Workflow action orchestration
│   │   ├── base.py             # Base WorkflowAction class
│   │   ├── task_workflows.py   # Task workflow actions (CreateImplementationPlanAction, BeginImplementationAction)
│   │   └── registry.py         # Workflow action registry
│   ├── services/               # Business logic
│   │   ├── codebase_investigation.py
│   │   ├── config_service.py
│   │   ├── context_assembly.py
│   │   ├── conversation_service.py
│   │   ├── document_editor.py
│   │   ├── integration_service.py
│   │   ├── project_service.py
│   │   ├── resource_service.py
│   │   ├── task_service.py
│   │   └── template_service.py
│   ├── db/                     # Persistence
│   │   ├── database.py         # Database setup
│   │   ├── models/             # SQLAlchemy 2.0 with Mapped[] (base.py, codebase.py, configuration.py, conversation.py, document.py, messages.py, project.py, task.py)
│   │   ├── repositories/       # Data access (base.py, codebase.py, configuration.py, context_provider_resource.py, conversation.py, document.py, project.py, task.py)
│   │   └── migrations/         # Alembic migrations
│   ├── context_providers/      # External context
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── github.py
│   │   ├── jira.py
│   │   ├── slack.py
│   │   ├── codebase.py
│   │   └── webpage.py
│   ├── integrations/           # API clients
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── github.py
│   │   ├── jira.py
│   │   ├── slack.py
│   │   ├── codebase.py
│   │   └── shell.py
│   ├── config/                 # Configuration
│   │   ├── registry.py
│   │   ├── base.py
│   │   ├── llm_providers.py
│   │   ├── integration_configs.py
│   │   ├── agent_config.py
│   │   └── logfire_config.py
│   ├── core/                   # Core utilities
│   │   └── registry.py
│   ├── utils/                  # Utilities
│   │   └── hash.py
│   └── templates/              # Document templates (architecture_document.md, implementation_plan.md, task_specification.md)
├── tests/                      # Test suite
├── alembic/                    # Migrations
├── pyproject.toml             # Dependencies
└── uv.lock                    # Lockfile
```

## Layers

**API** (`api/`): HTTP handling, validation, response formatting. Routers by domain, Pydantic schemas, dependency injection

**Service** (`services/`): Business logic, multi-repo coordination, context assembly, agent orchestration, document editing. Receive dependencies via DI

**Data Access** (`db/`): Database operations. Models (SQLAlchemy ORM), repositories (abstraction), session management

**Agents** (`agents/`): AI-powered agents. Conversation management, tool execution, context-aware responses, multi-provider LLM. Role-based with pluggable engines

**Integration** (`integrations/` + `context_providers/`): External services. Integrations = direct API clients (auth, rate limiting). Context providers = normalize data (smart loading strategies)

**Configuration** (`config/`): Multi-source resolution (env, database, defaults), schema validation, agent/integration settings

## Key Modules

**API Routers**:
- `projects.py`: CRUD, resource linking, task listing
- `tasks.py`: Management, state transitions
- `conversations.py`: Unified endpoints for all entity types
- `codebases.py`: Management, architecture docs
- `configurations.py`: CRUD with validation
- `settings.py`: System settings, integration testing
- `agents.py`: Agent management endpoints
- `tool_approvals.py`: Tool approval workflow endpoints

**DB Models** (SQLAlchemy 2.0 with `Mapped[]`):
- `project.py`, `task.py`, `conversation.py`, `messages.py`, `configuration.py`, `codebase.py`, `document.py`

**Repositories**: `base.py` (generic `BaseRepository[T]`), specialized repos, transaction management

**Services**:
- `context_assembly.py`: Multi-source gathering
- `document_editor.py`: Find-and-replace with conflict detection
- `config_service.py`: Validation, resolution
- `template_service.py`: Templates
- `conversation_service.py`: Conversation lifecycle management, conversation replacement
- `integration_service.py`: Integration management
- `project_service.py`: Project operations
- `task_service.py`: Task operations including state transitions
- `resource_service.py`: Context resource management
- `codebase_investigation.py`: Codebase analysis

**Workflow Actions** (`workflow_actions/`):
- `base.py`: Abstract WorkflowAction base class
- `task_workflows.py`: Task-specific workflow actions (CreateImplementationPlanAction, BeginImplementationAction)
- `registry.py`: Action registry for lookup by key

**Context Providers**: GitHub (repo/PR/issue), Jira (tickets/projects), Slack (conversations/threads), Codebase (local files/code), Web (content scraping)

## Development

**Testing** (`backend/tests/`): Mirror structure, unit and integration tests

**Migrations** (`backend/alembic/`): Alembic schema evolution, version-controlled

**Dependencies**: `pyproject.toml`, `uv.lock`. Modern tooling with `uv` for fast resolution, strict pinning
