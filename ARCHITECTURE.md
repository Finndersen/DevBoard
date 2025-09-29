# DevBoard - Technical Architecture Documentation

## Implementation Overview
This document describes the current technical implementation of DevBoard, a sophisticated AI-powered developer command center built with modern Python and TypeScript technologies. The system implements a local-first architecture with extensive AI agent integration and multi-source context assembly.

### System Status
**Implementation State**: Production-ready with comprehensive feature coverage
- **Database Layer**: 100% complete with full migration support
- **API Layer**: 95% complete with all core endpoints functional
- **Agent System**: 90% complete with sophisticated conversation management
- **Context Providers**: 90% complete with multi-source integration
- **Frontend**: 85% complete with full workflow support

## Technical Architecture Overview
DevBoard implements a **sophisticated local client-server architecture** optimized for developer workflows:

### Backend Architecture
**Framework**: FastAPI with async Python, modern SQLAlchemy 2.0, PydanticAI agent framework
**Database**: SQLite with PostgreSQL migration path, comprehensive relationship modeling
**AI Integration**: PydanticAI with multi-provider LLM support (OpenAI, Anthropic, Google)
**Real-time**: WebSocket support for agent progress streaming
**Observability**: Pydantic Logfire integration with comprehensive instrumentation

### Frontend Architecture  
**Framework**: React 19+ with TypeScript, Vite build system, modern hooks-based state management
**Styling**: Tailwind CSS with responsive design system
**Testing**: Vitest + React Testing Library + MSW for comprehensive test coverage
**State Management**: Props-down/events-up pattern with API-driven data fetching
**Real-time**: WebSocket integration for live agent updates

## Implementation Directory Structure

### Backend Implementation (`/backend`)
Modern Python FastAPI application with comprehensive layered architecture:

```
backend/
├── devboard/                      # Main Python package
│   ├── api/                      # FastAPI application layer
│   │   ├── dependencies/         # Dependency injection modules  
│   │   │   ├── agents.py        # Agent service dependencies
│   │   │   ├── entities.py      # Entity dependency providers
│   │   │   ├── repositories.py  # Repository factory functions
│   │   │   └── services.py      # Service factory functions
│   │   ├── routers/             # API endpoint implementations
│   │   │   ├── projects.py      # Project CRUD operations
│   │   │   ├── tasks.py         # Task management + state transitions
│   │   │   ├── conversations.py # Unified agent conversation endpoints
│   │   │   ├── codebases.py     # Codebase + architecture docs
│   │   │   ├── configurations.py # Configuration management
│   │   │   └── settings.py      # System settings + connection tests
│   │   └── schemas/             # Pydantic request/response models
│   │       ├── project.py       # Project API schemas  
│   │       ├── task.py          # Task + conversation schemas
│   │       └── agent.py         # Agent interaction schemas
│   ├── agents/                  # PydanticAI agent implementations
│   │   ├── base_agent.py       # Abstract base agent with document editing
│   │   ├── project_agent.py    # Project Q&A + document collaboration
│   │   ├── task_agent.py       # Task specification + planning agents
│   │   ├── llm_service.py      # Multi-provider LLM management
│   │   └── tools.py            # Agent tool definitions
│   ├── services/               # Business logic layer
│   │   ├── agent_conversation.py # Agent message orchestration
│   │   ├── context_assembly.py  # Multi-source context gathering
│   │   ├── document_editor.py   # Document editing with conflict detection
│   │   ├── resource_service.py  # Context resource management
│   │   ├── config_service.py    # Configuration validation + management
│   │   └── template_service.py  # Document template management
│   ├── db/                     # Database + persistence layer
│   │   ├── models/             # SQLAlchemy 2.0 models with full typing
│   │   │   ├── project.py      # Project + specification documents
│   │   │   ├── task.py         # Tasks + implementation plans
│   │   │   ├── conversation.py # Unified conversation containers
│   │   │   ├── messages.py     # Agent conversation messages
│   │   │   └── configuration.py # Hierarchical configuration storage
│   │   ├── repositories/       # Data access patterns
│   │   │   ├── base.py         # Generic repository with type safety
│   │   │   └── [entity]_repository.py # Specialized data access
│   │   └── session.py          # Database session management
│   ├── context_providers/      # External context integration
│   │   ├── registry.py         # Provider discovery + instantiation
│   │   ├── github.py           # GitHub PR/issue/repo analysis
│   │   ├── jira.py             # Jira ticket + project context
│   │   ├── slack.py            # Slack conversation analysis
│   │   ├── codebase.py         # Local file system analysis
│   │   └── webpage.py          # Web content scraping
│   ├── integrations/           # External API clients
│   │   ├── registry.py         # Integration factory + management
│   │   ├── github.py           # PyGithub + API wrapper
│   │   ├── jira.py             # Jira API integration
│   │   ├── slack.py            # Slack SDK wrapper
│   │   └── filesystem.py       # Local file operations
│   ├── config/                 # Configuration framework
│   │   ├── registry.py         # Configuration schema registry
│   │   ├── llm_config.py       # LLM provider configurations
│   │   ├── integration_configs.py # External service credentials
│   │   └── agent_config.py     # Agent behavior settings
│   └── templates/              # Document templates
│       ├── task_specification.md
│       ├── implementation_plan.md
│       └── architecture_document.md
├── tests/                      # Comprehensive test suite
│   ├── agents/                 # Agent behavior tests
│   ├── services/               # Service layer tests
│   ├── repositories/           # Data access tests
│   └── routers/               # API endpoint tests
├── alembic/                    # Database migrations
│   └── versions/               # Migration scripts
├── pyproject.toml             # Project config + dependencies
└── uv.lock                    # Dependency resolution lockfile
```

### Frontend Implementation (`/frontend`)  
Modern React application with TypeScript, comprehensive testing, and reusable component system:

