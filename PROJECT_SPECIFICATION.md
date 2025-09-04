# Project Specification: “DevBoard” (Version 10)

## Overview

DevBoard is a "developer command centre" application designed to be a comprehensive project management system and an AI-powered developer assistant. It runs locally on a user's machine, integrating with essential developer tools like Jira, Slack, Notion, and GitHub. By ingesting project context from these sources, DevBoard provides AI agents with the necessary information to assist in the planning, development, and delivery of tasks. Users can query for project status, manage tasks, and delegate implementation work to AI agents, all from a unified interface.

## Architecture & Tech Stack 🏛️

The system will be built on a local client-server architecture, ensuring access to local file systems for code repository management.

* **Project Structure**: A monorepo structure with clearly separated `backend` and `frontend` applications is recommended. Each application will use a standard `src` layout for clean separation of source code from configuration and test files.
    ```
    /
    ├── backend/
    │   ├── devboard/           # Main Python package
    │   │   ├── api/
    │   │   │   └── routers/    # API endpoints
    │   │   ├── db/
    │   │   │   ├── models/     # SQLAlchemy models
    │   │   │   └── repositories/ # Data access layer
    │   │   ├── services/       # Business logic, agent orchestration
    │   │   ├── config/         # Configuration schemas and base classes
    │   │   │   ├── registry.py # ConfigRegistry (domain-colocated)
    │   │   │   └── base.py     # BaseConfig, ConfigValidationResult
    │   │   ├── integrations/   # External API clients
    │   │   │   └── registry.py # IntegrationRegistry (domain-colocated)
    │   │   ├── context_providers/ # Intelligent context gathering
    │   │   │   └── registry.py # ContextProviderRegistry (domain-colocated)
    │   │   └── schemas/        # Pydantic response/request models
    │   ├── tests/
    │   └── pyproject.toml
    │
    ├── frontend/
    │   ├── src/
    │   │   ├── components/ # Reusable UI components
    │   │   ├── views/      # Main pages/screens (e.g., ProjectDashboard, TaskDetail)
    │   │   ├── services/   # API client, state management
    │   │   └── assets/
    │   └── package.json
    │
    └── docker-compose.yml
    ```

* **Deployment**: A container-based approach (e.g., Docker) is recommended, with local code repositories mounted as volumes to provide necessary file system access.
* **Backend**:
  * **Framework**: An asynchronous Python web server using FastAPI.
  * **Database**: SQLAlchemy as the ORM with a local SQLite database for initial phases, offering a clear migration path to PostgreSQL for future multi-user support. Use Alembic for DB schema management and migrations.
  * **Real-time Communication**: WebSockets will be used for streaming agent progress and other real-time updates to the frontend.
  * Use `uv` for dependency management,  `ruff` for linting and formatting and `pyright` for type checking
* **Frontend**: A modern, web-based UI built with a framework like React.
* **Long-Running Tasks**:
  * **Challenge**: AI agent sessions are long-running and cannot be handled within a single synchronous API request.
  * **Proposed Solution**: A background task queue is required. A lightweight option like Dramatiq or Huey will be used for initial phases. The flow will be: API triggers a background job -> job streams updates via WebSockets -> UI displays real-time progress.
* **File Synchronization Strategy**:
  * **Challenge**: Documents managed in the UI (e.g., `ARCHITECTURE.md`, `CLAUDE.md`) may also be edited directly on the filesystem, leading to conflicts.
  * **Proposed Solution**: Implement a diff-reconciliation mechanism. Before saving changes from the UI to a file, the application will check the file's last modified timestamp. If the file has changed on disk since it was last read by the app, a three-way merge (using a library like `diff-match-patch`) will be attempted to reconcile the changes automatically. If conflicts cannot be resolved, the user will be prompted to choose which version to keep or to resolve the conflicts manually.
* **Multi-User Collaboration (Phase 3 Goal)**:
  * While the initial focus is a local-first single-user experience, the architecture should not preclude future collaboration. This would likely involve a shared backend and database where project and task data can be synced between users.

## Logical Objects & Entities 🧱

### 1. Project
A high-level representation of a large piece of work, analogous to a Jira Epic.
* **Project Details**: A central Markdown document containing the project overview, technical details, and status.
* **Context Providers**: Associated with various context sources like Slack channels, Notion pages, etc.I dont 

### 2. Task
A self-contained piece of work, often linked to a remote ticket in Jira or Asana.
* **Attributes**:
  * **Status**: A state machine tracking progress: `Pending` -> `Planning` -> `Awaiting Approval` -> `Implementing` -> `In Review` -> `Complete`.
  * **Description**: Detailed text description.
  * **Links**: References to the parent Project, remote task ID, and relevant GitHub repositories/PRs.
  * **AI State**: A `conversation_id` to resume agent sessions and a structured `Implementation Plan` artifact.

### 3. Integration
A low-level API client interface for external services that provides raw access to service APIs.
* **Purpose**: Handles authentication, API calls, rate limiting, and error handling for external services.
* **Examples**: SlackIntegration, JiraIntegration, GitHubIntegration, CodebaseIntegration.
* **Authentication**: Credentials (API keys, tokens) loaded from environment variables for security.
* **Configuration Pattern**: Each integration has a corresponding `*IntegrationConfig` class that extends `BaseConfig`
* **Factory Pattern**: Each integration implements a `create()` classmethod that handles configuration loading and validation from environment variables
* **Connection Testing**: All integrations implement `test_connection()` method for real-time validation of API credentials and connectivity
* **Registry System**: `IntegrationRegistry` (located in `devboard/integrations/registry.py`) maps integration type names to integration classes using domain-colocated architecture for better cohesion
* **API Interface**:
  * Service-specific methods like `get_slack_message()`, `search_jira_issues()`, `get_github_pr()`
  * Raw data retrieval without business logic or summarization
  * Reusable across different context providers or direct API access
  * Standardized error handling with custom exception hierarchy
* **Error Handling**: Custom exceptions for different failure scenarios:
  * `IntegrationConfigurationError`: Missing or invalid configuration (environment variables)
  * `AuthenticationError`: Invalid API credentials or expired tokens
  * `RateLimitError`: API rate limits exceeded
  * `ResourceNotFoundError`: Requested resource not found or access denied

