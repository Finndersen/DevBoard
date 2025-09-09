# DevBoard - Architecture Documentation

## Overview
The DevBoard codebase is an AI-powered developer command center, designed to streamline development workflows by providing a unified platform for managing projects, codebases, configurations, and tasks. It aims to enhance developer productivity through intelligent automation and context-aware assistance.

Its main purpose is to act as a central hub for developers, offering tools for code analysis, documentation generation, task management, and integration with various development services like Jira, GitHub, and Slack.

The target audience includes software developers, team leads, and project managers who seek to improve efficiency, maintain code quality, and gain better insights into their development processes.

## Architecture Overview
DevBoard follows a client-server architecture, consisting of a Python-based backend API and a React-based frontend web application.

-   **Frontend**: A single-page application (SPA) built with React, providing the user interface for interacting with the DevBoard functionalities. It communicates with the backend API via RESTful calls.
-   **Backend**: A FastAPI application that exposes a REST API. It handles business logic, interacts with the database, and integrates with external services (GitHub, Jira, Slack, etc.) through various context providers and integration services.
-   **Database**: A relational database (managed by SQLAlchemy and Alembic) for persistent storage of project data, codebase information, configurations, and other application-specific data.

Key components interact as follows: The frontend sends requests to the backend API. The backend processes these requests, potentially interacting with the database or external services, and returns responses to the frontend. Data flows from the frontend to the backend for creation/updates, and from the backend to the frontend for display and interaction.

## Project Structure
The project is organized into two main top-level directories: `backend` and `frontend`, along with configuration files for development and deployment.

-   `/backend`: Contains all server-side code, API definitions, database models, business logic, and integrations.
    -   `devboard/api`: Defines the FastAPI application, API routers, and Pydantic schemas for request/response validation.
    -   `devboard/config`: Manages application configurations, including agent, LLM, and integration settings.
    -   `devboard/context_providers`: Modules responsible for fetching context from various sources (e.g., GitHub, Jira, Slack, web pages).
    -   `devboard/core`: Core utilities and registry patterns.
    -   `devboard/db`: Database connection, SQLAlchemy models, Alembic migrations, and repository implementations.
    -   `devboard/integrations`: Modules for interacting with external services (e.g., Filesystem, GitHub, Jira, Slack).
    -   `devboard/services`: Contains the main business logic and orchestrates operations (e.g., `codebase_investigation.py`, `config_service.py`, `task_planning_agent.py`).
    -   `devboard/templates`: Markdown templates for document generation (e.g., `architecture_document.md`).
    -   `devboard/utils`: Utility functions (e.g., `gemini_cli.py`, `hash.py`).
    -   `tests`: Unit and integration tests for the backend.
    -   `alembic.ini`: Configuration for Alembic database migrations.
    -   `Dockerfile`: Dockerfile for building the backend service.
    -   `pyproject.toml`: Python project configuration, dependencies, and development tools.
    -   `uv.lock`: Dependency lock file.
-   `/frontend`: Contains all client-side code for the web application.
    -   `src/components`: Reusable React UI components.
    -   `src/lib`: Frontend utility functions, including `api.ts` for backend API interaction.
    -   `src/views`: Page-level React components that compose other components to form application views.
    -   `src/assets`: Static assets like images.
    -   `public`: Publicly accessible static files.
    -   `package.json`: Node.js project configuration, dependencies, and scripts.
    -   `tsconfig.json`: TypeScript configuration.
    -   `vite.config.ts`: Vite build tool configuration.
    -   `tailwind.config.js`, `postcss.config.js`: Tailwind CSS configuration.
    -   `vitest.config.ts`: Vitest testing framework configuration.