```
frontend/
├── src/
│   ├── components/            # Reusable UI components
│   │   ├── ui/               # Standardized UI component library
│   │   │   ├── Button.tsx    # Standardized button with variants/sizes/states
│   │   │   ├── Card.tsx      # Consistent card component with theming
│   │   │   ├── Input.tsx     # Theme-aware input with labels/errors
│   │   │   ├── Textarea.tsx  # Standardized textarea component
│   │   │   ├── Modal.tsx     # Reusable modal with proper theming
│   │   │   ├── StatusBadge.tsx # Status indicators with color variants
│   │   │   ├── ErrorBoundary.tsx # React error boundary handling
│   │   │   ├── ErrorMessage.tsx # Standardized error display
│   │   │   └── index.ts      # Component library exports
│   │   ├── __tests__/        # Component unit tests
│   │   ├── Layout.tsx        # Navigation shell + routing
│   │   ├── Chat.tsx          # Real-time agent conversation UI
│   │   ├── ConfigurationForm.tsx # Dynamic config forms
│   │   └── ConfigurationField.tsx # Individual field components
│   ├── views/                # Page-level components
│   │   ├── __tests__/        # View integration tests
│   │   ├── ProjectDashboard.tsx # Project listing + creation (refactored)
│   │   ├── ProjectDetail.tsx    # Project details + Q&A chat
│   │   ├── TaskDetail.tsx       # Task planning + specification (refactored)
│   │   ├── Codebases.tsx        # Codebase + architecture management
│   │   └── Settings.tsx         # System configuration UI
│   ├── hooks/                # Custom React hooks for data fetching
│   │   ├── useApi.ts         # Generic API hook with loading/error states
│   │   ├── useProjects.ts    # Project CRUD operations hooks
│   │   ├── useTasks.ts       # Task management hooks
│   │   ├── useCodebases.ts   # Codebase operations hooks
│   │   └── index.ts          # Hook exports
│   ├── styles/               # Design system and styling utilities
│   │   ├── designSystem.ts   # Color palette, layouts, typography
│   │   └── inputStyles.ts    # Standardized input styling system
│   ├── utils/                # Utility functions
│   │   ├── approvalKeys.ts   # Approval context key helpers
│   │   └── diffUtils.ts      # Document diff utilities
│   ├── lib/                  # Core utilities + services
│   │   ├── __tests__/        # Utility tests
│   │   └── api.ts            # Typed API client + interfaces
│   ├── contexts/             # React context providers
│   │   ├── DarkModeContext.tsx # Theme switching context
│   │   └── ApprovalsContext.tsx # Agent approval state management
│   ├── test/                 # Test configuration
│   │   ├── setup.ts          # Test environment setup
│   │   ├── utils.tsx         # Test helper functions
│   │   └── mocks/            # MSW API mocks
│   ├── App.tsx               # Main application + routing
│   ├── main.tsx              # Application entry point
│   └── index.css             # Global styles + Tailwind
├── package.json              # Dependencies + scripts
├── vite.config.ts            # Build configuration
├── vitest.config.ts          # Test runner configuration  
├── tailwind.config.js        # CSS framework configuration
└── tsconfig.json             # TypeScript compiler settings
```

## Current Technology Implementation

### Core Technology Stack

#### Backend Technology (Python 3.12+)
**Production-Ready Implementation with Modern Python Patterns**

**Core Framework & Infrastructure**:
- **FastAPI**: Async ASGI application with automatic OpenAPI documentation
- **SQLAlchemy 2.0**: Modern ORM with `Mapped[]` annotations and select() queries
- **Alembic**: Database migration management with version control
- **Pydantic V2**: Data validation with performance optimizations
- **PydanticAI**: Advanced AI agent framework with conversation management
- **Pydantic Logfire**: Comprehensive observability and performance monitoring

**AI & LLM Integration**:
- **Multi-Provider Support**: OpenAI GPT-4, Anthropic Claude, Google Gemini
- **Intelligent Fallbacks**: Automatic model selection with hierarchy-based fallback
- **Conversation Persistence**: Full agent conversation history with PydanticAI message format
- **Tool Approval Workflow**: Deferred tool execution with user approval

**External Service Integration**:
- **PyGithub**: GitHub API integration with rate limiting
- **Jira Python SDK**: Atlassian API integration 
- **Slack SDK**: Slack Bot API integration
- **HTTPx**: Async HTTP client for external API calls
- **BeautifulSoup4**: Web scraping with HTML parsing

**Development & Quality Tools**:
- **uv**: Fast Python package installer and dependency resolver
- **Ruff**: Extremely fast Python linter with comprehensive rule coverage
- **Pyright**: Static type checker with strict type enforcement
- **Pytest**: Test framework with async support and comprehensive fixtures

#### Frontend Technology (TypeScript + React)
**Modern React 19+ Implementation with Full Type Safety**

**Core Framework & Build System**:
- **React 19+**: Latest React with concurrent features and improved hooks
- **TypeScript**: Strict type checking with comprehensive interface definitions
- **Vite**: Fast build system with HMR and optimized production builds
- **React Router v7+**: Client-side routing with data loading patterns

**UI/UX & Styling**:
- **Tailwind CSS**: Utility-first CSS framework with custom design system
- **Heroicons**: SVG icon library optimized for Tailwind
- **React-Markdown**: Markdown rendering with syntax highlighting support
- **PostCSS + Autoprefixer**: CSS processing with browser compatibility

**Testing & Quality**:
- **Vitest**: Fast test runner with native ESM support
- **React Testing Library**: Component testing focused on user interactions
- **MSW (Mock Service Worker)**: API mocking for realistic testing
- **ESLint**: Code quality enforcement with React-specific rules

**State Management & Data Flow**:
- **API-Driven State**: Centralized `ApiClient` with TypeScript interfaces
- **Custom Hooks**: Reusable data fetching hooks with loading/error states
- **React Hooks**: Modern state management with `useState`/`useEffect` patterns
- **WebSocket Integration**: Real-time updates for agent conversations
- **Props-Down/Events-Up**: Clean data flow architecture

**Design System & Components**:
- **Reusable UI Library**: Standardized component library in `src/components/ui/`
- **Design System**: Centralized color palette, typography, and layout utilities
- **Theme Support**: Comprehensive dark/light mode with Tailwind CSS classes
- **Form Components**: Consistent input styling with error handling and validation

### Database & Persistence Implementation

#### Database Architecture
**SQLite with PostgreSQL Migration Path**

**Current Database Setup**:
- **SQLite**: Development and single-user deployment database
- **Connection Pooling**: SQLAlchemy connection management with async support
- **Migration Strategy**: Alembic-managed schema evolution
- **Backup Strategy**: File-based backups with versioning support

**Advanced ORM Implementation**:
- **Modern SQLAlchemy 2.0**: Uses `select()` statements instead of legacy `query()` methods
- **Full Type Annotations**: `Mapped[T]` annotations throughout models
- **Relationship Management**: Bidirectional relationships with `back_populates`
- **Generic Repository Pattern**: Type-safe data access with `BaseRepository[T]`

**Database Schema Highlights**:
- **Document Storage**: Generic document system with content hashing for conflict detection
- **Unified Conversation System**: Polymorphic conversation architecture supporting all entity types through single table
- **Message Persistence**: Unified message storage with structured PydanticAI message format across all conversations
- **Resource Sharing**: Many-to-many relationships for context provider resources
- **Configuration Hierarchy**: JSON-based configuration storage with Pydantic validation

**Conversation Architecture Benefits**:
- **Unified API Pattern**: Single set of conversation endpoints for all entity types eliminates duplication
- **Easy Extensibility**: Adding new conversational entities requires only adding enum value, no new tables or endpoints
- **Simplified Codebase**: One repository and service pattern replaces N entity-specific implementations
- **Better Separation**: Conversation logic cleanly separated from entity-specific concerns
- **Future-Ready**: Supports nested conversations for advanced agent-to-agent communication patterns

### Development & Deployment Infrastructure

#### Development Environment
**Modern Python & Node.js Development Setup**

**Backend Development**:
```bash
# Modern Python dependency management
uv sync                    # Install dependencies
uv run alembic upgrade head # Database migrations  
uv run uvicorn devboard.api.main:app --reload # Development server
uv run pytest            # Test execution
uv run ruff check . --fix # Linting with auto-fix
```