### 4. Context Provider
A high-level interface that transforms raw integration data into relevant project/task context using domain intelligence.
* **Purpose**: Provides intelligent, summarized context for AI agents by leveraging one or more Integrations.
* **Examples**: GitHubContextProvider, JiraContextProvider, SlackContextProvider, CodebaseContextProvider, WebPageContextProvider.
* **API Interface**:
  * `can_handle_uri(resource_uri)`: Class method to determine if the provider can handle a given resource link.
  * `get_retrieval_strategy(resource_uri) -> 'EAGER' | 'ON_DEMAND'`: Determines if a resource is small enough for eager loading.
  * `get_resource(resource_uri)`: Retrieves full content for small-scope resources (EAGER).
  * `get_relevant_context(resource_uri, query)`: Universal query interface that uses internal sub-agents to process high-level queries and return focused summaries (ON_DEMAND).
  * `get_integration_tools()`: Returns lower-level Integration tools for Implementation Agent (write operations like updating Jira status, creating GitHub PRs).
  * `generate_resource_description(resource_uri)`: Auto-generates or retrieves user-provided descriptions for resources.
  * `create_instance()`: Factory method for creating configured provider instances with proper error handling.
* **Registry & Initialization Pattern**:
  * **Registry Design**: `ContextProviderRegistry` (located in `devboard/context_providers/registry.py`) stores provider classes (not instances) using domain-colocated architecture for intuitive discovery
  * **Factory Pattern**: Each provider class implements `create_instance()` factory method that handles configuration validation
  * **Error Handling**: Missing/invalid configurations raise `ContextProviderUnavailable` exceptions with detailed error messages
  * **Runtime Instantiation**: Provider instances are created at request time during context assembly, allowing graceful error collection
  * **User Feedback**: Configuration errors are collected and presented to users, enabling informed troubleshooting

### 5. ContextProviderResource
Represents a linkable external resource (GitHub repo, Jira ticket, Slack thread, etc.) that provides context for projects and tasks.
* **Shared Resources**: Uses Many-to-Many relationships allowing the same resource to be linked to multiple projects and tasks
* **Attributes**:
  * **Resource URI**: Unique identifier for the external resource (e.g., GitHub URL, Jira ticket URL)
  * **Provider Name**: The context provider that can handle this resource
  * **Description**: Single description representing the resource itself (either user-provided or auto-generated)
  * **Created Timestamp**: When the resource was first added to the system
* **Resource Sharing Benefits**:
  * **Deduplication**: Same GitHub repo/Jira ticket stored once, linked to multiple projects/tasks
  * **Data Consistency**: Single source of truth for resource metadata and descriptions
  * **Cross-Reference**: Easily see all projects/tasks using a particular resource
  * **Cascade Deletion**: Resources are automatically removed when no longer linked to any project/task
* **Junction Tables**: Simple M2M associations with timestamps tracking when resources were linked

### 6. Codebase
Represents a software codebase relevant to a project or task.
* **Architecture Document**: Each codebase can have an associated `ARCHITECTURE.md` file stored in its repository. This document is created and incrementally updated by an AI agent.

## Features & Phased Rollout 🚀

### Global Settings & Configuration
* **Phase 1**: Comprehensive global settings view for managing all application configuration:
  * **Integration Management**: Configure API credentials and connection settings for GitHub, Jira, Slack, OpenAI, Anthropic, and Google (Gemini) integrations with on-demand connection testing
  * **Codebase Management**: Add/remove local repository paths with validation
  * **Context Provider Configuration**: Manage context provider resource links with URI validation and auto-description generation
  * **Agent Configuration**: Select models for each agent type (Q&A, Planning, Implementation) with dynamic model lists based on configured LLM providers and intelligent fallback hierarchy
  * **Connection Testing**: On-demand connection verification with immediate results and actionable error messages for troubleshooting
* **Phase 2**: Advanced configuration features including configuration templates, bulk operations, and enhanced diagnostics
* **Phase 3**: A unified MCP (tool) server that provides integrations from all configured context providers to the Implementation Agent.

### Integrations & Context Providers
* **Phase 1**: 
  * **Integrations**: GitHub (PR/commits), Jira (tickets), Slack (messages), Codebase (file system), WebPage (HTTP/HTTPS)
  * **Context Providers**: GitHubContextProvider, JiraContextProvider, SlackContextProvider, CodebaseContextProvider, WebPageContextProvider
  * **Strategy**: Full EAGER/ON_DEMAND implementation with high-level query interface
  * **Configuration Management**: Type-safe configuration validation and graceful provider initialization
* **Phase 2**: Additional providers like Notion, enhanced caching, and local content indexing.

### Project
* **Phase 1**: A project view with the editable Project Details document. A project-level chat interface for the Q&A agent.
* **Phase 2**: The ability to conversationally provide project status updates, which an agent then uses to update the formal Project Details document.

### Task
* **Phase 1**:
    * Create tasks manually or by linking a Jira/Asana ID.
    * Trigger the investigation/planning phase to generate an Implementation Plan.
    * Manually or conversationally edit and approve the plan.
    * Trigger the Implementation Agent.
    * Basic visualization of agent progress (e.g., streaming logs).
    * Trigger an agent to create a GitHub PR after implementation.
* **Phase 2**:
    * Detailed visualization of implementation agent activity (sub-tasks, tool use).
    * Continue conversation with the implementation agent during the PR lifecycle to respond to feedback.
    * Trigger the Post-Task Review Agent upon task completion.

### CLI
* **Phase 2**: A CLI command for starting an interactive agent session for a specific task, automatically loading its context and conversation history.

### Multi-User Collaboration
* **Phase 3**: A mechanism to sync Project and Task data between multiple users collaborating on the same project.

## AI Agents & Orchestration 🤖

### 1. Project Q&A Agent
* **Function**: Answers questions about a project's status and context.
* **Context**:
  * Project overview document.
  * Full list of tasks and their statuses.
  * List of available ON_DEMAND resources with URIs and descriptions
