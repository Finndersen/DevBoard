# DevBoard - Implementation Plan

This document outlines the detailed, step-by-step tasks required to build the DevBoard application, based on the project specification. Each item is a trackable task.

## Phase 1: Minimum Viable Product (MVP)

### Epic 1: Project Setup & Backend Foundation

* [ ] **Task 1.1: Initialize FastAPI Project**
  * Set up a standard FastAPI project structure with directories for `routers`, `models`, `services`, `core` (for config), etc.
  * Initialize a `pyproject.toml` file for dependency management with `uv`.
* [ ] **Task 1.2: Set up Ruff for Linting and Formatting**
  * Add `ruff` as a development dependency in `pyproject.toml`.
  * Configure `ruff` within `pyproject.toml` to handle both linting and formatting, establishing a consistent code style.
* [ ] **Task 1.3: Configure Docker Environment**
  * Create a `Dockerfile` for the Python backend that installs dependencies and runs the Uvicorn server.
  * Create a `docker-compose.yml` to manage the FastAPI service, making it easy to run the entire backend with a single command.
* [ ] **Task 1.4: Set Up Database with SQLAlchemy & Atlas**
  * Install SQLAlchemy and Atlas CLI.
  * Configure SQLAlchemy to use a local SQLite database file.
  * Set up the Atlas project configuration to load the schema from the SQLAlchemy models, following a versioned migration workflow.
* [ ] **Task 1.5: Implement Background Task Runner with Huey**
  * Integrate Huey as the background task runner.
  * Configure Huey to use the same SQLite database file as the main application for its broker, ensuring a zero-dependency setup.
* [ ] **Task 1.6: Implement WebSocket Manager**
  * Create a FastAPI router for WebSocket connections (e.g., `/ws/jobs/{job_id}`).
  * Implement a connection manager to handle multiple clients listening for job updates.

### Epic 2: Database Models & Core API

* [ ] **Task 2.1: Implement SQLAlchemy Models**
  * Translate the full schema from the specification into Python code using modern, type-annotated SQLAlchemy syntax.
  * This includes `Project`, `Task`, `Codebase`, `ContextProviderLink`, `Configuration`, and the `project_codebase_association` table.
* [ ] **Task 2.2: Create Initial Database Migration**
  * Use Atlas to generate the initial versioned migration script based on the implemented models.
  * Review and apply the migration to create the initial database schema.
* [ ] **Task 2.3: Implement Project API Endpoints**
  * Create `GET /api/projects`, `POST /api/projects`, `GET /api/projects/{id}`, and `PATCH /api/projects/{id}`.
  * Develop Pydantic models for request and response validation.
* [ ] **Task 2.4: Implement Task API Endpoints**
  * Create `GET /api/projects/{id}/tasks`, `POST /api/tasks`, `GET /api/tasks/{id}`, and `PATCH /api/tasks/{id}`.
* [ ] **Task 2.5: Implement Codebase API Endpoints**
  * Create endpoints for `GET`, `POST`, and `DELETE` on codebases, including linking/unlinking them from projects.
* [ ] **Task 2.6: Implement Configuration API Endpoints**
  * Create `GET /api/configurations`, `GET /api/configurations/{provider_type}`, and `POST /api/configurations/{provider_type}`.

### Epic 3: Context Provider & Configuration Framework

* [ ] **Task 3.1: Implement Pydantic-Settings Framework**
  * Create the Pydantic `BaseSettings` models for Jira, Slack, and GitHub, defining environment variables and user-configurable fields.
* [ ] **Task 3.2: Build Core Context Provider Interface**
  * Define the abstract base class in Python for all context providers, enforcing the implementation of `get_resource`, `get_relevant_context`, etc.
* [ ] **Task 3.3: Implement Jira Context Provider (Phase 1)**
  * Use the Jira Python library to implement the `get_resource` method.
  * Focus on fetching a ticket's title and description from a URL to auto-populate a new DevBoard task.
* [ ] **Task 3.4: Implement Slack Context Provider (Phase 1)**
  * Use the Slack SDK to implement `get_relevant_context`.
  * This initial version will use the `search.messages` API call to find relevant information in a channel.
* [ ] **Task 3.5: Implement Local Document Provider (Phase 1)**
  * Implement a simple provider that can read the text content from local PDF or Markdown files specified by a file path.

### Epic 4: Agent Orchestration & Core Workflows

* [ ] **Task 4.1: Implement Task Planning Workflow**
  * Create the `POST /api/tasks/{task_id}/plan` endpoint.
  * This endpoint will dispatch a job to the background runner.
  * The job will execute the `Task Investigation & Planning Agent`, stream progress via WebSockets, and save the resulting Markdown plan to the `Task` model upon completion.
* [ ] **Task 4.2: Implement Task Implementation Workflow**
  * Create the `POST /api/tasks/{task_id}/implement` endpoint.
  * This will dispatch a job that runs the `Task Implementation Agent` with the approved plan as context.
  * The job will stream raw logs from the agent (e.g., Claude Code SDK output) to the WebSocket channel.
* [ ] **Task 4.3: Implement Project Q&A Agent**
  * Create a new API endpoint (e.g., `POST /api/projects/{project_id}/chat`).
  * This will be a synchronous endpoint that runs the `Project Q&A Agent` and returns its response directly.
* [ ] **Task 4.4: Implement PR Creation Workflow**
  * Create the `POST /api/tasks/{task_id}/create-pr` endpoint.
  * This dispatches a background job that uses the GitHub API (via a context provider) to create a pull request.

### Epic 5: Frontend UI - Project & Task Management

* [ ] **Task 5.1: Set Up React Frontend**
  * Use Create React App or Vite to initialize a new React project.
  * Set up basic routing (e.g., React Router) for different views like the project dashboard and task detail.
* [ ] **Task 5.2: Implement Project Dashboard View**
  * Build the main project view, which fetches and displays project data from the API.
  * Implement the header and the main navigation tabs ("Board", "Details", "Settings").
* [ ] **Task 5.3: Build Kanban Board Component**
  * Use a library like `react-beautiful-dnd` to create the draggable Kanban board.
  * Ensure that dropping a card in a new column triggers a `PATCH` request to the API to update the task's status.
* [ ] **Task 5.4: Build Task Detail View**
  * Create the modal or full-screen view for a single task.
  * This view will fetch detailed task data, including the `implementation_plan`.
* [ ] **Task 5.5: Implement Markdown Editor Component**
  * Integrate a library like `react-markdown` for rendering and an editor like `react-simplemde-editor` for editing Markdown content.
* [ ] **Task 5.6: Implement Agent Interaction Components**
  * Build the `Logs` tab component, which should establish a WebSocket connection based on a job ID and display incoming messages.
  * Build the `Agent Chat` tab for conversational interactions.
* [ ] **Task 5.7: Implement Settings View**
  * Create the forms needed for the user to input and save their context provider configurations.

## Phase 2: Enhancements & Advanced Features

* [ ] **Task 6.1: Implement Unified MCP Server**
* [ ] **Task 6.2: Enhance Context Providers** (e.g., local indexing)
* [ ] **Task 6.3: Implement Conversational Project Updates**
* [ ] **Task 6.4: Implement Detailed Agent Visualization**
* [ ] **Task 6.5: Implement Post-Task Review Agent**
* [ ] **Task 6.6: Create DevBoard CLI**