**Frontend Development**:
```bash
# Modern Node.js tooling
npm install               # Install dependencies
npm run dev              # Vite development server with HMR
npm run build           # Production build with optimization
npm run test            # Vitest test execution
npm run type-check      # TypeScript compilation check
```

#### Production Deployment
**Docker-Based Containerization with Local-First Architecture**

**Container Strategy**:
- **Multi-stage Builds**: Optimized Docker images with layer caching
- **Volume Mounting**: Local codebase access for AI agent file operations
- **Data Persistence**: Host-mounted directories for database and configuration
- **Environment Management**: Docker Compose orchestration with environment files

**Production Configuration**:
- **Database Migration**: Automatic Alembic migration on container startup
- **Health Checks**: Comprehensive health monitoring with dependency validation
- **Logging**: Structured logging with Logfire integration
- **Security**: API key management through environment variables

## Key Components

### Backend
-   **API Routers (`devboard/api/routers`)**: Define the RESTful API endpoints for different domains (projects, codebases, configurations, tasks, QA, settings). They handle request parsing, validation, and delegate to services for business logic.
-   **Database Repositories (`devboard/db/repositories`)**: Provide an abstraction layer for database operations, encapsulating CRUD logic for various models (e.g., `ProjectRepository`, `CodebaseRepository`).
-   **Services (`devboard/services`)**: Implement the core business logic of the application. Examples include `CodebaseInvestigationService` (for analyzing codebases and generating documentation), `ConfigService` (for managing configurations), and `TaskPlanningAgent` (for AI-driven task planning).
-   **Context Providers (`devboard/context_providers`)**: Modules that abstract the retrieval of context from different sources (e.g., `GitHubContextProvider`, `JiraContextProvider`, `SlackContextProvider`, `WebpageContextProvider`). They normalize data from external systems.
-   **Integrations (`devboard/integrations`)**: Handle the direct communication and interaction with external APIs (e.g., GitHub, Jira, Slack).

### Frontend
-   **UI Component Library (`frontend/src/components/ui`)**: Standardized, reusable UI components with consistent theming, variants, and error handling. Includes Button, Card, Input, Modal, StatusBadge, and form components.
-   **Custom Hooks (`frontend/src/hooks`)**: Type-safe data fetching hooks that encapsulate API calls with loading states, error handling, and refetch capabilities. Includes generic `useApi` and domain-specific hooks like `useProjects`, `useTasks`.
-   **Design System (`frontend/src/styles`)**: Centralized design tokens including color palette, typography scales, layout utilities, and standardized input styling for consistent theming across all components.
-   **Components (`frontend/src/components`)**: Reusable UI elements and complex components such as Chat, ConfigurationForm, and Layout components that use the standardized UI library.
-   **Views (`frontend/src/views`)**: Top-level components representing distinct pages (ProjectDashboard, TaskDetail, Codebases, Settings). Refactored to use standardized UI components and custom hooks for consistent UX.
-   **API Client (`frontend/src/lib/api.ts`)**: Typed HTTP client with comprehensive TypeScript interfaces, abstracting API calls from UI components with proper error handling and response typing.

## API Endpoints

The backend exposes a RESTful API with the following main endpoint categories:

### Projects API (`/api/projects`)
-   `GET /api/projects/`: List all projects.
-   `POST /api/projects/`: Create a new project.
-   `GET /api/projects/{project_id}`: Get details of a specific project.
-   `PATCH /api/projects/{project_id}`: Update an existing project.
-   `DELETE /api/projects/{project_id}`: Delete a project.
-   `GET /api/projects/{project_id}/tasks`: List all tasks associated with a project.
-   `GET /api/projects/{project_id}/resources`: Get all context provider resources for a project.
-   `POST /api/projects/{project_id}/resources`: Add a context provider resource to a project.
-   `DELETE /api/projects/{project_id}/resources/{resource_id}`: Remove a context provider resource from a project.

**Request/Response Schemas (Pydantic)**:
-   `ProjectCreate`: `name` (str), `details` (str), `current_status` (str)
-   `ProjectUpdate`: `name` (str, optional), `details` (str, optional), `current_status` (str, optional)
-   `ProjectResponse`: `id` (int), `name` (str), `details` (str), `current_status` (str), `created_at` (datetime)
-   `ProjectResourceCreate`: `resource_uri` (str), `description` (str, optional)
-   `ResourceResponse`: `id` (int), `resource_uri` (str), `description` (str, optional)
-   `DeleteResponse`: `message` (str), `success` (bool)

### Codebases API (`/api/codebases`)
-   `GET /api/codebases/`: List all registered codebases.
-   `POST /api/codebases/`: Create a new codebase.
-   `GET /api/codebases/{codebase_id}`: Get details of a specific codebase.
-   `PATCH /api/codebases/{codebase_id}`: Update an existing codebase.
-   `DELETE /api/codebases/{codebase_id}`: Delete a codebase.
-   `GET /api/codebases/{codebase_id}/architecture_document/`: Get complete architecture document information (content, hash, path, size).
-   `PUT /api/codebases/{codebase_id}/architecture_document/`: Update the architecture document with conflict detection.
-   `POST /api/codebases/{codebase_id}/architecture_document/generate`: Generate or update the architecture document using AI.
-   `GET /api/codebases/{codebase_id}/architecture/status` (Deprecated): Get architecture document status.
-   `GET /api/codebases/{codebase_id}/architecture/content` (Deprecated): Get architecture document content.

**Request/Response Schemas (Pydantic)**:
-   `CodebaseCreate`: `name` (str), `description` (str), `local_path` (str)
-   `CodebaseUpdate`: `name` (str, optional), `description` (str, optional), `repository_url` (str, optional), `local_path` (str, optional)
-   `CodebaseResponse`: `id` (int), `name` (str), `description` (str), `repository_url` (str, optional), `local_path` (str)
-   `ArchitectureDocumentResponse`: `exists` (bool), `content` (str, optional), `content_hash` (str, optional), `file_path` (str, optional), `size_bytes` (int, optional)
-   `ArchitectureUpdateRequest`: `content` (str), `original_hash` (str, optional)
-   `ArchitectureUpdateResponse`: `success` (bool), `content_hash` (str, optional), `message` (str, optional), `error_type` (str, optional), `current_hash` (str, optional)
-   `ArchitectureGenerationResponse`: `success` (bool), `file_path` (str, optional), `content` (str, optional), `error_message` (str, optional), `error_type` (str, optional)

### Configurations API (`/api/configurations`)
-   `GET /api/configurations/`: List all configurations, optionally filtered by key prefix.
-   `GET /api/configurations/{config_key}`: Get a specific configuration.
-   `GET /api/configurations/{config_key}/detail`: Get detailed configuration with field-level source information.
-   `POST /api/configurations/`: Create or update a configuration.
-   `PATCH /api/configurations/{config_key}`: Update a configuration.
-   `PATCH /api/configurations/{config_key}/fields`: Update specific configuration fields while respecting environment variable precedence.
-   `DELETE /api/configurations/{config_key}`: Delete a configuration.