* **Tools/Capabilities**:
  * Conversational interaction.
  * **Single Query Tool**: `get_relevant_context(resource_uri, query)` - works with any resource type
  * **Resource Discovery**: Agent can see available resources and their descriptions to decide which to query
  * **Read-Only**: Cannot perform write operations like updating tickets or creating PRs
  * Reading more details & state of individual tasks
  * Updating project details/summary and status
* **Model**: Fast & cheap model with a large context window (e.g., Gemini Flash).
* **Implementation**:
  * Can run in app within API request using framework like PydanticAI

### 2. Context Provider Investigation Agent (Sub-Agent)
* **Function**: Acts as a sub-agent to implement the `get_relevant_context()` API for a context provider.
* **Context**:
  * A resource URI (e.g., Slack channel link, Notion page).
  * A specific user query.
* **Tools/Capabilities**:
  * Context-provider specific tools for exploring resources, e.g.:
    * Search a Slack channel.
    * Explore and query Notion documents.
    * Summarize large documents (e.g., PDF).
    * Explores a website/webpage following links
* **Model**: Fast & cheap model with a large context window (e.g., Gemini Flash).
* **Implementation**:
  * Can initially run in app within API request using framework like PydanticAI, may need to offlload to background task

### 3. Codebase Investigation Agent
* **Function**: Generates and maintains the `ARCHITECTURE.md` file for a codebase.
* **Context**:
  * The full codebase (explored agentially via tools)
* **Tools/Capabilities**:
  * Can be triggered to create the `ARCHITECTURE.md` document if it doesn't exist.
  * Can perform incremental updates to the document to reflect changes in the code.
* **Model**: Powerful reasoning model (e.g., Gemini Pro).
* **Implementation**:
  * Possibly wrapping a single-shot Gemini CLI agent run in a background task.

### 4. Task Investigation & Planning Agent
* **Function**: Produces detailed implementation plan with enough granularity to facilitate implementation without further research/investigation
* **Context**:
  * The task description.
  * Access to all configured context providers.
* **Tools/Capabilities**:
  * Queries context providers for relevant information.
  * Asks clarifying questions to the user.
  * Generates a detailed, structured Implementation Plan.
  * Allows the user to conversationally review, update, and approve the plan.
  * Runs as a background task.
* **Model**: Intelligent model with a large context window (e.g., Gemini Pro).
* **Implementation**:
  * Can  run in app as background task/job using framework like Pydantic AI

### 5. Task Implementation Agent
* **Function**: Executes the approved Implementation Plan.
* **Context**:
  * Task description and approved Implementation Plan.
  * List of available ON_DEMAND resources with URIs and descriptions.
* **Tools/Capabilities**:
  * **Read Tools**: Universal `get_relevant_context(resource_uri, query)` for querying any context provider resource.
  * **Write Tools**: Lower-level Integration tools for mutations like `update_jira_task()`, `create_github_pr()`, `commit_code_changes()`.
  * Advanced file system manipulation (read, write, list files).
  * Executes shell commands (e.g., run tests, install dependencies).
  * Can update the Implementation Plan using search-and-replace edits.
* **Model**: Agent with strong agential/tool-use capabilities (e.g., Claude via Claude Code SDK).
* **Implementation**:
  * Claude Code SDK running in a background task, resuming from previous conversation state if applicable.
  * Provided with unified MCP server combining read tools (Context Providers) and write tools (Integrations).

### 6. Post-Task Review Agent
* **Function**: After a task is complete, this agent reviews the outcome to reconcile learnings and update project documentation.
* **Context**:
  * The completed task and its associated artifacts (e.g., PR, code changes).
* **Tools/Capabilities**:
  * Updates the main `Project Details` document.
  * Triggers the `Codebase Investigation Agent` to update the `ARCHITECTURE.md` file.
* **Model**: Reasoning model (e.g., Gemini Pro).
* **Implementation**:
  * Can run in app within API request using framework like PydanticAI or as a background task if it needs to do more extensive work.

## Project Agent Conversation Management

* **Challenge**: The Project Q&A agent's conversation history must feel continuous but cannot grow indefinitely, as this would exhaust the LLM's context window. The history must also account for tool calls made by the agent.
* **Proposed Solution**: A hybrid strategy of an automatic sliding window for message history, combined with a manual reset option and structured storage for tool calls. The primary "memory" of the project will always be the persisted `Project Details` document, not the conversation history.
* **Implementation**:
    * **Automatic Sliding Window**: The system will automatically persist only the last **N** messages (e.g., 40) for any given project conversation. When a new message is added, the oldest message is deleted from the database. This keeps the immediate conversational context relevant.
    * **Manual Reset**: The UI will provide a "Reset Conversation" button, allowing the user to clear the history for a project and start fresh.
    * **Tool Call Tracking**: The conversation history will explicitly store tool calls and their results as distinct message types. This provides the agent with a clear, structured history of its actions and their outcomes, which is crucial for effective reasoning.

## Task Planning Agent Context Management

* **Challenge**: When an agent is triggered for a task, it needs to be provided with the right context. Some linked resources are small and should be provided upfront, while others are too large and should be made available for the agent to search on-demand.
* **Proposed Solution**: Implement a **Context Assembly Process** that runs before the agent is called. This process intelligently decides how to handle each resource, preparing a perfectly tailored prompt for the agent with robust error handling.
* **Implementation**:
    1.  **Gather Resource URIs**: The backend orchestrator collects all resource links associated with the task from the database and by parsing the task description.
    2.  **Provider Instantiation & Error Collection**: For each URI, the orchestrator attempts to create a provider instance using the factory method pattern. If providers cannot be instantiated due to missing configuration, detailed error information is collected.
    3.  **Determine Retrieval Strategy**: For successfully instantiated providers, the orchestrator queries the `get_retrieval_strategy(uri)` method.
    4.  **Provider-Side Logic**: The logic for differentiating between "small" and "large" resources resides within each provider. For example:
        * A `SlackContextProvider` identifies a link with a message timestamp as `EAGER` and a channel link as `ON_DEMAND`.
        * A `NotionContextProvider` might check page metadata (like word count) to decide between `EAGER` and `ON_DEMAND`.
    5.  **Assemble Final Prompt with Error Reporting**: The orchestrator builds the agent's prompt based on the strategies:
        * For every resource marked `EAGER`, it calls `provider.get_resource(uri)` and includes the full content directly in the prompt's context section.
        * For every resource marked `ON_DEMAND`, it provides the resource URI, type, and description in the agent's initial context, along with the universal `get_relevant_context(resource_uri, query)` tool for querying any resource.
        * **Error Transparency**: Provider initialization errors are included in the response, enabling users to understand which resources could not be processed and why (e.g., "GitHub integration not configured").

