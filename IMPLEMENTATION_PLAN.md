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

* [x] **Task 2.1: Implement Core SQLAlchemy Models**
  * Implement the models required for the MVP: `Project`, `Task`, `Codebase`, `ContextProviderLink`, `Configuration`.
* [x] **Task 2.2: Create Initial Database Migration**
  * Use Alembic (alembic revision --autogenerate) to generate the initial migration script for the core models.
* [x] **Task 2.3: Implement Core API Endpoints**
  * Create `GET`, `POST`, `PATCH`, `DELETE` endpoints for `Project`, `Task`, and `Codebase` entities with Pydantic schemas.
* [x] **Task 2.4: Implement Configuration API Endpoints**
  * Create `GET`, `POST`, `PATCH`, `DELETE` endpoints for the generic Configuration table.
  * Create endpoints for managing Context Provider Links.
  * FastAPI application setup with CORS and router integration.

### Epic 3: Configuration Framework & Integration Layer ✅

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

### Epic 4: Context Provider Layer

* [ ] **Task 4.1: Build Context Provider Base Classes**
  * Define abstract base class with EAGER/ON_DEMAND strategy interface and high-level query tools.
* [ ] **Task 4.2: Implement Context Providers with Sub-Agents**
  * **GitHub Context Provider**: PR context, commit summaries (uses GitHub Integration)
  * **Jira Context Provider**: Ticket context, project status (uses Jira Integration)  
  * **Slack Context Provider**: Internal sub-agent for query processing (uses Slack Integration)
  * **Codebase Context Provider**: Agential code exploration using one-shot Claude Code/Gemini CLI execution (uses Codebase Integration)
  * Each provider implements `get_relevant_context(resource_uri, query)` interface and resource description generation

### Epic 5: Context Assembly & Q&A Agent

* [ ] **Task 5.1: Implement Context Assembly Service**
  * Build the service that determines EAGER vs ON_DEMAND strategies for each resource URI.
  * Implement parallel execution of provider queries and context compilation.
* [ ] **Task 5.2: Implement Project Q&A Agent**
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

## Phase 2: Advanced Agent Features

* [ ] **Task 7.1: Implement Agent Conversation History**
  * Add the `ProjectConversationMessage` model and implement sliding window conversation management.
* [ ] **Task 7.2: Implement Task Planning Agent**
  * Build conversational Planning Agent with context assembly and Implementation Plan generation.
* [ ] **Task 7.3: Implement Task Implementation Agent**
  * Build Implementation Agent using Claude Code SDK with codebase access and GitHub PR creation.
* [ ] **Task 7.4: Add Background Task Runner**
  * Implement Huey/Dramatiq for long-running agent sessions with WebSocket progress updates.
* [ ] **Task 7.5: Enhanced UI Features**
  * Task Detail View with Planning/Implementation phases and agent conversation history.