**Request/Response Schemas (Pydantic)**:
-   `ConfigurationCreate`: `key` (str), `value_json` (str), `schema_version` (str)
-   `ConfigurationUpdate`: `value_json` (str, optional), `schema_version` (str, optional)
-   `ConfigurationResponse`: `key` (str), `value_json` (str), `schema_version` (str), `updated_at` (datetime)
-   `ConfigurationDetailResponse`: `key` (str), `fields` (list[ConfigurationFieldInfo]), `validation_status` (str), `validation_errors` (list[str], optional)

### Tasks API (`/api/tasks`)
-   `GET /api/tasks/`: List all tasks.
-   `POST /api/tasks/`: Create a new task.
-   `GET /api/tasks/{task_id}`: Get details of a specific task.
-   `PATCH /api/tasks/{task_id}`: Update an existing task.
-   `DELETE /api/tasks/{task_id}`: Delete a task.
-   `POST /api/tasks/{task_id}/state-transition`: Trigger task state transition with optional AI agent assistance.

### Conversations API (`/api/conversations`)
**Unified conversation endpoints for all entity types (projects, tasks, codebases)**

-   `GET /api/conversations/{conversation_id}/messages`: Retrieve conversation message history.
-   `POST /api/conversations/{conversation_id}/messages`: Send a message to the agent.
-   `POST /api/conversations/{conversation_id}/approve-tools`: Approve or deny tool execution requests.
-   `DELETE /api/conversations/{conversation_id}/messages`: Clear all messages in a conversation.

**Request/Response Schemas (Pydantic)**:
-   `ChatRequest`: `message` (str)
-   `ToolApprovalRequest`: `approvals` (dict[str, bool])
-   `PromptResponse`: `type` (MESSAGE | TOOL_REQUEST), `message` (str, optional), `tool_requests` (list, optional)
-   `ConversationMessage`: `id` (int), `role` (str), `text_content` (str), `timestamp` (datetime)
-   `DeleteResponse`: `message` (str), `success` (bool)

### Other Routers
-   `/api/settings`: For managing application settings (specific endpoints not detailed here).

### General Endpoints
-   `GET /`: Health check endpoint, returns `{"message": "DevBoard API is running"}`.
-   `GET /health`: Detailed health check, returns `{"status": "healthy", "version": "0.1.0", "database": "connected"}`.

**Authentication and Authorization**: Not explicitly defined in the provided router code snippets, but typically handled by FastAPI dependencies or middleware.
**Rate Limiting and Error Handling**: FastAPI's default error handling is used, with custom `HTTPException` for specific error scenarios (e.g., 404 Not Found, 400 Bad Request, 409 Conflict for architecture document updates). Rate limiting is not explicitly implemented in the provided code.

## Data Models

### Database Schemas (SQLAlchemy)
The backend uses SQLAlchemy for ORM, with models defined in `devboard/db/models`. These models represent the entities stored in the relational database. Examples include:
-   **Project**: Represents a development project.
-   **Task**: Represents a development task.
-   **Codebase**: Represents a code repository or local codebase.
-   **Conversation**: Container for agent conversations with polymorphic parent entity association.
-   **ConversationMessage**: Individual messages within a conversation (supports PydanticAI message format).
-   **Configuration**: Stores application configurations.
-   **ContextProviderResource**: External resources linked to projects.
-   **Document**: Generic document storage with content hashing.

Alembic is used for managing database migrations, ensuring schema evolution is tracked and applied.

### Data Structures and Entities (Pydantic)
Pydantic models are extensively used for data validation, serialization, and deserialization, especially for API request and response bodies. These schemas mirror the database models but are tailored for API interaction. Examples include:
-   `ProjectBase`, `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`
-   `CodebaseBase`, `CodebaseCreate`, `CodebaseUpdate`, `CodebaseResponse`
-   `ConfigurationBase`, `ConfigurationCreate`, `ConfigurationUpdate`, `ConfigurationResponse`
-   `ArchitectureDocumentResponse`, `ArchitectureUpdateRequest`, `ArchitectureUpdateResponse`
-   `ResourceResponse`, `ProjectResourceCreate`

### Relationships Between Entities
Relationships between entities (e.g., Projects having Tasks, Projects having Resources) are defined within the SQLAlchemy models and reflected in the API schemas where appropriate.

## Configuration & Environment

-   **Environment Variables**: Loaded from `.env` files (in the current directory or home directory) using `python-dotenv`. These are used for sensitive information (e.g., API keys) and environment-specific settings.
-   **Configuration Files**: The `backend/devboard/config` directory contains Python modules for managing various configurations, including `agent_config.py`, `llm_config.py`, `integration_configs.py`, and `logfire_config.py`. These define structured configuration settings.
-   **Deployment Considerations**: The `docker-compose.yml` file orchestrates the deployment of the backend and potentially other services (like a database). The `backend/Dockerfile` defines the build process for the backend application.
-   **External Service Integrations**: Configuration for integrations like Jira, GitHub, and Slack are managed through the `devboard/config/integration_configs.py` and potentially through the `/api/configurations` endpoints.

## Development Patterns

### Backend Patterns
-   **Code Organization**: The backend follows a modular structure, separating concerns into `api`, `db`, `services`, `context_providers`, and `integrations` directories.
-   **API Design**: RESTful API principles are applied, with clear resource-based URLs and standard HTTP methods.
-   **Dependency Injection**: FastAPI's dependency injection system is used extensively, particularly for database sessions (`Depends(get_db)`) and service instances.
-   **Pydantic for Data Validation**: Pydantic models are used for strict data validation and serialization for all API inputs and outputs, ensuring data integrity.
-   **SQLAlchemy ORM**: The backend uses SQLAlchemy for object-relational mapping, abstracting database interactions and promoting a Pythonic way of working with data.
-   **Type Hinting**: Python type hints are used throughout the backend for improved code readability, maintainability, and static analysis.
-   **Error Handling**: Custom `HTTPException` instances are raised in API endpoints to return appropriate HTTP status codes and error messages to the client.

### Frontend Patterns
-   **Component Architecture**: React components are organized into a three-tier structure: reusable UI components (`components/ui/`), complex feature components (`components/`), and page-level views (`views/`).
-   **Custom Hooks Pattern**: Data fetching logic is encapsulated in custom hooks that provide consistent loading states, error handling, and refetch capabilities across all components.
-   **Design System Approach**: Centralized design tokens and utility classes ensure consistent styling and theming across all UI components.
-   **Type-Safe API Integration**: TypeScript interfaces and custom hooks provide end-to-end type safety from API responses to UI components.
-   **Theme-Aware Components**: All UI components support light/dark mode switching with Tailwind CSS classes and proper contrast ratios.
-   **Error Boundary Strategy**: React error boundaries and standardized error components provide graceful error handling and user feedback.
-   **Consistent Form Patterns**: Standardized form components with labels, validation, and error states provide consistent user experience across all forms.