### Planner/Implementer Handoff Strategy
* **Challenge**: The Planning and Implementation agents have different specializations and require different tools and frameworks, but the user experience should feel continuous.
* **Proposed Solution**: The "Baton Pass" model. The two agents are treated as separate, specialized services with a clean and formal handoff.
* **Implementation**:
    1.  **Planning Phase**: The user's conversation is exclusively with the `Task Investigation & Planning Agent`. The goal of this phase is to produce the `Implementation Plan`.
    2.  **Formal Handoff**: When the user clicks "Approve Plan", the task's status changes. The conversation history with the Planning Agent is archived.
    3.  **Implementation Phase**: A *new* conversation is initiated with the `Task Implementation Agent`. The approved `Implementation Plan` serves as the complete context and contract for this new agent.
    4.  **Seamless UI**: From the user's perspective, this all occurs within the same Task Detail View. The "brain" connected to the chat window simply switches from the Planner to the Implementer based on the task's status, ensuring the right specialist is always on the job.

### Agent Document Editing Strategy
* Use surgical find-replace style edit tool for making changes to documents (like the Project Details or an Implementation Plan)
* Treat key artifacts as "living documents" within the agent's context, that are mutated in-place instead of having contents returned from edit tool and ending up with multiple versions of th document in context


## User Workflow & UI/UX 🗺️

This section outlines the "happy path" for a user completing a task from start to finish.

1.  **Project Setup**:
    * The user opens DevBoard and creates a new Project (e.g., "Q3 Feature Launch").
    * They are taken to the Project dashboard and prompted to fill out the `Project Details` in a Markdown editor.
    * In a "Settings" tab, the user adds their first `Codebase` by providing a local path to a Git repository.
    * They connect their tools by adding credentials for Jira and Slack. They then link the project to a specific Jira board and the `#q3-features` Slack channel.

2.  **Task Creation**:
    * From the Project dashboard, the user clicks "Add Task" and pastes in a Jira ticket URL.
    * DevBoard's Jira `ContextProvider` automatically fetches the ticket's title and description, populating the new task. The task appears in the "Pending" column of the project's Kanban board.

3.  **Planning Phase**:
    * The user clicks on the new task, opening the "Task Detail View".
    * They click the "**Generate Plan**" button. The UI shows a status indicator and a real-time log stream of agent activity in the chat window:
        * `[Planner] Reading task description...`
        * `[Planner] Querying Jira for linked tickets...`
        * `[Planner] Searching Slack channel #q3-features for "API authentication"...`
        * `[Planner] Generating implementation steps...`
    * The task status changes to `Planning`.

4.  **Approval Phase**:
    * Once complete, the generated `Implementation Plan` appears in the Markdown editor within the Task Detail View.
    * The user reviews the plan. They can either edit it directly or use a chat interface to ask the Planning Agent for revisions.
    * Once satisfied, the user clicks "**Approve Plan**". The task status moves to `Awaiting Approval`.

5.  **Implementation Phase**:
    * The user clicks "**Start Implementation**". The `Task Implementation Agent` is triggered.
    * The UI now shows a live log of the agent's actions (e.g., `editing file: src/auth.py`, `running tests...`) in the agent chat window.
    * The task status moves to `Implementing`.

6.  **Completion & Review**:
    * The agent finishes and reports success. A "**Create Pull Request**" button appears.
    * Clicking it triggers an agent workflow to create the PR on GitHub.
    * The task status moves to `In Review`. The user can then follow their standard code review process outside of DevBoard.

## UI/UX Component Design 🎨

This section breaks down the primary views of the application into their core components, providing a blueprint for frontend development.

### 1. Project Dashboard View
This is the main landing page for a specific project. It provides a high-level overview and serves as the primary navigation hub.
* **Header Component**:
  * Displays the Project Name.
  * Contains a primary action button like "+ New Task".
  * Navigation tabs: "Board", "Details", "Settings".
* **Task List / Kanban Board Component (Default View)**:
  * **Columns**: Displays columns corresponding to the task statuses (`Pending`, `Planning`, `Implementing`, etc.).
  * **Task Cards**: Each task is represented by a card within a column. Cards are draggable between columns to manually update status.
  * **Card Details**: Each card shows the task title, a snippet of the description, and any relevant icons (e.g., Jira logo if linked).
  * **Filtering**: Controls to filter tasks by name, associated codebase, etc.
* **Project Details Component ("Details" Tab)**:
  * A full-screen Markdown editor for viewing and editing the `Project Details` document.
  * A chat interface on the side for interacting with the `Project Q&A Agent`.
* **Settings Component ("Settings" Tab)**:
  * UI for managing linked codebases.
  * UI for managing linked `ContextProvider` resources (e.g., list of connected Slack channels, Notion pages).

### 2. Global Settings View
This is a comprehensive configuration management interface accessible from the main navigation. It provides centralized control over all application settings.
* **Header Component**:
  * Displays "Global Settings" title.
  * Navigation tabs: "Integrations", "Codebases", "Context Providers", "Agents".
* **Integrations Tab**:
  * **Integration Cards**: Each integration (GitHub, Jira, Slack, OpenAI, Anthropic, Google) displayed as a card with:
    * Connection status indicator (gray=untested, green=working, red=failed) updated only after testing
    * "Test Connection" button with loading states that performs immediate connection verification
    * Configuration form with masked API keys (e.g., "sk-...xyz123") and reveal option
    * Save/Cancel buttons with validation feedback
  * **On-Demand Testing**: Click "Test Connection" performs real-time connection test with immediate success/failure results and actionable error messages
* **Codebases Tab**:
  * **Path Management Interface**: Add/remove local repository paths with:
    * Path input field with file system browser integration
    * Path validation (directory exists, is git repository)
    * List of configured codebases with edit/remove options
