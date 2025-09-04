# DevBoard - Implementation Plan

This document outlines the detailed, step-by-step tasks required to build the DevBoard application, based on the project specification. The MVP focuses on validating the multi-source context gathering architecture with a Project Q&A agent and four context providers (GitHub, Jira, Slack, Codebase). Each item is a trackable task.

## Phase 1: Minimum Viable Product (MVP)

### Epic 1: Core Backend & Database Setup ✅

* [x] **Task 1.1: Initialize FastAPI Project**
  * Set up a standard FastAPI project structure with directories for `routers`, `models`, `services`, `core` (for config), etc.
  * Initialize a `pyproject.toml` file for dependency management with `uv`.
* [x] **Task 1.2: Set up Ruff for Linting and Formatting, and Pyright for type checking**
  * Add `ruff` and `pyright` as a development dependency in `pyproject.toml`.
  * Configure development commands in Makefile.
  * Create a pre-commit hook to run `ruff` and `pyright` on staged files before each commit.
* [x] **Task 1.3: Configure Docker Environment & Persistence**
  * Create a `Dockerfile` for the Python backend.
  * Create a `docker-compose.yml` that defines the backend service and configures a volume mount for data persistence.
* [x] **Task 1.4: Set Up Database with SQLAlchemy & Alembic**
  * Install SQLAlchemy and Alembic.
  * Configure SQLAlchemy to use a local SQLite database file located in the persistent data directory.
  * Initialize Alembic and configure in `pyproject.toml`.

### Epic 2: Database Models & Core API ✅

**Major Architectural Change - M2M Resource Sharing**: Refactored `ContextProviderResource` from polymorphic parent relationships to Many-to-Many relationships with Projects and Tasks. This enables:
- **Resource Sharing**: Same GitHub repo/Jira ticket can be linked to multiple projects/tasks
- **Data Consistency**: Single source of truth for resource metadata and descriptions 
- **Cascade Deletion**: Resources automatically deleted when no longer linked to any entity
- **Find-or-Create Pattern**: Duplicate resources are merged automatically based on URI

* [x] **Task 2.1: Implement Core SQLAlchemy Models**
  * Implement the models required for the MVP: `Project`, `Task`, `Codebase`, `ContextProviderResource`, `Configuration`.
  * **UPDATED**: Refactored `ContextProviderResource` to use Many-to-Many relationships with Projects and Tasks, enabling resource sharing and deduplication.
* [x] **Task 2.2: Create Initial Database Migration**
  * Use Alembic (alembic revision --autogenerate) to generate the initial migration script for the core models.
* [x] **Task 2.3: Implement Core API Endpoints**
  * Create `GET`, `POST`, `PATCH`, `DELETE` endpoints for `Project`, `Task`, and `Codebase` entities with Pydantic schemas.
* [x] **Task 2.4: Implement Configuration API Endpoints**
  * Create `GET`, `POST`, `PATCH`, `DELETE` endpoints for the generic Configuration table.
  * Create endpoints for managing Context Provider Resources with M2M linking to Projects and Tasks.
  * **UPDATED**: Implemented find-or-create pattern for resource sharing and cascade deletion when resources become orphaned.
  * FastAPI application setup with CORS and router integration.

### Epic 3: Configuration Framework & Integration Layer ✅

**Major Architectural Improvement - Domain-Colocated Registries**: Refactored registry architecture to use domain colocation with centralized services:
- **Registry Location**: Moved registries to their domain directories (`config/registry.py`, `integrations/registry.py`, `context_providers/registry.py`)
- **Service Centralization**: Moved `ConfigService` to `services/config_service.py` for consistent service layer architecture
- **Self-Building Pattern**: All registries now use class attributes as single source of truth, eliminating manual registration
- **DRY Compliance**: Removed string duplication by using `config_key`, `provider_type`, and `integration_type` class attributes

* [x] **Task 3.1: Implement Generic Configuration Framework**
  * Create the generic Configuration table and configuration service with Pydantic validation.
  * Create hierarchical key patterns and schema registry for type-safe configuration loading.
* [x] **Task 3.2: Build Integration Base Classes**
  * Define the abstract base class for all integrations with common authentication and error handling patterns.
* [x] **Task 3.3: Implement Core Integrations**
  * **GitHub Integration**: API client for PRs, commits, issues, branches
  * **Jira Integration**: API client for tickets, projects, comments
  * **Slack Integration**: API client for messages, channels, conversations
  * **Codebase Integration**: File system operations and one-shot agent execution wrapper
* [x] **Task 3.4: Implement Integration Registry and Factory Pattern**
  * Build `IntegrationRegistry` (domain-colocated in `integrations/registry.py`) for mapping integration type names to integration classes
  * Add factory method pattern with `create()` classmethod for configuration-based instantiation
  * Implement standardized error handling with `IntegrationConfigurationError` and other custom exceptions
  * **UPDATED**: Refactored to use self-building registry pattern with `integration_type` class attributes as single source of truth
* [x] **Task 3.5: Add Integration Connection Testing**
  * Implement `test_connection()` method for all integration classes
  * Create `IntegrationService` for handling connection testing logic with detailed error reporting
  * Add integration testing API endpoint with proper HTTP status codes and structured error responses

### Epic 4: Context Provider Layer ✅