## Testing Strategy

-   **Backend Testing**:
    -   **Framework**: `pytest` and `pytest-asyncio` are used for writing unit and integration tests.
    -   **Test Organization**: Tests are located in the `backend/tests` directory, mirroring the structure of the `devboard` module (e.g., `test_projects_router.py` for `projects.py` router).
    -   **Coverage**: The `pyproject.toml` indicates a focus on code quality with `ruff` and `pyright`, suggesting an emphasis on well-tested and type-safe code.
-   **Frontend Testing**:
    -   **Framework**: `vitest` is used for unit and component testing, along with `@testing-library/react` for testing React components in a user-centric way.
    -   **Test Organization**: Tests are typically co-located with the components or modules they test, or in dedicated `__tests__` directories (e.g., `frontend/src/components/__tests__`).
    -   **Tools**: `@vitest/ui` for interactive test runner, `jsdom` for DOM environment, `msw` for API mocking.
    -   **Coverage**: `vitest run --coverage` command is available for generating test coverage reports.

## Deployment & Operations

-   **Build Process**:
    -   **Backend**: The `backend/Dockerfile` defines the steps to build a Docker image for the FastAPI application, including dependency installation and application setup.
    -   **Frontend**: `npm run build` (which executes `tsc -b && vite build`) compiles TypeScript and bundles the React application for production.
-   **Deployment Pipeline**: The `docker-compose.yml` file is used to define and run multi-container Docker applications. This facilitates local development and can be adapted for production deployments.
-   **Monitoring and Logging**: `logfire` is integrated into the FastAPI application for structured logging and tracing, which is crucial for monitoring application health and performance in production environments.

## Getting Started

### Prerequisites for Development
-   **Docker**: For running the database and other services.
-   **Python 3.12+**: For backend development.
-   **Node.js (LTS recommended)**: For frontend development.
-   **uv**: Python package installer and resolver (implied by `uv.lock`).
-   **npm/yarn**: Node.js package manager.

### Setup Instructions

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd DevBoard
    ```

2.  **Backend Setup**:
    ```bash
    cd backend
    uv venv  # Create a virtual environment
    source .venv/bin/activate # Activate the virtual environment
    uv sync  # Install dependencies
    alembic upgrade head # Run database migrations
    ```

3.  **Frontend Setup**:
    ```bash
    cd frontend
    npm install # Install Node.js dependencies
    ```

4.  **Docker Services**:
    ```bash
    cd .. # Go back to the project root
    docker-compose up -d # Start database and other services in the background
    ```

### How to Run Tests

-   **Backend Tests**:
    ```bash
    cd backend
    source .venv/bin/activate
    pytest
    ```

-   **Frontend Tests**:
    ```bash
    cd frontend
    npm test # Runs vitest
    npm run test:ui # Runs vitest with a UI
    npm run test:coverage # Runs vitest and generates coverage report
    ```

### How to Run the Application

1.  **Ensure Docker services are running**:
    ```bash
    cd .. # Go back to the project root
    docker-compose up -d
    ```

2.  **Start the Backend API**:
    ```bash
    cd backend
    source .venv/bin/activate
    uvicorn devboard.api.main:app --reload --port 8000
    ```
    The API will be accessible at `http://localhost:8000`.

3.  **Start the Frontend Development Server**:
    ```bash
    cd frontend
    npm run dev
    ```
    The frontend application will typically be accessible at `http://localhost:5173` (or another port specified by Vite).

## AI Agent System Implementation

### Agent Architecture Implementation

The DevBoard AI agent system is built on **PydanticAI framework** with specialized agent types that understand project context and collaborate through structured document editing.

#### Core Agent Implementation

**BaseAgent Class (`devboard/agents/base_agent.py`)**:
The foundation class providing common functionality for all AI agents including LLM service integration, configuration management, and conversation history tracking. Handles context assembly, prompt construction, and response generation patterns.

**Agent Configuration System**:
- **Multi-Provider Support**: Configurable LLM providers (OpenAI, Anthropic, Google) managed via `devboard/config/llm_config.py`
- **Model Hierarchy**: Fallback configuration with preferred models defined in agent-specific configurations
- **Agent-Specific Settings**: Temperature, max tokens, and behavior parameters stored in database configurations
- **Dynamic Model Selection**: Runtime model switching based on availability implemented in `LLMService`

#### Implemented Agent Types

**Project Q&A Agent (`devboard/agents/project_agent.py`)**:
Specialized agent for handling project-level questions and collaborative specification editing. Assembles context from multiple sources (GitHub, Jira, Slack, codebases) and generates contextually aware responses. Supports conversational document editing workflows with user approval patterns.

**Task Planning Agents (`devboard/agents/task_agent.py`)**:
- **Specification Agent**: Active during task definition phase, focuses on requirements gathering and task specification development
- **Planning Agent**: Creates detailed implementation strategies during planning phase
- **State-Aware Prompting**: Different behaviors and prompting strategies based on task lifecycle phase

**Codebase Investigation Agent (`devboard/services/codebase_investigation.py`)**:
Analyzes code repositories to generate and maintain living architecture documentation. Performs comprehensive code analysis, generates structured documentation using templates from `devboard/services/template_service.py`, and supports incremental updates based on codebase changes.

#### Agent Conversation Service Implementation

**AgentConversationService (`devboard/services/agent_conversation.py`)**:
Central orchestration service managing agent conversations with persistence and tool approval workflows. Constructor takes `conversation_id` as first parameter, eliminating need to pass it to each method call. Key methods include `send_message(message)` for user prompts, `process_tool_approvals(approvals)` for deferred tool execution, `store_new_messages(messages)` for persistence, and `clear_messages()` for conversation history deletion. Handles message processing with context assembly, tool call management with user approval workflows, and conversation persistence across sessions. Automatically detects and cleans up pending tool calls when user sends new message instead of approving tools. Integrates with unified `ConversationRepository` and PydanticAI framework for structured agent interactions.

#### Context Assembly Implementation

**ContextAssemblyService (`devboard/services/context_assembly.py`)**:
- **Multi-Source Integration**: Combines data from GitHub, Jira, Slack, and local codebases through pluggable provider architecture
- **Strategy-Based Loading**: EAGER vs ON_DEMAND resource retrieval patterns based on resource size and access patterns
- **URI-Based Resource System**: Standardized resource identification across providers using URI patterns
- **Context Caching**: Intelligent caching with TTL for performance optimization implemented in-memory

#### Message Persistence Implementation

**Unified Conversation System (`devboard/db/models/`)**:
Implements polymorphic conversation architecture supporting all entity types (Projects, Tasks, Codebases) through unified models:

**Conversation Model (`conversation.py`)**:
Container model with polymorphic parent entity association using `parent_entity_type` enum (PROJECT, TASK, CODEBASE) and `parent_entity_id`. Enforces one conversation per entity via unique constraint on (parent_entity_type, parent_entity_id). Supports nested conversations through `parent_conversation_id` for future agent-to-agent communication. Conversations are created lazily via `get_or_create_for_entity()` when accessing entity details, ensuring every entity has an associated conversation without explicit API calls.

