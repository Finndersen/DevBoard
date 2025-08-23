# Project Specification: “DevBoard” (Version 10)

## Overview

DevBoard is a "developer command centre" application designed to be a comprehensive project management system and an AI-powered developer assistant. It runs locally on a user's machine, integrating with essential developer tools like Jira, Slack, Notion, and GitHub. By ingesting project context from these sources, DevBoard provides AI agents with the necessary information to assist in the planning, development, and delivery of tasks. Users can query for project status, manage tasks, and delegate implementation work to AI agents, all from a unified interface.

## Architecture & Tech Stack 🏛️

The system will be built on a local client-server architecture, ensuring access to local file systems for code repository management.

* **Deployment**: A container-based approach (e.g., Docker) is recommended, with local code repositories mounted as volumes to provide necessary file system access.
* **Backend**:
  * **Framework**: An asynchronous Python web server using FastAPI.
  * **Database**: SQLAlchemy as the ORM with a local SQLite database for initial phases, offering a clear migration path to PostgreSQL for future multi-user support. Use [Atlas](https://atlasgo.io/) for DB schema management and migrations.
  * **Real-time Communication**: WebSockets will be used for streaming agent progress and other real-time updates to the frontend.
  * Use `uv` for dependency management and `ruff` for linting and formatting
* **Frontend**: A modern, web-based UI built with a framework like React.
* **Long-Running Tasks**:
  * **Challenge**: AI agent sessions are long-running and cannot be handled within a single synchronous API request.
  * **Proposed Solution**: A background task queue is required. A lightweight option like Dramatiq or FastAPI's built-in `BackgroundTasks` will be used for initial phases. The flow will be: API triggers a background job -> job streams updates via WebSockets -> UI displays real-time progress.
* **File Synchronization Strategy**:
  * **Challenge**: Documents managed in the UI (e.g., `ARCHITECTURE.md`, `CLAUDE.md`) may also be edited directly on the filesystem, leading to conflicts.
  * **Proposed Solution**: Implement a diff-reconciliation mechanism. Before saving changes from the UI to a file, the application will check the file's last modified timestamp. If the file has changed on disk since it was last read by the app, a three-way merge (using a library like `diff-match-patch`) will be attempted to reconcile the changes automatically. If conflicts cannot be resolved, the user will be prompted to choose which version to keep or to resolve the conflicts manually.
* **Multi-User Collaboration (Phase 3 Goal)**:
  * While the initial focus is a local-first single-user experience, the architecture should not preclude future collaboration. This would likely involve a shared backend and database where project and task data can be synced between users.

## Logical Objects & Entities 🧱

### 1. Project
A high-level representation of a large piece of work, analogous to a Jira Epic.
* **Project Details**: A central Markdown document containing the project overview, technical details, and status.
* **Context Providers**: Associated with various context sources like Slack channels, Notion pages, etc.

### 2. Task
A self-contained piece of work, often linked to a remote ticket in Jira or Asana.
* **Attributes**:
  * **Status**: A state machine tracking progress: `Pending` -> `Planning` -> `Awaiting Approval` -> `Implementing` -> `In Review` -> `Complete`.
  * **Description**: Detailed text description.
  * **Links**: References to the parent Project, remote task ID, and relevant GitHub repositories/PRs.
  * **AI State**: A `conversation_id` to resume agent sessions and a structured `Implementation Plan` artifact.

### 3. Context Provider
An interface for providing project and task context from external data sources.
* **Authentication**: Users will provide credentials (API keys, Personal Access Tokens) via the UI or environment variables. For Slack, the approach will aim to use `xoxc` and `xoxd` tokens to avoid workspace app installation.
* **API / Interface**:
  * `can_handle_uri(resource_uri)`: Determines if the provider can handle a given resource link.
  * `get_resource(resource_uri)`: Retrieves the full content of a small-scope resource.
  * `get_relevant_context(resource_uri, query)`: Retrieves context relevant to a specific query from a larger-scope resource.
  * `get_mcp_tools()`: Returns a list of tools specific to this provider that can be passed to an agent.
  * `update_content()`: Performs a refresh of any locally cached content.

### 4. Codebase
Represents a software codebase relevant to a project or task.
* **Architecture Document**: Each codebase can have an associated `ARCHITECTURE.md` file stored in its repository. This document is created and incrementally updated by an AI agent.

## Features & Phased Rollout 🚀

### Global
* **Phase 1**: UI for managing user-level agent configurations (e.g., custom slash commands, `CLAUDE.md` prompt guidance, MCP server configuration).
* **Phase 2**: A unified MCP (tool) server that provides integrations from all configured context providers to the Implementation Agent.

### Context Providers
* **Phase 1**: Initial integrations for Slack, GitHub, Jira, Notion, and local documents (e.g., PDF). Large-scale resources will rely on the provider's native search capabilities.
* **Phase 2**: More sophisticated handling of large-scale resources, such as generating local summaries or indexes of Slack conversations for faster retrieval.

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
  * List of available large-scale context provider resources with associated descriptions
* **Tools/Capabilities**:
  * Conversational interaction.
  * `retrieve_relevant_project_context(query)`: A tool for on-demand, targeted context fetching from providers to manage context window limitations. OR, a `get_relevant_context(resource_uri, query)` tool to get context from specific large-scale resources.
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
  * Task description
  * The approved Implementation Plan.
* **Tools/Capabilities**:
  * Performs code changes.
  * Runs tests.
  * Can be interactively guided by the user to iterate on the solution.
  * Can respond to PR review comments.
* **Model**: Agent with strong agential/tool-use capabilities (e.g., Claude via Claude Code SDK).
* **Implementation**:
  * Claude Code SDK running in a background task , resuming from previous conversation state if applicable.
  * Provided with a unified MCP server combining tools from all configured context providers.

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

### Agent Document Editing Strategy
* **Challenge**: When an agent needs to update a document (like the Project Details or an Implementation Plan), simply appending the new version to the conversation history is inefficient and confusing.
* **Proposed Solution**: Treat key artifacts as "living documents" within the agent's context. Instead of passing the document as a simple string in the prompt, it can be provided as a special tool-accessible object. The agent would use a dedicated `update_document(section_id, new_content)` tool. This approach keeps the context clean, allows for targeted, in-place updates, and provides a clear audit trail of changes.


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
    * They click the "**Generate Plan**" button. The UI shows a status indicator and a real-time log stream:
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
    * The UI now shows a live log of the agent's actions (e.g., `editing file: src/auth.py`, `running tests...`).
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

### 2. Task Detail View
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
  * **"Plan" Tab**: Contains the rich Markdown editor for the `Implementation Plan`. This is the default view when a plan is ready for review.
  * **"Agent Chat" Tab**: The interactive chat window for conversing with the `Planning` or `Implementation` agents. This is where clarifying questions are asked and answered.
  * **"Logs" Tab**: A read-only, auto-scrolling view for the real-time log stream during agent execution. It displays the step-by-step progress of the running agent.
* **Action Bar Component**:
  * A persistent footer or sidebar containing the primary action buttons for the task. The buttons are dynamic and change based on the current task status.
    * **Status `Pending`**: Shows "**Generate Plan**".
    * **Status `Awaiting Approval`**: Shows "**Edit Plan**" and "**Approve Plan**".
    * **Status `Implementing`**: Shows "**View Logs**" and "**Stop Agent**".
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

* **Agent Actions**
  * `POST /api/tasks/{task_id}/plan` - Trigger the `Task Investigation & Planning Agent`. Returns a job ID.
  * `POST /api/tasks/{task_id}/implement` - Trigger the `Task Implementation Agent`. Returns a job ID.
  * `POST /api/tasks/{task_id}/create-pr` - Trigger the PR creation workflow. Returns a job ID.

* **Real-time Updates**
  * `WS /ws/jobs/{job_id}` - A WebSocket endpoint the frontend connects to after triggering an agent, to receive real-time progress updates.

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

## Database Schema (SQLAlchemy Models) 🗄️

This section defines the initial database models using modern, type-annotated SQLAlchemy syntax.

```python
import datetime
from typing import List, Optional

from sqlalchemy import Column, create_engine, ForeignKey, String, Table, Text
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

class ContextProviderLink(Base):
    """Links a Project or Task to an external resource URI, like a Slack channel or Notion page."""
    __tablename__ = 'context_provider_links'
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column()
    parent_type: Mapped[str] = mapped_column(String(50)) # 'project' or 'task'
    provider_type: Mapped[str] = mapped_column(String(50)) # e.g., 'slack', 'notion'
    resource_uri: Mapped[str] = mapped_column(String(1024))
    
    __mapper_args__ = {
        "polymorphic_on": "parent_type",
    }

class Configuration(Base):
    """Stores the JSON-serialized configuration for a single context provider type."""
    __tablename__ = 'configurations'
    
    provider_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    settings_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
```

## Context Provider Configuration

A robust and type-safe configuration system is required to manage the settings for various context providers.

* **Strategy**: The application will use the **Pydantic-Settings** library to manage configurations. This approach provides:
  * **Type Safety & Validation**: Each provider will have a dedicated Pydantic `BaseSettings` model (e.g., `SlackSettings`, `JiraSettings`) ensuring that configuration is always valid.
  * **Environment Variable Loading**: Sensitive information like API keys and tokens will be loaded directly from environment variables, adhering to security best practices.
  * **Database Persistence**: Non-sensitive, user-configurable settings will be serialized to JSON and stored in the database.
* **Implementation**:
  1. A Pydantic model is defined for each provider, specifying which fields are loaded from the environment and which are user-configurable.
  2. A `Configuration` table in the database stores the JSON representation of the user-configurable settings for each provider type.
  3. When the application needs a provider's settings, it will load the JSON from the database and instantiate the corresponding Pydantic model. Pydantic will automatically merge the database values with the values from environment variables to create a complete, validated settings object.
* **Example Pydantic Models**:
  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class SlackSettings(BaseSettings):
      # Loaded from an environment variable named SLACK_API_TOKEN
      api_token: str
      # A non-secret value stored in the DB, editable by the user
      default_channel: str = "general"
      # Tells Pydantic to look for environment variables
      model_config = SettingsConfigDict(env_prefix='SLACK_')

  class JiraSettings(BaseSettings):
      api_token: str
      server_url: str # e.g., "[https://your-company.atlassian.net](https://your-company.atlassian.net)"
      user_email: str
      model_config = SettingsConfigDict(env_prefix='JIRA_')
  ```

## File Synchronization Strategy

* **Challenge**: Documents managed in the UI that are linked to local files (e.g., `ARCHITECTURE.md`, `CLAUDE.md`) may be edited by external applications (like a text editor or IDE) while they are open in DevBoard. This can lead to conflicting changes and data loss if not handled correctly.
* **Proposed Solution**: To prevent data loss and manage concurrent edits, the application will implement a **three-way merge** strategy. This is the same robust approach used by version control systems like Git.
* **Implementation Details**:
    1.  **State Tracking**: When a file is opened for editing in the DevBoard UI, the application will store its initial state (the **Base Version**).
    2.  **Pre-Save Check**: Before saving any changes from the UI, the backend will first read the current state of the file on disk (the **Disk Version**).
    3.  **Diff & Patch**: Using a library like Google's **`diff-match-patch`**, the system will:
        * Calculate the patch representing the changes between the **Base Version** and the **UI Version**.
        * Attempt to apply this patch to the **Disk Version**.
    4.  **Conflict Resolution**:
        * If the patch applies cleanly (meaning the edits don't overlap), the merged content is written to the file, and the save is successful.
        * If the patch fails to apply, a **merge conflict** has occurred. The API will return an error, and the UI will present the user with a dialog to resolve the conflict:
            * **Overwrite Disk Changes**: Saves the UI version, discarding any external edits.
            * **Discard My Changes**: Reloads the file from disk, discarding all UI edits.
            * **Copy My Changes to Clipboard**: Allows the user to manually copy their work and resolve the conflict in an external editor.