* **Context Providers Tab**:
  * **Resource Management**: Interface for managing context provider resources:
    * Add resource form with URI input and provider auto-detection
    * Resource validation and provider compatibility checking
    * Auto-description generation toggle with manual override option
    * List of configured resources grouped by provider type
* **Agents Tab**:
  * **Model Selection Interface**: Dropdown selectors for each agent type:
    * Q&A Agent, Planning Agent, Implementation Agent
    * Dynamic model lists populated based on configured and working LLM providers
    * Fallback hierarchy display showing automatic model selection order
    * Status indicators showing which providers are available for each model

### 3. Task Detail View
This is a focused, full-screen view that opens when a user clicks on a Task Card. It's the primary workspace for all agent interactions.
* **Header Component**:
  * Displays the full Task Title.
  * Includes a Status Dropdown to manually change the task's status.
  * "Back to Project" navigation link.
* **Metadata Component**:
  * A clean, readable section displaying key-value information:
    * **Linked Ticket**: A clickable link to the remote Jira/Asana ticket.
    * **Codebase**: The associated codebase for the task.
    * **Created Date**: Timestamp of when the task was created.
* **Main Content Component (Tabbed Interface)**:
  * **"Plan" Tab**: Contains the rich Markdown editor for the `Implementation Plan`.
  * **"Agent Conversation" Tab**: A single, unified, chronological view for all agent interactions.
    * **User Messages**: Standard chat bubbles.
    * **Agent Responses**: Standard chat bubbles for final, user-facing answers.
    * **Agent "Thinking" Blocks**: For the agent's internal monologue (thoughts, tool calls, tool results), these will be displayed in a distinct, collapsible block. By default, it's collapsed to a summary (e.g., "Agent is thinking... [View 3 Steps]"). When expanded, the user can see the detailed, step-by-step execution log.
* **Action Bar Component**:
  * A persistent footer or sidebar containing the primary action buttons for the task. The buttons are dynamic and change based on the current task status.
    * **Status `Pending`**: Shows "**Generate Plan**".
    * **Status `Awaiting Approval`**: Shows "**Edit Plan**" and "**Approve Plan**".
    * **Status `Implementing`**: Shows "**View Conversation**" and "**Stop Agent**".
    * **Status `Complete`**: Shows "**Create Pull Request**".

## API Endpoints 🔌

This section defines the core RESTful API contract between the frontend and the backend.

* **Projects**
  * `GET /api/projects` - List all projects.
  * `POST /api/projects` - Create a new project.
  * `GET /api/projects/{project_id}` - Get details for a single project.
  * `PATCH /api/projects/{project_id}` - Update a project's details.

* **Tasks**
  * `GET /api/projects/{project_id}/tasks` - List all tasks for a project.
  * `POST /api/tasks` - Create a new task.
  * `GET /api/tasks/{task_id}` - Get details for a single task.
  * `PATCH /api/tasks/{task_id}` - Update a task's details.

* **Configurations**
  * `GET /api/configurations` - List all provider configurations.
  * `GET /api/configurations/{provider_type}` - Get the configuration for a specific provider.
  * `POST /api/configurations/{provider_type}` - Create or update a provider's configuration.

* **Settings Management**
  * `GET /api/configurations?prefix=integration` - List integration configurations using existing generic endpoint.
  * `GET /api/configurations?prefix=agent` - List agent configurations using existing generic endpoint.
  * `POST /api/settings/integrations/{integration_type}/test` - Test connection for a specific integration with immediate results and detailed error information.
  * `GET /api/settings/agents/available-models` - Get available models based on configured and working LLM providers.

* **Agent Actions**
  * `POST /api/tasks/{task_id}/plan` - Trigger the `Task Investigation & Planning Agent`. Returns a job ID.
  * `POST /api/tasks/{task_id}/implement` - Trigger the `Task Implementation Agent`. Returns a job ID.
  * `POST /api/tasks/{task_id}/create-pr` - Trigger the PR creation workflow. Returns a job ID.

* **Real-time Updates**
  * `WS /ws/jobs/{job_id}` - A WebSocket endpoint the frontend connects to after triggering an agent, to receive real-time progress updates.

## Database Schema (SQLAlchemy Models) 🗄️

This section defines the initial database models using modern, type-annotated SQLAlchemy syntax.

```python
import datetime
from typing import List, Optional

from sqlalchemy import Column, create_engine, DateTime, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# Association table for the many-to-many relationship between Projects and Codebases
project_codebase_association = Table(
    "project_codebase_association",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("codebase_id", ForeignKey("codebases.id"), primary_key=True),
)

class Project(Base):
    """Represents a high-level project, acting as a container for tasks and codebases."""
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
    current_status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    tasks: Mapped[List["Task"]] = relationship(back_populates="project")
    codebases: Mapped[List["Codebase"]] = relationship(
        secondary=project_codebase_association, back_populates="projects"
    )
    context_resources: Mapped[List["ContextProviderResource"]] = relationship(
        secondary=project_context_resource_association, back_populates="projects"
    )
    messages: Mapped[List["ProjectConversationMessage"]] = relationship(back_populates="project")

class Task(Base):
    """Represents a single, self-contained piece of work within a project."""
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'))
    codebase_id: Mapped[Optional[int]] = mapped_column(ForeignKey('codebases.id'))
    
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default='Pending')
    remote_task_id: Mapped[Optional[str]] = mapped_column(String(100))
    conversation_id: Mapped[Optional[str]] = mapped_column(String(100))
    implementation_plan: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped[Optional["Codebase"]] = relationship(back_populates="tasks")
    context_resources: Mapped[List["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )

class Codebase(Base):
    """Represents a software codebase that can be associated with projects and tasks."""
    __tablename__ = 'codebases'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    repository_url: Mapped[Optional[str]] = mapped_column(String(512))
    local_path: Mapped[Optional[str]] = mapped_column(String(512))

    projects: Mapped[List["Project"]] = relationship(
        secondary=project_codebase_association, back_populates="codebases"
    )
    tasks: Mapped[List["Task"]] = relationship(back_populates="codebase")

class Configuration(Base):
    """Generic key-value configuration store for all application settings."""
    __tablename__ = 'configurations'
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(50), default="1.0")
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ContextProviderResource(Base):
    """Represents a context provider resource that can be shared across projects and tasks."""
    __tablename__ = 'context_provider_resources'
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(255))
    resource_uri: Mapped[str] = mapped_column(String(1024), unique=True)
    description: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    projects: Mapped[List["Project"]] = relationship(
        secondary=project_context_resource_association, back_populates="context_resources"
    )
    tasks: Mapped[List["Task"]] = relationship(
        secondary=task_context_resource_association, back_populates="context_resources"
    )

# Association table for Project <-> ContextProviderResource
project_context_resource_association = Table(
    "project_context_resources",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("context_provider_resources.id"), primary_key=True),
    Column("added_at", DateTime, default=datetime.datetime.utcnow),
)

# Association table for Task <-> ContextProviderResource
task_context_resource_association = Table(
    "task_context_resources",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("context_provider_resources.id"), primary_key=True),
    Column("added_at", DateTime, default=datetime.datetime.utcnow),
)
    
class ProjectConversationMessage(Base):
    """Represents a single message or tool call in the conversation with a Project Q&A Agent."""
    __tablename__ = 'project_conversation_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'))
    
    # The role of the message sender, e.g., 'user', 'assistant', 'tool_call', 'tool_result'
    role: Mapped[str] = mapped_column(String(50))
    
    # For text content from 'user' or 'assistant'
    content: Mapped[Optional[str]] = mapped_column(Text)
    
    # For structured data from 'tool_call' or 'tool_result'
    tool_data: Mapped[Optional[dict]] = mapped_column(JSON)
    
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="messages")

```