**ConversationMessage Model (`messages.py`)**:
Unified message model storing all conversation messages with support for structured PydanticAI message format. Fields include `message_type` enum (USER_PROMPT, TEXT_RESPONSE, TOOL_CALL, TOOL_RESULT, STRUCTURED_RESPONSE), `pydantic_content` JSON storage for complete message structure, and `text_content` for quick text access. Provides temporal ordering and role-based messaging across all entity types.

**ConversationRepository (`devboard/db/repositories/conversation.py`)**:
Unified repository providing conversation management across all entity types. Key methods include `get_or_create_for_entity(entity_type, entity_id)` for lazy conversation initialization (called by entity GET endpoints), `create_message(conversation_id, pydantic_message)` for PydanticAI message persistence, `get_messages(conversation_id, exclude_tool_calls=False)` with optional tool call filtering, `delete_messages(conversation_id)` for clearing history, and `convert_messages_to_pydantic(message_records)` for reconstructing PydanticAI message objects from database records.

### Document Collaboration Implementation

#### Structured Document Editing

**DocumentEditorService (`devboard/services/document_editor.py`)**:
Handles collaborative document editing with conflict detection using content hashing for version control. Implements atomic edit application with user approval workflows for all changes. Supports find-and-replace operations with rollback capabilities and maintains edit history for audit trails.

**Document Templates (`devboard/services/template_service.py`)**:
- **Task Specification Schema**: Structured requirements templates with predefined sections for objectives, requirements, and acceptance criteria
- **Implementation Plan Schema**: Technical execution templates with analysis, implementation steps, and testing strategies  
- **Architecture Document Schema**: Codebase documentation templates with overview, component architecture, and development patterns

#### Tool System Implementation

**Agent Tools (`devboard/agents/tools.py`)**:
Specialized PydanticAI tools providing agent capabilities including document content editing, context resource research, and codebase structure analysis. Tools are decorated with PydanticAI's `@tool` decorator and provide structured interfaces for agent interactions with external systems and document modification workflows.

## Database Schema & Models Implementation

### SQLAlchemy Model Architecture

The database layer uses **SQLAlchemy 2.0** with modern patterns including `Mapped[T]` type annotations, `select()` statement patterns, and full async support.

#### Core Entity Models

**Project Model (`devboard/db/models/project.py`)**:
Core entity representing development projects with specification document relationships, task collections, codebase associations, and context resource links. Uses eager loading for specification documents and many-to-many relationships for shared resources. Implements cascade deletion for owned documents.

**Task Model (`devboard/db/models/task.py`)**:
Represents discrete work units with lifecycle state management (DEFINING → DESIGNING → PLANNING → IMPLEMENTING → IN REVIEW → COMPLETE). Links to external systems via `external_id` and maintains separate specification and plan documents. Includes project relationship and state-based filtering capabilities.

**Document Model (`devboard/db/models/document.py`)**:
Generic document storage with content hashing for conflict detection using SHA-256. Supports different document types (specifications, plans, architecture docs) with template versioning. Implements content diffing and collaborative editing features.

**Conversation Model (`devboard/db/models/conversation.py`)**:
Central conversation container with polymorphic parent entity support. Uses `parent_entity_type` enum (PROJECT, TASK, CODEBASE) and `parent_entity_id` for flexible entity association. Unique constraint ensures one conversation per entity. Supports nested conversations via `parent_conversation_id` for agent-to-agent communication patterns.

**ConversationMessage Model (`devboard/db/models/messages.py`)**:
Unified message storage for all conversation types. Fields include `conversation_id` foreign key, `message_type` enum for message classification, `pydantic_content` JSON for full PydanticAI message structure, `text_content` for extracted text, and `timestamp` for ordering. Replaces previous entity-specific message models with single unified implementation.

#### Association Tables & Many-to-Many Relationships

**Resource Sharing Implementation (`devboard/db/models/base.py`)**:
Association tables implementing many-to-many relationships between projects and codebases, and between projects and context provider resources. Enables resource sharing across multiple projects while maintaining referential integrity. Uses composite primary keys for efficient lookups and prevents duplicate associations.

#### Configuration Storage Implementation

**Configuration Model (`devboard/db/models/configuration.py`)**:
Hierarchical configuration storage supporting JSON serialization with schema versioning. Implements key-based lookup with dot notation support (e.g., `agent.qa.default`). Includes automatic timestamp tracking for configuration updates and supports environment variable override patterns.

**ContextProviderResource Model (`devboard/db/models/configuration.py`)**:
Stores external resource references with URI-based identification, provider type classification, and optional user descriptions. Implements unique constraints on resource URIs and supports sharing across multiple projects through association tables.

### Repository Pattern Implementation

**Generic Repository Base (`devboard/db/repositories/base.py`)**:
Type-safe repository base class providing common CRUD operations with generic type support. Implements standard database patterns including get-by-id, get-all, create, update, and delete operations. Uses SQLAlchemy 2.0 patterns with `select()` statements and session management. Provides transaction boundary management and automatic flush handling.

**Specialized Repositories**:
- **ProjectRepository (`devboard/db/repositories/project.py`)**: Project-specific queries with eager loading of specification documents and relationship management
- **TaskRepository (`devboard/db/repositories/task.py`)**: Task filtering by project and state with lifecycle management support
- **ConversationRepository (`devboard/db/repositories/conversation.py`)**: Unified conversation management for all entity types with polymorphic parent resolution
- **DocumentRepository (`devboard/db/repositories/document.py`)**: Content hashing and conflict detection for collaborative editing workflows
- **ContextProviderResourceRepository (`devboard/db/repositories/context_provider_resource.py`)**: URI-based resource management with project association handling

### Database Migration Strategy

**Alembic Configuration**:
- **Auto-generated Migrations**: Schema changes tracked automatically
- **Version Control**: All migrations stored in version control
- **Production Safety**: Migration validation and rollback capabilities
- **Data Migration**: Support for complex data transformations during schema updates

## Context Provider Implementation Patterns

### Context Provider Architecture

The DevBoard context system implements a **pluggable provider architecture** that standardizes how external data sources are integrated and accessed by AI agents.

#### Provider Interface Implementation

**Base Context Provider (`devboard/context_providers/base.py`)**:
Abstract base class defining the contract for all context providers. Requires implementation of provider type identification, context retrieval methods, and retrieval strategy determination. Establishes common patterns for URI validation, context data structures, and error handling across all provider implementations.

#### Implemented Context Providers

**GitHub Context Provider (`devboard/context_providers/github.py`)**:
Provides context from GitHub repositories, issues, and pull requests. Parses GitHub URLs for repos, issues, PRs, and commits, fetches data via GitHub API integration using `devboard/integrations/github.py`. Implements smart retrieval strategies where small resources (issues, PRs) use EAGER loading and large resources (full repos) use ON_DEMAND loading.