-   `.git/`: Git version control metadata.
-   `.idea/`: IntelliJ/PyCharm IDE configuration files.
-   `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `node_modules/`, `dist/`: Generated files, virtual environments, and dependency installations.
-   `docker-compose.yml`: Docker Compose configuration for running the application services.
-   `ARCHITECTURE.md`, `CLAUDE.md`, `IMPLEMENTATION_PLAN.md`, `ORIGINAL_DOCUMENT.md`, `PROJECT_SPECIFICATION.md`: Project documentation files.

## Technology Stack

### Programming Languages Used
-   **Backend**: Python (3.12+)
-   **Frontend**: TypeScript, JavaScript

### Frameworks and Libraries
-   **Backend**:
    -   **Web Framework**: FastAPI
    -   **ORM**: SQLAlchemy
    -   **Database Migrations**: Alembic
    -   **Data Validation/Serialization**: Pydantic, Pydantic-settings
    -   **HTTP Client**: httpx
    -   **Web Scraping**: beautifulsoup4
    -   **Logging/Tracing**: logfire
    -   **Environment Variables**: python-dotenv
    -   **Integrations**: jira, PyGithub, slack-sdk
-   **Frontend**:
    -   **UI Library**: React
    -   **Build Tool**: Vite
    -   **Routing**: react-router-dom
    -   **Styling**: Tailwind CSS, PostCSS, Autoprefixer
    -   **Icons**: @heroicons/react
    -   **Markdown Rendering**: react-markdown
    -   **HTTP Client**: axios

### External Dependencies and Their Purposes
-   **Jira**: Integration for managing Jira issues.
-   **PyGithub**: Integration for interacting with GitHub repositories.
-   **slack-sdk**: Integration for interacting with Slack workspaces.
-   **uvicorn**: ASGI server for running FastAPI.
-   **pydantic-ai**: Likely for AI-related Pydantic models or utilities.

### Build Tools and Development Environment
-   **Backend**:
    -   **Dependency Management**: uv (implied by `uv.lock`)
    -   **Linter**: ruff
    -   **Type Checker**: pyright
    -   **Testing**: pytest, pytest-asyncio
    -   **Task Runner**: Makefile
-   **Frontend**:
    -   **Build Tool**: Vite
    -   **TypeScript Compiler**: tsc
    -   **Linter**: eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh
    -   **Testing**: vitest, @vitest/ui, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event
    -   **Mocking**: msw (Mock Service Worker)
    -   **DOM Environment for Tests**: jsdom
-   **Containerization**: Docker, docker-compose

## Key Components

### Backend
-   **API Routers (`devboard/api/routers`)**: Define the RESTful API endpoints for different domains (projects, codebases, configurations, tasks, QA, settings). They handle request parsing, validation, and delegate to services for business logic.
-   **Database Repositories (`devboard/db/repositories`)**: Provide an abstraction layer for database operations, encapsulating CRUD logic for various models (e.g., `ProjectRepository`, `CodebaseRepository`).
-   **Services (`devboard/services`)**: Implement the core business logic of the application. Examples include `CodebaseInvestigationService` (for analyzing codebases and generating documentation), `ConfigService` (for managing configurations), and `TaskPlanningAgent` (for AI-driven task planning).
-   **Context Providers (`devboard/context_providers`)**: Modules that abstract the retrieval of context from different sources (e.g., `GitHubContextProvider`, `JiraContextProvider`, `SlackContextProvider`, `WebpageContextProvider`). They normalize data from external systems.
-   **Integrations (`devboard/integrations`)**: Handle the direct communication and interaction with external APIs (e.g., GitHub, Jira, Slack).

### Frontend
-   **Components (`frontend/src/components`)**: Reusable UI elements such as buttons, forms, navigation elements, and display widgets.
-   **Views (`frontend/src/views`)**: Top-level components that represent distinct pages or sections of the application (e.g., `ProjectDashboard`, `Codebases`, `Settings`). They orchestrate data fetching and component rendering for a specific view.
-   **API Client (`frontend/src/lib/api.ts`)**: A module responsible for making HTTP requests to the backend API, abstracting the details of API calls from the UI components.

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

### Other Routers
-   `/api/tasks`: For managing tasks (specific endpoints not detailed here).
-   `/api/settings`: For managing application settings (specific endpoints not detailed here).
-   `/api/qa`: For Quality Assurance related functionalities (specific endpoints not detailed here).

### General Endpoints
-   `GET /`: Health check endpoint, returns `{"message": "DevBoard API is running"}`.
-   `GET /health`: Detailed health check, returns `{"status": "healthy", "version": "0.1.0", "database": "connected"}`.

**Authentication and Authorization**: Not explicitly defined in the provided router code snippets, but typically handled by FastAPI dependencies or middleware.
**Rate Limiting and Error Handling**: FastAPI's default error handling is used, with custom `HTTPException` for specific error scenarios (e.g., 404 Not Found, 400 Bad Request, 409 Conflict for architecture document updates). Rate limiting is not explicitly implemented in the provided code.

## Data Models

### Database Schemas (SQLAlchemy)
The backend uses SQLAlchemy for ORM, with models defined in `devboard/db/models`. These models represent the entities stored in the relational database. Examples include:
-   **Project**: Represents a development project.
-   **Codebase**: Represents a code repository or local codebase.
-   **Configuration**: Stores application configurations.
-   **Task**: Represents a development task.
-   **Resource**: Represents an external resource linked to a project or task.

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

-   **Code Organization**: The backend follows a modular structure, separating concerns into `api`, `db`, `services`, `context_providers`, and `integrations` directories. The frontend organizes components into `components` and `views`.
-   **API Design**: RESTful API principles are applied, with clear resource-based URLs and standard HTTP methods.
-   **Dependency Injection**: FastAPI's dependency injection system is used extensively, particularly for database sessions (`Depends(get_db)`) and service instances.
-   **Pydantic for Data Validation**: Pydantic models are used for strict data validation and serialization for all API inputs and outputs, ensuring data integrity.
-   **SQLAlchemy ORM**: The backend uses SQLAlchemy for object-relational mapping, abstracting database interactions and promoting a Pythonic way of working with data.
-   **Type Hinting**: Python type hints are used throughout the backend for improved code readability, maintainability, and static analysis. TypeScript is used in the frontend for similar benefits.
-   **Error Handling**: Custom `HTTPException` instances are raised in API endpoints to return appropriate HTTP status codes and error messages to the client.
-   **Frontend Component Structure**: React components are organized into reusable `components` and page-specific `views`, promoting modularity and reusability.

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