## Key Artifact Schemas 📝

### 1. Implementation Plan Schema
This artifact is the contract between the Planning and Implementation agents. It is a structured **Markdown document** designed to be comprehensive, providing all necessary context to minimize ambiguity and the need for further research by the implementation agent.

````markdown
# Implementation Plan: Refactor Authentication Service

## 1. Goal
Refactor the authentication service to use a new JWT library for better security.

## 2. Context Summary
- The current system uses the legacy `pyjwt` library which does not support the required PS256 algorithm.
- A project-level decision was made (see Notion doc #123) to migrate to `python-jose`.
- The user model is defined in `src/models/user.py` and contains `id`, `username`, and `role`.

## 3. Files to Modify

### `src/services/auth.py`
- **Reason:** Main service file containing the token generation and validation logic.
- **Relevant Snippets:**
  ```python
  # Snippet of the existing token creation function
  def create_token(user_id: int) -> str:
    payload = {'id': user_id}
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')
  ```

### `tests/test_auth.py`
- **Reason:** Unit tests for the authentication service that will need to be updated.

## 4. Implementation Steps
1.  Add `python-jose` to the `requirements.txt` file.
2.  In `src/services/auth.py`, import `jwt` from `jose` instead of `jwt`.
3.  Update the `create_token` function to use `jose.jwt.encode` with the `PS256` algorithm.
4.  Update the corresponding token decoding function to match.
5.  Modify tests in `tests/test_auth.py` to assert the new token structure and algorithm.
6.  Ensure all existing tests pass after the changes.

## 5. Relevant Definitions

### User Model (`src/models/user.py`)
```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    role = Column(String, default='user')
````

### 2. Codebase Architecture Document (`ARCHITECTURE.md`)
This document is a living representation of the codebase, generated and updated by the `Codebase Investigation Agent`. It follows a consistent Markdown structure to ensure clarity and navigability.

```markdown
# Architecture Overview: [Codebase Name]

**Last Updated:** YYYY-MM-DD

## 1. High-Level Summary
A brief, one-paragraph description of the codebase's purpose, primary language, and framework.

## 2. Key Directories & Files
- `/src`: Main application source code.
- `/tests`: Unit and integration tests.
- `/docs`: Project documentation.
- `Dockerfile`: Container build definition.

## 3. Core Modules & Components
### 3.1. Authentication Service (`src/services/auth.py`)
- **Purpose:** Manages user authentication, token generation, and validation.
- **Key Functions:** `create_token()`, `verify_token()`
- **Dependencies:** `UserModel`, `jose.jwt`

### 3.2. User Model (`src/models/user.py`)
- **Purpose:** Defines the data structure for a user.
- **Schema:** `id`, `username`, `hashed_password`, `role`

## 4. Data Models & Database
An overview of the database schema and the primary data models used in the application.

## 5. API Endpoints (if applicable)
- `POST /login`: Authenticates a user and returns a JWT.
- `GET /users/me`: Returns the profile of the authenticated user.

## 6. Design Patterns & Conventions
A description of any major design patterns (e.g., Repository Pattern, Dependency Injection) or coding conventions used throughout the codebase.
```


## Generic Configuration Framework

A flexible, type-safe configuration system manages all application settings using a hierarchical key-value approach with schema validation.

* **Core Concepts**:
  * **Configuration Registry**: Code-based registry (located in `devboard/config/registry.py`) mapping configuration keys to Pydantic models for validation using domain-colocated architecture
  * **Configuration Service**: Business logic service (located in `devboard/services/config_service.py`) for configuration validation and management, following centralized service layer pattern
  * **Hierarchical Keys**: Organized namespace like `integration.slack.main`, `context_provider.codebase.local`, `agent.qa.model_settings`
  * **Multi-Source Loading**: Combines environment variables (sensitive data) with database storage (user settings)
  * **Type Safety**: All configurations validated against registered Pydantic schemas

* **Self-Building Registry Pattern**:
  * Configuration schemas are automatically registered using class attributes as single source of truth
  * Registry builds itself from `config_key` class attributes, eliminating manual registration
  * Context providers check configuration validity before initialization
  * Integration instances are only created when valid configurations exist
  * Graceful degradation with logging for missing/invalid configurations

* **Configuration Registry Pattern**:
  ```python
  from abc import ABC, abstractmethod
  from typing import Dict, Type, TypeVar
  from pydantic import BaseModel
  
  T = TypeVar('T', bound=BaseModel)
  
  class ConfigRegistry:
      """Registry of configuration schemas using self-building pattern"""
      
      # Import configuration classes to avoid circular imports
      from devboard.config.agent_config import QAAgentConfig, PlanningAgentConfig
      from devboard.integrations.slack import SlackIntegrationConfig
      # ... other imports
      
      # Self-building registry using class attributes as single source of truth
      _schemas = {
          schema.config_key: schema
          for schema in [
              QAAgentConfig,
              PlanningAgentConfig, 
              SlackIntegrationConfig,
              # ... other config classes
          ]
      }
      
      @classmethod
      def get_schema(cls, key: str) -> Type[BaseConfig] | None:
          """Get the registered schema for a configuration key."""
          return cls._schemas.get(key)
  ```

* **Example Configuration Schemas**:
  ```python
  # Integration Layer - API credentials and connection details
  class SlackIntegrationConfig(BaseSettings):
      api_token: str  # From SLACK_API_TOKEN env var
      workspace_url: Optional[str] = None  # From database
      model_config = SettingsConfigDict(env_prefix='SLACK_')

  # Context Provider Layer - Behavior and defaults  
  class SlackContextProviderConfig(BaseModel):
      integration_key: str = "integration.slack.main"
      lookback_days: int = 7
      max_messages_per_query: int = 50
      agent_model: str = "gemini-flash"
      
  # Agent Configuration
  class QAAgentConfig(BaseModel):
      model_name: str = "gemini-flash"
      max_context_tokens: int = 100000
      temperature: float = 0.1
      
  # Register schemas with repository
  ConfigRepository.register_schema("integration.slack.main", SlackIntegrationConfig)
  ConfigRepository.register_schema("context_provider.slack.discussions", SlackContextProviderConfig) 
  ConfigRepository.register_schema("agent.qa.default", QAAgentConfig)
  ```

* **Configuration Service Interface**:
  ```python
  from typing import Optional, List, Dict
  from pydantic import ValidationError
  
  class ConfigValidationResult:
      def __init__(self, success: bool, config: Optional[BaseModel] = None, errors: Optional[List[str]] = None):
          self.success = success
          self.config = config
          self.errors = errors or []
  
  class ConfigService:
      def get_config(self, key: str) -> Optional[BaseModel]:
          """Simple getter - returns config if valid, None if not"""
          result = self.validate_config(key)
          return result.config if result.success else None
      
      def validate_config(self, key: str) -> ConfigValidationResult:
          """Returns detailed validation result with error information"""
          schema = ConfigRepository.get_schema(key)
          if not schema:
              return ConfigValidationResult(False, errors=[f"No schema registered for key: {key}"])
          
          try:
              # Load DB data (empty dict if no entry exists)
              db_data = self._load_from_db(key) or {}
              
              # Attempt to instantiate with DB + env vars
              config = schema.model_validate(db_data)
              return ConfigValidationResult(True, config=config)
              
          except ValidationError as e:
              # Parse errors to provide helpful feedback
              errors = []
              for error in e.errors():
                  field = error['loc'][0] if error['loc'] else 'unknown'
                  if 'missing' in error['type']:
                      errors.append(f"Missing required field '{field}' - check environment variables or database configuration")
                  else:
                      errors.append(f"Invalid value for '{field}': {error['msg']}")
              
              return ConfigValidationResult(False, errors=errors)
      
      def set_config(self, key: str, data: BaseModel) -> None: ...
      def list_configs(self, prefix: str = None) -> List[str]: ...
      def delete_config(self, key: str) -> None: ...
      def get_provider_status(self, provider_type: str) -> Dict[str, ConfigValidationResult]: ...
  ```

## Configuration Framework Usage Examples

The generic configuration framework manages all application settings through the unified key-value system:

* **Basic Usage**:
  ```python
  # Simple config retrieval
  slack_config = config_service.get_config("integration.slack.main")
  if slack_config:
      integration = SlackIntegration(slack_config)
  
  # Detailed validation for UI/diagnostics
  result = config_service.validate_config("integration.slack.main")
  if not result.success:
      for error in result.errors:
          # Show user: "Missing required field 'api_token' - check environment variables"
          display_error(error)
  ```

* **Provider Availability Check**:
  ```python
  # Check if provider is fully configured and ready to use
  provider_status = config_service.get_provider_status("slack")
  if all(result.success for result in provider_status.values()):
      # Provider is ready
      setup_slack_provider()
  else:
      # Show configuration errors to user
      show_provider_setup_errors(provider_status)
  ```

* **Configuration Hierarchy**:

* **Integration Configurations** (API credentials from environment):
  * `integration.slack.main` → SlackIntegrationConfig
  * `integration.jira.main` → JiraIntegrationConfig  
  * `integration.github.main` → GitHubIntegrationConfig
  * `integration.openai.main` → OpenAIIntegrationConfig
  * `integration.anthropic.main` → AnthropicIntegrationConfig
  * `integration.google.main` → GoogleIntegrationConfig
  * **Note**: Codebase integration requires no configuration (uses current working directory)

* **Context Provider Configurations** (behavior settings from database with hardcoded defaults):
  * `context_provider.slack.discussions` → SlackContextProviderConfig (lookback_days=7, max_messages_per_query=50)
  * `context_provider.codebase.exploration` → CodebaseContextProviderConfig (max_file_size_kb=500, exclude_patterns=[".git", "node_modules", ".venv"])
  * `context_provider.jira.tickets` → JiraContextProviderConfig (include_comments=true, max_comment_depth=3)
  * `context_provider.github.activity` → GitHubContextProviderConfig (include_pr_reviews=true, max_commits_per_pr=20)
  * `context_provider.webpage.crawling` → WebPageContextProviderConfig (max_depth=2, respect_robots_txt=true)

* **Agent Configurations** (model selection and behavior settings):
  * `agent.qa.default` → QAAgentConfig (model hierarchy: ["gpt-4o", "claude-3-5-sonnet-20241022", "gemini-1.5-pro-latest"])
  * `agent.planning.default` → PlanningAgentConfig (model hierarchy: ["gemini-1.5-pro-latest", "gpt-4o", "claude-3-5-sonnet-20241022"])
  * `agent.implementation.default` → ImplementationAgentConfig (model hierarchy: ["claude-3-5-sonnet-20241022", "gpt-4o", "gemini-1.5-pro-latest"])

* **LLM Provider Configurations** (API credentials from environment):
  * `integration.anthropic.main` → AnthropicIntegrationConfig (api_key from ANTHROPIC_API_KEY)
  * `integration.google.main` → GoogleIntegrationConfig (api_key from GOOGLE_API_KEY)
  * `integration.openai.main` → OpenAIIntegrationConfig (api_key from OPENAI_API_KEY, organization_id from OPENAI_ORG_ID)

* **Application-Level Configurations**:
  * `app.database.main` → DatabaseConfig
  * `app.websocket.main` → WebSocketConfig
  * `app.security.main` → SecurityConfig

## File Synchronization Strategy

* **Challenge**: Documents managed in the UI that are linked to local files (e.g., `ARCHITECTURE.md`, `CLAUDE.md`) may be edited by external applications (like a text editor or IDE) while they are open in DevBoard. This can lead to conflicting changes and data loss if not handled correctly.
* **Proposed Solution**: To prevent data loss and manage concurrent edits, the application will implement a **three-way merge** strategy. This is the same robust approach used by version control systems like Git.
* **State Tracking**: File content is always stored in the DB (as **Base Version**). If file sync is enabled:
    * When file content is requested by UI, first read content from file and update DB version if different
    * When file content is updated from the UI, read file and DB content and perform 3-way merge and update both File and DB content with result.
    * If there is a merge conflict, report error to user and they can attempt to resolve manually

## Architecture Design Principles

### Domain-Colocated Registries with Centralized Services

The codebase follows a hybrid architectural approach that balances domain cohesion with service layer clarity:

* **Domain-Colocated Registries**: 
  * **Rationale**: Registries are collections of domain objects without business logic, making them natural candidates for domain colocation
  * **Implementation**: `ContextProviderRegistry`, `ConfigRegistry`, and `IntegrationRegistry` are located within their respective domain directories
  * **Benefits**: High cohesion, intuitive discovery, natural ownership by domain experts
  * **Pattern**: Self-building registries using class attributes as single source of truth

* **Centralized Service Layer**:
  * **Rationale**: Services contain cross-domain business logic and orchestration, requiring centralized location for clarity
  * **Implementation**: All services (including `ConfigService`) located in `devboard/services/`
  * **Benefits**: Clear architectural layer separation, easier testing and mocking, natural for cross-domain logic
  * **Pattern**: Dependency injection with clear service boundaries

### Single Source of Truth Pattern

* **Registry Architecture**: All registries use class attributes (`config_key`, `provider_type`, `integration_type`) as the authoritative source, eliminating string duplication
* **Self-Building Pattern**: Registries build themselves from class metadata, removing the need for manual registration
* **DRY Compliance**: No duplicate configuration keys or type names across the codebase

## Implementation Design Decisions & Architecture Details

### SQLAlchemy 2.0 Migration Pattern
The codebase uses modern SQLAlchemy 2.0 syntax throughout:
* **Query Style**: `select()` statements instead of legacy `query()` method
* **Result Handling**: `scalar_one_or_none()`, `scalars().all()` for type-safe results
* **Repository Pattern**: Consistent `BaseRepository` pattern with dependency injection
* **Import Strategy**: Absolute imports (`from devboard.module`) instead of relative imports

### Context Provider Dependency Management
* **Registry Architecture**: `ContextProviderRegistry` stores provider classes (not instances) for clean separation of concerns
* **Factory Pattern**: Each provider implements `create_instance()` class method that handles configuration validation and integration setup
* **Error Collection**: Provider initialization failures are collected as structured error information rather than causing system failure
* **Runtime Instantiation**: Provider instances are created on-demand during context assembly, enabling graceful error handling
* **Exception Hierarchy**: `ContextProviderUnavailable` exceptions provide detailed error messages for missing/invalid configurations
* **User Feedback**: Context assembly returns `ProjectContextData` with separate collections for successful context and provider errors
* **Zero-Configuration Providers**: WebPageContextProvider and CodebaseContextProvider work without external configuration requirements

### Configuration Key Naming Convention
* **Integration Layer**: `integration.{provider_type}.main` (e.g., `integration.github.main`)
* **Context Provider Layer**: `context_provider.{provider_type}.default` (future use)
* **Agent Layer**: `agent.{agent_type}.default` (future use)

### Database Schema Implementation
* **Modern SQLAlchemy**: Uses `Mapped[]` annotations and `mapped_column()` syntax
* **Relationship Patterns**: Proper bidirectional relationships with `back_populates`
* **Migration Strategy**: Alembic configured in `pyproject.toml` instead of separate `.ini` file
* **Test Database**: Separate in-memory SQLite for testing with proper transaction isolation

### Error Handling & Exception Hierarchy
* **Custom Exceptions**: Service-specific exception hierarchies (e.g., `AuthenticationError`, `RateLimitError`)
* **Exception Chaining**: Proper `raise ... from e` patterns for debugging
* **Logging Strategy**: Structured logging with appropriate levels for different scenarios

## Container Configuration & Persistence

* **Strategy**: The application will be run within a container-based environment (e.g., Docker) to ensure consistency and ease of setup. To manage persistent data and provide access to local codebases, Docker volumes will be used extensively.
* **Application Data Persistence**:
    * A dedicated directory on the host machine (e.g., `~/.devboard/data`) will be mapped to a directory inside the container (e.g., `/app/data`).
    * This volume will store all persistent application state, including the SQLite database file (`devboard.db`) and all JSON configuration files (`agent_config.json`, etc.). This ensures that all user data and settings are preserved even if the container is stopped, removed, or rebuilt.
* **Codebase Access**:
    * To allow the application and its AI agents to read and write to local code repositories, users will configure paths to their local codebase directories.
    * These host paths will be mounted as volumes into a specific directory inside the container (e.g., `/code`). For example, a host directory `/Users/me/dev/my-project` could be mounted to `/code/my-project` inside the container.
* **Example `docker-compose.yml` snippet**:
    ```yaml
    services:
      backend:
        build: .
        volumes:
          # 1. Maps a host directory for the app's persistent data
          - ~/.devboard/data:/app/data
          # 2. Mounts a user's local codebase into the container
          - /path/to/user/codebase:/code/codebase
    ```