**Jira Context Provider (`devboard/context_providers/jira.py`)**:
Handles Jira issues, projects, and boards with URL pattern validation for Jira instances and issue key formats. Fetches issue details, comments, and attachments through the Jira integration layer. Supports both cloud and server Jira instances with configurable base URLs.

**Slack Context Provider (`devboard/context_providers/slack.py`)**:
Integrates with Slack channels and conversations, parsing Slack message and channel URLs. Fetches conversation threads and channel history via Slack Web API. Formats conversation context with proper threading and user identification for agent consumption.

**Codebase Context Provider (`devboard/context_providers/codebase.py`)**:
Analyzes local and remote code repositories through file system access and Git operations. Generates architecture summaries and file listings using template-based documentation generation. Uses EAGER loading for architecture documents and ON_DEMAND loading for full codebase analysis.

**Web Page Context Provider (`devboard/context_providers/webpage.py`)**:
Fetches and processes HTML content from documentation sites and web pages. Extracts relevant text content and metadata while filtering out navigation and advertising content. Implements content cleaning and structure preservation for agent consumption.

### Context Assembly Service Implementation

**Resource Resolution Strategy (`devboard/services/context_assembly.py`)**:
Central orchestration service that coordinates context gathering from multiple providers. Maintains provider registry with GitHub, Jira, Slack, codebase, and webpage providers. Implements resource categorization by retrieval strategy (EAGER vs ON_DEMAND) and parallel context loading for performance. Assembles complete context packages for agent consumption including project resources, query context, and on-demand resource references.

#### URI-Based Resource System

**Resource URI Standards**:
Standardized URI patterns implemented across all providers for consistent resource identification. GitHub patterns support repositories, issues, pull requests, and commits. Jira patterns handle both cloud and server instances for issues and projects. Slack patterns support message permalinks and channel URLs. Each provider implements regex-based URI validation and parsing for robust resource handling.

**Resource Validation Implementation (`devboard/services/resource_service.py`)**:
Manages context provider resources with comprehensive validation including provider discovery, URI format validation, and resource accessibility testing. Creates database resource records with automatic provider type detection and project linking. Implements error handling for unsupported URIs and unavailable resources with detailed error messaging for user feedback.

### Integration Layer Implementation

#### External API Integration

**GitHub Integration (`devboard/integrations/github.py`)**:
Handles GitHub API authentication using personal access tokens with httpx async client. Provides methods for fetching repository information, issue details with comments, and pull request data with reviews. Implements rate limiting awareness and error handling for GitHub API responses.

**Jira Integration (`devboard/integrations/jira.py`)**:
Manages Jira API authentication using email and API token combination for both cloud and server instances. Supports configurable base URLs for different Jira deployments. Fetches issue details with expandable fields and project information with proper authentication handling.

**Slack Integration (`devboard/integrations/slack.py`)**:
Implements Slack Web API integration using bot tokens for workspace access. Handles conversation history retrieval and thread reply fetching with proper message threading. Manages Slack-specific authentication patterns and API response formatting.

#### Error Handling & Resilience

**Provider Error Handling (`devboard/context_providers/__init__.py`)**:
Comprehensive exception hierarchy including `ContextProviderUnavailable`, `NoProviderFound`, and `UnsupportedResourceUriError` for different failure scenarios. Implements graceful degradation patterns where unavailable providers don't prevent agent operation. Includes structured logging for debugging and monitoring provider health.

### Performance & Caching Implementation

**Context Caching Strategy**:
In-memory caching system with configurable TTL (default 5 minutes) for context data optimization. Implements cache-aside pattern with automatic cache invalidation and fresh data fetching. Reduces external API calls and improves agent response times for frequently accessed resources.

## Dependency Injection Architecture

### FastAPI Dependency System Implementation

DevBoard leverages **FastAPI's dependency injection system** extensively to manage service lifecycles, database sessions, and cross-cutting concerns like authentication and logging.

#### Core Dependency Patterns

**Database Session Management (`devboard/api/dependencies/repositories.py`)**:
Provides repository instances with automatically managed database sessions through FastAPI's dependency injection. Each repository receives a database session from the `get_db` dependency, ensuring proper transaction boundaries and connection lifecycle management across all API endpoints.

**Service Layer Dependencies (`devboard/api/dependencies/services.py`)**:
Orchestrates complex service dependencies including context assembly services with multiple integration dependencies (GitHub, Jira, Slack). Implements dependency composition where higher-level services receive all required lower-level dependencies automatically. Handles optional integration dependencies with graceful fallback when services are unavailable.

**Agent Dependencies (`devboard/api/dependencies/agents.py`)**:
Provides agent conversation services with full context assembly, LLM service integration, and dynamic agent configuration. Key dependency `get_conversation_agent(conversation_id)` resolves appropriate agent type (ProjectAgent, TaskAgent, CodebaseAgent) by querying the conversation's parent_entity_type from the database. Retrieves agent-specific configuration from the config service and composes the complete agent conversation service with all required dependencies including conversation repository and context services. This dependency-based agent resolution enables the unified conversation endpoints to work with any entity type.

#### Entity Validation Dependencies

**Entity Verification (`devboard/api/dependencies/entities.py`)**:
Provides entity validation dependencies that verify entity existence and return the entity or raise appropriate HTTP 404 errors. Includes verification functions for projects, tasks, and codebases that integrate with repository dependencies to perform database lookups and error handling consistently across all API endpoints.

#### Configuration Dependencies

**Configuration Service Integration**:
Provides configuration service with database backing through repository dependency injection. Includes LLM service creation with dynamic configuration retrieval, enabling runtime configuration updates without service restart. Implements configuration hierarchy with environment variable overrides and database fallbacks.

#### Integration Dependencies

**External Service Integration Management**:
Manages optional external service integrations with configuration-based instantiation. Handles GitHub, Jira, and Slack integrations with graceful degradation when credentials are not available. Returns `None` for unavailable integrations, allowing services to operate with reduced functionality rather than failing completely.

### Service Layer Architecture

#### Service Composition Pattern

**Layered Service Architecture**:
Implements base service patterns with repository dependencies and composed services with multiple service dependencies. The `AgentConversationService` exemplifies complex service composition, orchestrating context assembly, message persistence, LLM interactions, and response formatting through coordinated service calls. Services follow dependency inversion principles with interface-based dependencies.

#### Repository Lifecycle Management

**Repository Pattern with Dependency Injection**:
Generic repository base class with dependency-injected database sessions providing context manager support for transaction boundary management. Repositories automatically handle commit/rollback patterns and are injected into API endpoints through FastAPI's dependency system. Enables consistent transaction management across all database operations.

### Configuration Management Implementation

#### Hierarchical Configuration System

**Multi-Source Configuration Resolution (`devboard/services/config_service.py`)**:
Manages configuration from multiple sources with precedence hierarchy: environment variables (highest), database configuration, and default values (lowest). Implements dot notation key support with automatic environment variable mapping (e.g., `agent.qa.default` → `AGENT_QA_DEFAULT`). Provides Pydantic schema validation with structured error reporting for configuration validation.

#### Agent Configuration Management