* [x] **Task 4.1: Build Context Provider Base Classes with Registry**
  * Define abstract base class with EAGER/ON_DEMAND strategy interface and high-level query tools.
  * Implement `ContextProviderRegistry` for managing provider classes (not instances).
  * Add `ContextProviderUnavailable` exception hierarchy for configuration error handling.
  * Define factory method pattern with `create_instance()` class method for each provider.
* [x] **Task 4.2: Implement Context Providers with Sub-Agents**
  * **GitHub Context Provider**: PR context, commit summaries (uses GitHub Integration)
  * **Jira Context Provider**: Ticket context, project status (uses Jira Integration)  
  * **Slack Context Provider**: Internal sub-agent for query processing (uses Slack Integration)
  * **Codebase Context Provider**: Agential code exploration using one-shot Claude Code/Gemini CLI execution (uses Codebase Integration)
  * **WebPage Context Provider**: HTTP/HTTPS resource fetching and content analysis
  * Each provider implements `get_relevant_context(resource_uri, query)` interface and resource description generation
  * All providers implement factory method pattern with configuration validation and error handling

### Epic 5: Context Assembly & Q&A Agent ✅

* [x] **Task 5.1: Implement Context Assembly Service with Error Handling**
  * Build the service that determines EAGER vs ON_DEMAND strategies for each resource URI.
  * Implement runtime provider instantiation with factory methods and error collection.
  * Add `ProjectContextData` structure to separate successful context from provider errors.
  * Implement parallel execution of provider queries and context compilation.
* [x] **Task 5.2: Implement Project Q&A Agent**
  * Create PydanticAI-based agent with custom prompting and universal `get_relevant_context(resource_uri, query)` tool.
  * Agent receives list of available ON_DEMAND resources with descriptions in initial context.
  * Build synchronous API endpoint (`POST /api/projects/{project_id}/chat`) for agent interaction.
* [ ] **Task 5.3: Validate Multi-Source Context Assembly**
  * Test scenarios involving all four context providers to ensure the architecture works end-to-end.

### Epic 6: Basic Frontend UI

* [ ] **Task 6.1: Set Up React Frontend**
  * Use Vite to initialize a new React project and set up basic routing.
* [ ] **Task 6.2: Implement Project Dashboard**
  * Build the main project view for creating projects and linking context provider resources.
* [ ] **Task 6.3: Implement Agent Chat Interface**
  * Create Project Q&A chat interface with context assembly and real-time responses.
* [ ] **Task 6.4: Build Configuration Management UI**
  * Create forms for managing Integration and Context Provider configurations.
  * Build UI for linking projects to context provider resources with user-provided descriptions.
  * Include auto-description generation option when user provides just a URI.
* [ ] **Task 6.5: Implement Basic Task Management**
  * Simple task CRUD operations with Jira integration for task linking.

### Epic 7: Global Settings & Configuration View

* [ ] **Task 7.1: Extend Configuration Framework for LLM Providers**
  * Add OpenAI integration configuration schema with API key and organization ID support.
  * Add Anthropic integration configuration schema with API key support.
  * Add Google integration configuration schema with API key support.
  * Update configuration initialization to register new LLM provider schemas.
* [ ] **Task 7.2: Implement Agent Configuration Schemas**
  * Create QAAgentConfig, PlanningAgentConfig, and ImplementationAgentConfig with model selection.
  * Implement model hierarchy logic and fallback system for agent configuration.
  * Add agent configuration registration to the configuration framework.
* [x] **Task 7.3: Build Settings API Endpoints**
  * Extend existing `/api/configurations` endpoints to support prefix filtering for settings management.
  * Implement `/api/settings/integrations/{integration_type}/test` for on-demand connection testing with immediate results and detailed error information.
  * Add `/api/settings/agents/available-models` endpoint to get dynamic model lists based on working LLM providers.
* [ ] **Task 7.4: Implement Global Settings Frontend**
  * Create main settings view with tabbed interface (Integrations, Codebases, Context Providers, Agents).
  * Build integration configuration cards with connection status indicators and test buttons.
  * Implement codebase path management interface with validation.
  * Create context provider resource management interface.
  * Add agent model selection dropdowns with dynamic model lists.
* [ ] **Task 7.5: Add Connection Testing & Validation**
  * Implement on-demand connection testing for all integration types with immediate response handling.
  * Add form validation with detailed error messaging for configuration fields.
  * Create integration-specific connection status indicators that update after testing.
  * Implement API key masking and reveal functionality in configuration forms.

## Phase 2: Advanced Agent Features

* [ ] **Task 8.1: Implement Agent Conversation History**
  * Add the `ProjectConversationMessage` model and implement sliding window conversation management.
* [ ] **Task 8.2: Implement Task Planning Agent**
  * Build conversational Planning Agent with context assembly and Implementation Plan generation.
* [ ] **Task 8.3: Implement Task Implementation Agent**
  * Build Implementation Agent using Claude Code SDK with codebase access and GitHub PR creation.
* [ ] **Task 8.4: Add Background Task Runner**
  * Implement Huey/Dramatiq for long-running agent sessions with WebSocket progress updates.
* [ ] **Task 8.5: Enhanced UI Features**
  * Task Detail View with Planning/Implementation phases and agent conversation history.