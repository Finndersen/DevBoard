# DevBoard - Implementation Plan

This document outlines the detailed, step-by-step tasks required to build the DevBoard application, based on the project specification. Each item is a trackable task.

## Phase 1: Minimum Viable Product (MVP)

### Epic 1: Core Backend & Database Setup

* [ ] **Task 1.1: Initialize FastAPI Project**
  * Set up a standard FastAPI project structure with directories for `routers`, `models`, `services`, `core` (for config), etc.
  * Initialize a `pyproject.toml` file for dependency management with `uv`.
* [ ] **Task 1.2: Set up Ruff for Linting and Formatting, and Pyright for type checking**
  * Add `ruff` and `pyright` as a development dependency in `pyproject.toml`.
  * Configure `lint` and `format` script commands in `pyproject.toml`.
  * Create a pre-commit hook to run `ruff` and `pyright` on staged files before each commit.
* [ ] **Task 1.3: Configure Docker Environment & Persistence**
  * Create a `Dockerfile` for the Python backend.
  * Create a `docker-compose.yml` that defines the backend service and configures a volume mount for data persistence.
* [ ] **Task 1.4: Set Up Database with SQLAlchemy & Atlas**
  * Install SQLAlchemy and Alembic.
  * Configure SQLAlchemy to use a local SQLite database file located in the persistent data directory.
  * Initialize Alembic (alembic init) to create the migrations environment.

### Epic 2: Database Models & Core API

* [ ] **Task 2.1: Implement Core SQLAlchemy Models**
  * Implement the models required for the MVP: `Project`, `Task`, `Codebase`, `ContextProviderLink`, `Configuration`.
* [ ] **Task 2.2: Create Initial Database Migration**
  * Use Alembic (alembic revision --autogenerate) to generate and apply the initial migration script for the core models.
* [ ] **Task 2.3: Implement Core API Endpoints**
  * Create `GET`, `POST`, and `PATCH` endpoints for `Project`, `Task`, and `Codebase` entities.
* [ ] **Task 2.4: Implement Configuration API Endpoints**
  * Create `GET` and `POST` endpoints for `ContextProviderLink` and `agent_config.json`.
  * Create the `GET /api/llm-providers/available` endpoint.

### Epic 3: Context & LLM Provider Framework

* [ ] **Task 3.1: Implement Pydantic-Settings Framework**
  * Create the Pydantic `BaseSettings` models for initial Context Providers (Jira, Slack, GitHub) and LLM Providers (e.g., Anthropic).
* [ ] **Task 3.2: Build Core Context Provider Interface**
  * Define the abstract base class for all context providers.
* [ ] **Task 3.3: Implement Initial Context Providers**
  * Implement Phase 1 functionality for Jira (fetch ticket), Slack (search), and Local Document providers.

### Epic 4: Single-Shot Agent Workflows

* [ ] **Task 4.1: Implement Context Assembly Service**
  * Build the service that runs before an agent is called to prepare the prompt context.
* [ ] **Task 4.2: Implement Single-Shot Project Q&A Agent**
  * Create a synchronous API endpoint (`POST /api/projects/{project_id}/chat`) that takes a query, runs the agent, and returns a single response.
* [ ] **Task 4.3: Implement Single-Shot Task Planning Workflow**
  * Create a synchronous API endpoint (`POST /api/tasks/{task_id}/plan`) that runs the Planning Agent and returns the complete `Implementation Plan` in the response.

### Epic 5: Basic Frontend UI

* [ ] **Task 5.1: Set Up React Frontend**
  * Use Vite to initialize a new React project and set up basic routing.
* [ ] **Task 5.2: Implement Project Dashboard & Kanban Board**
  * Build the main project view for creating and viewing projects and tasks.
* [ ] **Task 5.3: Build Task Detail View**
  * Create the view for a single task, allowing users to see and edit details.
* [ ] **Task 5.4: Implement Markdown Component**
  * Integrate a component for rendering and editing Markdown for project/task descriptions and the implementation plan.
* [ ] **Task 5.5: Implement Basic Agent Interaction UI**
  * Create a simple UI with a "Run" button to trigger the single-shot agents and a display area for the results.
* [ ] **Task 5.6: Implement Settings View**
  * Create the forms for managing context provider and agent model configurations.

## Phase 2: Agent Interactivity & Automation

* [ ] **Task 6.1: Implement Background Task Runner (Huey)**
* [ ] **Task 6.2: Implement WebSocket Manager for Real-Time Updates**
* [ ] **Task 6.3: Implement Agent Conversation History**
  * Add the `ProjectConversationMessage` model and create the migration.
  * Update the Project Q&A agent to be conversational, using the "Sliding Window" logic.
* [ ] **Task 6.4: Implement Conversational Task Planning**
  * Update the Task Planning workflow to be an interactive, conversational background task.
* [ ] **Task 6.5: Implement Task Implementation Agent**
* [ ] **Task 6.6: Implement PR Creation Workflow**
* [ ] **Task 6.7: Enhance UI for Real-Time Interaction**
  * Implement the `Logs` and `Agent Chat` tabs in the Task Detail View.