**Dynamic Agent Configuration**:
Manages agent-specific configuration with runtime validation and fallback mechanisms. Retrieves validated agent configurations with model hierarchy support for LLM provider fallbacks. Implements default configuration patterns when validation fails, ensuring agents can operate with sensible defaults even when configuration is incomplete or invalid.

### Error Handling & Middleware Implementation

#### Global Error Handling

**Custom Exception Handlers (`devboard/api/main.py`)**:
Global exception handling with structured error responses for HTTP exceptions and Pydantic validation errors. Provides consistent error response format across all endpoints with error type classification, detailed messages, and request path context. Integrates with Logfire for error tracking and monitoring.

#### Request Lifecycle Middleware

**Request Context and Logging**:
HTTP middleware adding request context including unique request IDs, timing information, and structured logging. Tracks request lifecycle from start to completion with duration metrics and response status codes. Adds request ID headers to responses for distributed tracing and debugging support.

## Frontend Component System Implementation

### UI Component Library Architecture

The DevBoard frontend implements a **comprehensive design system** with reusable, theme-aware components that provide consistent user experience across all views.

#### Core UI Components (`frontend/src/components/ui/`)

**Button Component (`Button.tsx`)**:
Standardized button component with multiple variants (primary, secondary, outline, ghost), sizes (sm, md, lg), and loading states. Supports icon integration and disabled states with proper accessibility attributes. Implements consistent focus states and transition animations for improved user experience.

**Card Component (`Card.tsx`)**:
Flexible container component with configurable padding options (none, sm, md, lg) and optional hover effects. Provides consistent border radius, shadow, and background theming across light and dark modes. Used as the foundation for content sections throughout the application.

**Input Component (`Input.tsx`)**:
Form input component with integrated labels, error states, help text, and icon support (left/right icons). Implements standardized focus states, error styling, and proper accessibility attributes. Supports all standard HTML input props while maintaining consistent theming.

**Textarea Component (`Textarea.tsx`)**:
Multi-line text input with the same theming and functionality as the Input component. Includes proper resize handling and maintains font family consistency for code editing use cases.

**Modal Component (`Modal.tsx`)**:
Reusable modal with proper focus management, backdrop handling, and responsive sizing (sm, md, lg, xl). Implements escape key handling, click-outside-to-close, and accessibility best practices with ARIA attributes.

**StatusBadge Component (`StatusBadge.tsx`)**:
Status indicator component with semantic color variants (default, success, warning, error, info) and sizes. Provides consistent status visualization across different data types and states throughout the application.

**Error Handling Components**:
- **ErrorBoundary (`ErrorBoundary.tsx`)**: React class component for catching JavaScript errors with graceful fallback UI and reload functionality
- **ErrorMessage (`ErrorMessage.tsx`)**: Standardized error display with retry actions and consistent error messaging patterns

#### Design System Implementation (`frontend/src/styles/`)

**Design System Utilities (`designSystem.ts`)**:
Centralized design tokens including color palette definitions, text color utilities, border color patterns, focus states, transition classes, and common layout patterns. Provides consistent design language across all components with Tailwind CSS class abstractions.

**Input Styling System (`inputStyles.ts`)**:
Comprehensive styling system for form elements with standardized classes for different input types (base inputs, chat inputs, textareas, feedback inputs). Includes disabled states and theme-aware styling for consistent form experiences.

### Custom Hooks Architecture (`frontend/src/hooks/`)

#### Generic API Hook Pattern

**useApi Hook (`useApi.ts`)**:
Generic data fetching hook providing consistent patterns for loading states, error handling, and data refetching. Implements TypeScript generics for type-safe API responses and supports both immediate and deferred loading patterns.

**useMutation Hook (`useMutation.ts`)**:
Handles mutation operations (POST, PUT, PATCH, DELETE) with loading states and error handling. Provides promise-based return values for operation chaining and supports TypeScript generics for type-safe parameter passing.

#### Domain-Specific Hooks

**useProjects Hook (`useProjects.ts`)**:
Project management operations including fetching project lists, individual projects, creating, updating, and deleting projects. Encapsulates all project-related API calls with consistent loading and error states.

**useTasks Hook (`useTasks.ts`)**:
Task management operations for project tasks, individual task details, and task lifecycle management. Provides type-safe interfaces for task creation, updates, and status transitions.

**useCodebases Hook (`useCodebases.ts`)**:
Codebase management operations including codebase CRUD operations, architecture document management, and codebase analysis workflows.

### Component Refactoring Implementation

#### ProjectDashboard Refactoring

**Before**: 189-line monolithic component with inline styling, manual state management, and direct API calls
**After**: 175-line component using standardized UI components, custom hooks, and design system utilities

**Key Improvements**:
- Replaced direct `apiClient` calls with `useProjects()` and `useCreateProject()` hooks
- Eliminated inline modal implementation in favor of reusable `Modal` component
- Replaced manual form elements with `Input`, `Textarea`, and `Button` components
- Added comprehensive error handling with `ErrorMessage` component
- Implemented design system utilities for consistent spacing and colors

#### TaskDetail Refactoring

**Before**: Large component with complex state management and inconsistent styling
**After**: Refactored to use standardized UI components and custom hooks for data operations

**Key Improvements**:
- Integrated `useTask()` and `useUpdateTask()` hooks for API operations
- Replaced task status display with `StatusBadge` component
- Standardized all buttons with `Button` component variants
- Implemented consistent error handling and loading states
- Used `Card` components for content sections

### Theme System Implementation

#### Dark Mode Support

**DarkModeContext (`contexts/DarkModeContext.tsx`)**:
React context providing theme state management with localStorage persistence and system preference detection. Integrates with Tailwind CSS dark mode classes for seamless theme switching across all components.

**Theme-Aware Component Design**:
All UI components implement comprehensive dark mode support using Tailwind's `dark:` prefixes. Ensures proper contrast ratios and accessibility compliance across light and dark themes.

### Performance Optimizations

#### Efficient Data Fetching

**Custom Hooks with Caching**:
Data fetching hooks implement intelligent caching patterns to minimize API calls and improve user experience. Includes refetch capabilities for manual data refresh and automatic error retry mechanisms.

**Component Optimization**:
Strategic use of React patterns to minimize re-renders and optimize component performance. Proper dependency arrays in useEffect hooks and intelligent state management reduce unnecessary computations.

### Testing Integration

#### Component Testing

**UI Component Tests**:
Comprehensive test coverage for all UI components using React Testing Library with proper accessibility testing and interaction verification. Tests focus on user behavior rather than implementation details.

**Hook Testing**:
Custom hooks are tested with proper mocking of API calls using MSW (Mock Service Worker) for realistic testing scenarios. Tests cover loading states, error conditions, and success scenarios.

### Development Experience

#### Developer Tools

**TypeScript Integration**:
Full TypeScript support across all components and hooks with strict type checking. Provides excellent developer experience with autocomplete and compile-time error detection.

**Component Library**:
Barrel exports (`index.ts`) provide clean import patterns and improved developer experience. Consistent prop interfaces and documentation improve development velocity.