# Project Specification: “DevBoard” (Version 10)

## Overview

DevBoard is a "developer command centre" application designed to be a comprehensive project management system and an AI-powered developer assistant. It runs locally on a user's machine, integrating with essential developer tools like Jira, Slack, Notion, and GitHub. By ingesting project context from these sources, DevBoard provides AI agents with the necessary information to assist in the planning, development, and delivery of tasks. Users can query for project status, manage tasks, and delegate implementation work to AI agents, all from a unified interface.

## Architecture & Tech Stack 🏛️

The system follows a local client-server architecture with monorepo structure, ensuring access to local file systems for code repository management.

**Backend**:
- **Framework**: FastAPI with async Python
- **Database**: SQLAlchemy ORM with SQLite (PostgreSQL migration path)
- **Real-time**: WebSockets for agent progress streaming
- **Tools**: uv (dependency management), ruff (linting), pyright (type checking)
- **Observability**: Pydantic Logfire for monitoring and instrumentation

**Frontend**:
- **Framework**: React 19+ with TypeScript
- **Build**: Vite with Hot Module Replacement
- **Styling**: Tailwind CSS with responsive design
- **Routing**: React Router v7+
- **Testing**: Vitest, React Testing Library, MSW
- **State**: React hooks with API-driven data fetching

**Key Features**:
- **Long-running Tasks**: Background job queue (Dramatiq/Huey) with WebSocket progress updates
- **File Synchronization**: SHA256 content hashing for conflict detection on architecture documents
- **Container Deployment**: Docker with mounted local code repositories
- **Future Multi-user**: Architecture supports shared backend and collaboration (Phase 3)

## Logical Objects & Entities 🧱

### 1. Project
A high-level representation of a large piece of work, analogous to a Jira Epic.
* **Project Details**: A central Markdown document containing the project overview, technical details, and status.
* **Context Providers**: Associated with various context sources like Slack channels, Notion pages, etc.I dont 

### 2. Task
A self-contained piece of work, often linked to a remote ticket in Jira or Asana.
* **Attributes**:
  * **Status**: A state machine tracking progress: `Pending` -> `Designing` -> `Planning` -> `Implementing` -> `In Review` -> `Complete`.
  * **Task Specification**: Enhanced description document crafted interactively with the Task Planning Agent (stored in `description` field).
  * **Implementation Plan**: Detailed technical implementation plan created through conversational workflow.
  * **Links**: References to the parent Project, remote task ID, and relevant GitHub repositories/PRs.
  * **AI State**: Full conversation history with Task Planning Agent stored as `TaskConversationMessage` records.
* **Interactive Document Crafting**:
  * **State-Based Workflow**: Different agent capabilities based on task state (Designing vs Planning)
  * **Structured Editing**: Agent responses include find-replace edits applied atomically with user approval
  * **Research Integration**: Full access to context providers during specification and planning phases

### 3. Integration
A low-level API client interface for external services that provides raw access to service APIs.
* **Purpose**: Handles authentication, API calls, rate limiting, and error handling for external services.
* **Examples**: SlackIntegration, JiraIntegration, GitHubIntegration, CodebaseIntegration.
* **Authentication**: Credentials (API keys, tokens) loaded from environment variables for security.
* **Configuration Pattern**: Integration configuration classes are centralized in `devboard/config/integration_configs.py` to avoid circular dependencies
* **Factory Pattern**: Each integration implements a synchronous `create()` classmethod that handles configuration loading and validation from environment variables
* **Connection Testing**: All integrations implement `test_connection()` method for real-time validation of API credentials and connectivity
* **Registry System**: `integration_registry` singleton instance (located in `devboard/integrations/registry.py`) maps integration type names to integration classes using domain-colocated architecture for better cohesion and instance-based pattern for improved testability
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
  * **Registry Design**: `context_provider_registry` singleton instance (located in `devboard/context_providers/registry.py`) stores provider classes using domain-colocated architecture and instance-based pattern for improved testability
  * **Factory Pattern**: Each provider class implements synchronous `create_instance()` factory method that delegates to integration's `create()` method, eliminating code duplication
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
  * **Integration Management**: Configure API credentials and connection settings for GitHub, Jira, Slack, OpenAI, Anthropic, and Gemini integrations with on-demand connection testing
  * **Dynamic Configuration System**: Environment variables can be overridden through UI with clear indicators showing value sources (environment, database, defaults)
  * **Environment Variable Support**: Automatic loading from `.env` files in current directory, home directory, or backend directory at startup
  * **Codebase Management**: Add/remove local repository paths with validation
  * **Context Provider Configuration**: Manage context provider resource links with URI validation and auto-description generation
  * **Agent Configuration**: Select models for each agent type (Q&A, Planning, Implementation) with dynamic model lists based on configured LLM providers and intelligent fallback hierarchy
  * **Connection Testing**: On-demand connection verification with immediate results and actionable error messages for troubleshooting
  * **Type-Safe Configuration Service**: Enhanced configuration management with dual-interface design:
    * **Typed Methods**: `get_config(ConfigClass)` and `validate_config(ConfigClass)` for compile-time type safety when config type is known
    * **Dynamic Methods**: `get_config_by_key(key)` and `validate_config_by_key(key)` for runtime key-based access
    * **Generic Validation Results**: `ConfigValidationResult[T]` provides strongly-typed configuration validation with proper error handling
    * **Automatic Key Extraction**: Configuration classes define their own keys via `config_key` attribute, eliminating duplication
    * **Integration Benefits**: GitHub, Slack, and Jira integrations use typed methods for improved developer experience and compile-time error detection
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
    * **Interactive Task Planning**: State-based workflow with Task Planning Agent for conversational document crafting:
      * **Designing State**: Interactive task specification refinement with research capabilities
      * **Planning State**: Implementation plan creation with full context access
      * **State Transitions**: Manual progression through design → planning → implementation phases
    * **Document Editing**: Structured agent responses with find-replace edits applied atomically with user approval
    * **Three-Tab Interface**: Task Specification, Implementation Plan, and Planning Agent conversation views
    * Trigger the Implementation Agent after planning completion.
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

### 1. Project Q&A Agent (Enhanced with Shared Architecture)
* **Function**: Answers questions about a project's status and context through conversational interface
* **Context**:
  * Project overview document.
  * Full list of tasks and their statuses.
  * List of available ON_DEMAND resources with URIs and descriptions
  * Full conversation history with the user (stored as PydanticAI message format)
* **Tools/Capabilities**:
  * **Context Research**: `get_relevant_context(resource_uri, query)` - works with any resource type
  * **Resource Discovery**: Agent can see available resources and their descriptions to decide which to query
  * **Read-Only**: Cannot perform write operations like updating tickets or creating PRs
  * **Future Enhancement**: Could be extended with deferred document editing tools for project documentation
* **Message Storage**: Full PydanticAI message history (ModelRequest/ModelResponse) stored in JSON format with minimal schema
* **Model**: Configurable model selection via LLMService with agent type preferences (e.g., QA agent type)
* **Implementation**:
  * PydanticAI-based using shared base agent service infrastructure
  * Shared API patterns with Task Planning Agent for consistency

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

### 4. Task Planning Agent (Enhanced with Deferred Tools)
* **Function**: Interactive document crafting for task specifications and implementation plans through state-based conversational workflow with user approval for document changes
* **Context**:
  * Current task specification and implementation plan documents
  * Access to all configured context providers for research
  * Full conversation history with the user (stored as PydanticAI message format)
  * Task state awareness (Designing vs Planning phases)
* **Tools/Capabilities**:
  * **Document Editing Tools**: Deferred tools with `approval_required=True` for editing task specification and implementation plan documents
    * `edit_task_specification(edits: list[DocumentEdit], reasoning: str)`
    * `edit_implementation_plan(edits: list[DocumentEdit], reasoning: str)`
    * Pre-validation ensures edits can be applied before presenting to user
  * **Context Research**: Full access to project context, codebase information, and external resources via `get_relevant_context()` tool
  * **Interactive Approval Workflow**: Agent execution pauses for user to approve/deny document changes with optional feedback
  * **Conversational Refinement**: Agent can revise edits based on user feedback when edits are denied
  * **State-Aware Prompting**: Different capabilities based on task state (Designing: spec only, Planning: both documents)
* **Message Storage**: Full PydanticAI message history (ModelRequest/ModelResponse) stored in JSON format with minimal schema
* **Model**: Configurable model selection via LLMService with agent type preferences (e.g., PLANNING agent type)
* **Implementation**:
  * PydanticAI-based with deferred tools for document editing
  * State-based prompt templates for different workflow phases
  * Shared base agent service for common functionality
  * API endpoints for tool approval/denial workflow

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
    * From the Project dashboard, the user clicks "Add Task", and has two options for how to create a task:
      * Can paste in an existing Jira ticket URL, and Jira integration automatically fetches the ticket's title and description, populating the new task. 
      * Can manually enter task details.
    * The new task appears in the Project's task list with status `Defining`.

3. **Defining Phase**:
   * The user clicks on the new task, opening the "Task Detail View".
   * The user can chat with the Task Agent and make manual edits to interactively build and refine the task specification document.

4.  **Planning Phase**:
    * User can click the "**Generate Implementation Plan**" button. The UI shows a status indicator and a real-time log stream of agent activity in the chat window:
        * `[Planner] Reading task description...`
        * `[Planner] Querying Jira for linked tickets...`
        * `[Planner] Searching Slack channel #q3-features for "API authentication"...`
        * `[Planner] Generating implementation steps...`
    * The task status changes to `Planning`.

5.  **Approval Phase**:
    * Once complete, the generated `Implementation Plan` appears in the Markdown editor within the Task Detail View.
    * The user reviews the plan. They can either edit it directly or use a chat interface to ask the Planning Agent for revisions.

6.  **Implementation Phase**:
    * Once satisfied, the user clicks "**Start Implementation**". The `Task Implementation Agent` is triggered.
    * The UI now shows a live log of the agent's actions (e.g., `editing file: src/auth.py`, `running tests...`) in the agent chat window.
    * The task status moves to `Implementing`.

7.  **Completion & Review**:
    * The agent finishes and reports success. A "**Create Pull Request**" button appears.
    * Clicking it triggers an agent workflow to create the PR on GitHub.
    * The task status moves to `In Review`. The user can then follow their standard code review process outside of DevBoard.
    * Once the PR is merged, the user marks the task as `Complete`.


## Frontend Architecture & Implementation 🖥️

### Directory Structure & Organization

The frontend follows a clean, modular structure designed for maintainability and scalability:

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── __tests__/      # Component tests
│   │   ├── Layout.tsx      # Application shell with navigation
│   │   ├── Chat.tsx        # Real-time chat interface
│   │   ├── ConfigurationForm.tsx    # Settings form component
│   │   └── ConfigurationField.tsx   # Individual config field
│   ├── views/              # Main page components (routes)
│   │   ├── __tests__/      # View component tests
│   │   ├── ProjectDashboard.tsx     # Project listing and overview
│   │   ├── ProjectDetail.tsx        # Individual project details
│   │   ├── TaskDetail.tsx          # Task specification and planning
│   │   ├── Codebases.tsx           # Codebase management
│   │   └── Settings.tsx            # Global application settings
│   ├── lib/                # Core utilities and services
│   │   ├── __tests__/      # Service tests
│   │   └── api.ts          # API client and TypeScript interfaces
│   ├── test/               # Test configuration and utilities
│   │   ├── setup.ts        # Test environment setup
│   │   ├── utils.tsx       # Test utility functions
│   │   └── mocks/          # MSW mock handlers
│   ├── assets/             # Static assets (images, icons)
│   ├── App.tsx             # Main application component with routing
│   ├── main.tsx            # Application entry point
│   └── index.css           # Global styles and Tailwind imports
├── package.json            # Dependencies and scripts
├── tailwind.config.js      # Tailwind CSS configuration
├── tsconfig.json          # TypeScript configuration
├── vite.config.ts         # Vite build configuration
└── vitest.config.ts       # Test runner configuration
```

### State Management Architecture

The application uses a **props-down, events-up** pattern with React hooks for state management:

* **Local Component State**: Each view manages its own data using `useState` and `useEffect` hooks
* **API-Driven Data**: All persistent data is fetched from the backend API using the centralized `ApiClient`
* **Real-time Updates**: WebSocket connections provide live updates for long-running agent operations
* **Form State**: Controlled components with local state for form inputs and editing modes
* **Navigation State**: React Router handles URL state and navigation between views

**Key State Patterns:**
```typescript
// Loading states for async operations
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)

// Data fetching pattern
useEffect(() => {
  fetchData().catch(err => setError(err.message))
}, [dependency])

// Edit mode toggles for inline editing
const [isEditing, setIsEditing] = useState(false)
const [editedContent, setEditedContent] = useState(originalContent)
```

### Component Architecture & Design Patterns

**1. Component Hierarchy:**
```
App (Router Setup)
├── Layout (Navigation Shell)
│   └── Views (Route Components)
│       ├── Shared Components (Chat, Forms, etc.)
│       └── View-Specific Logic
```

**2. TypeScript Integration:**
* **Strict Type Safety**: All components use TypeScript with strict type checking
* **Interface-First Design**: API responses and component props are fully typed
* **Type-Only Imports**: Strict enforcement of `import type` syntax for type imports
* **Generic Components**: Reusable components with generic type parameters where appropriate

**3. Styling Approach:**
* **Utility-First CSS**: Tailwind CSS for consistent, responsive styling
* **Design System**: Custom color palette and spacing using Tailwind's configuration
* **Dark Mode Support**: Built-in dark mode toggle with system preference detection
* **Responsive Design**: Mobile-first approach with Tailwind's responsive utilities
* **Component Variants**: Conditional styling based on component state and props

### API Integration & Data Flow

**1. Centralized API Client:**
```typescript
class ApiClient {
  private readonly baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    // Centralized error handling and response processing
  }
  
  // Typed methods for all API endpoints
  async getProjects(): Promise<Project[]> { ... }
  async createTask(projectId: number, task: CreateTaskRequest): Promise<Task> { ... }
}
```

**2. Data Fetching Patterns:**
* **Effect-Based Loading**: `useEffect` hooks trigger API calls on component mount and dependency changes
* **Error Boundaries**: Graceful error handling with user-friendly error messages
* **Optimistic Updates**: Immediate UI updates followed by API synchronization
* **Loading States**: Skeleton screens and loading indicators for better UX

**3. Real-time Communication:**
* **WebSocket Integration**: Live updates for agent progress and system notifications
* **Event-Driven Updates**: Real-time chat messages and agent status updates
* **Connection Management**: Automatic reconnection and connection state handling

### User Interface Patterns & Behaviors

**1. Navigation & Routing:**
* **Single-Page Application**: Client-side routing with React Router
* **Persistent Navigation**: Global navigation bar with active state indicators
* **Breadcrumb Navigation**: Clear navigation hierarchy for nested views
* **Deep Linking**: All application states are URL-addressable

**2. Interactive Elements:**
* **Inline Editing**: Toggle between view and edit modes for documents and configurations
* **Modal Dialogs**: Confirmation dialogs for destructive actions
* **Form Validation**: Real-time validation with clear error messaging
* **Progressive Enhancement**: Graceful degradation for JavaScript-disabled environments

**3. Real-time Feedback:**
* **Loading Indicators**: Skeleton screens and spinners for async operations
* **Success/Error Toast**: Non-intrusive notifications for user actions
* **Live Agent Updates**: Streaming progress indicators for long-running AI operations
* **Auto-save Indicators**: Visual feedback for automatic content saving

### Testing Strategy & Quality Assurance

**1. Test Architecture:**
* **Unit Testing**: Vitest for fast, isolated component testing
* **Integration Testing**: React Testing Library for user-interaction testing
* **API Mocking**: MSW (Mock Service Worker) for realistic API mocking
* **Visual Testing**: Component testing with various props and states

**2. Testing Patterns:**
```typescript
// Component testing with user interactions
test('should update task status when status dropdown changes', async () => {
  const user = userEvent.setup()
  render(<TaskDetail />)
  
  await user.click(screen.getByRole('combobox'))
  await user.click(screen.getByText('In Progress'))
  
  expect(screen.getByText('In Progress')).toBeInTheDocument()
})

// API integration testing with MSW
test('should fetch and display projects', async () => {
  server.use(
    http.get('/api/projects', () => HttpResponse.json([mockProject]))
  )
  
  render(<ProjectDashboard />)
  await waitFor(() => expect(screen.getByText('Test Project')).toBeInTheDocument())
})
```

**3. Code Quality Standards:**
* **ESLint Configuration**: Strict linting rules for code consistency
* **TypeScript Strict Mode**: Maximum type safety with strict compiler options
* **Import Organization**: Consistent import ordering and type-only imports
* **Component Conventions**: Consistent naming patterns and file organization

### Performance & Optimization

**1. Build Optimization:**
* **Vite Build System**: Fast development builds with HMR and optimized production bundles
* **Code Splitting**: Route-based code splitting for smaller initial bundle sizes
* **Tree Shaking**: Automatic removal of unused code and dependencies
* **Asset Optimization**: Image compression and efficient asset loading

**2. Runtime Performance:**
* **React Best Practices**: Proper use of keys, memoization where needed, and efficient re-renders
* **Bundle Analysis**: Regular monitoring of bundle size and optimization opportunities
* **Lazy Loading**: Dynamic imports for route components and heavy dependencies
* **Efficient State Updates**: Minimal re-renders through proper state design

## Backend Architecture & Implementation 🏗️

### Directory Structure & Organization

```
backend/
├── devboard/                       # Main Python package
│   ├── api/                       # API layer
│   │   ├── routers/               # FastAPI route handlers
│   │   │   ├── projects.py        # Project endpoints
│   │   │   ├── tasks.py           # Task management endpoints
│   │   │   ├── codebases.py       # Codebase management
│   │   │   ├── configurations.py  # Settings endpoints
│   │   │   └── websocket.py       # WebSocket connections
│   │   └── schemas/               # Pydantic models
│   │       ├── project.py         # Project request/response schemas
│   │       ├── task.py             # Task schemas with state management
│   │       └── codebase.py        # Codebase and architecture schemas
│   ├── core/                      # Core business logic
│   │   ├── config.py              # Configuration service & registry
│   │   ├── agent_config.py        # Agent-specific configurations
│   │   └── integration_configs.py # Integration configurations
│   ├── db/                        # Database layer
│   │   ├── models/                # SQLAlchemy 2.0 models
│   │   ├── repositories/          # Data access patterns
│   │   └── session.py             # Database session management
│   ├── services/                  # Business services
│   │   ├── project_service.py     # Project management logic
│   │   ├── task_service.py        # Task orchestration
│   │   ├── llm_service.py         # LLM provider management
│   │   ├── context_assembly.py    # Context aggregation
│   │   └── codebase_investigation.py # Architecture generation
│   ├── integrations/              # External service clients
│   │   ├── __init__.py            # Integration registry
│   │   ├── github.py              # GitHub API client
│   │   ├── jira.py                # Jira integration
│   │   └── slack.py               # Slack client
│   ├── context_providers/         # Context gathering modules
│   │   ├── __init__.py            # Provider registry
│   │   ├── github.py              # GitHub context provider
│   │   ├── jira.py                # Jira context provider
│   │   ├── slack.py               # Slack context provider
│   │   ├── codebase.py            # Local codebase provider
│   │   └── webpage.py             # Web scraping provider
│   ├── templates/                 # Document templates
│   │   ├── task_specification.md  # Task spec template
│   │   ├── implementation_plan.md # Implementation template
│   │   └── architecture_document.md # Architecture template
│   └── utils/                     # Utility modules
│       ├── gemini_cli.py          # Gemini API utilities
│       └── __init__.py
├── tests/                         # Test suite
│   ├── test_*.py                  # Unit & integration tests
│   └── conftest.py                # Test fixtures
├── alembic/                       # Database migrations
│   └── versions/                  # Migration scripts
├── Makefile                       # Development commands
├── pyproject.toml                 # Project dependencies & config
└── README.md                      # Backend documentation
```

### API Layer & Endpoints 🔌

This section defines the core RESTful API contract between the frontend and the backend.

* **Projects**
  * `GET /api/projects` - List all projects.
  * `POST /api/projects` - Create a new project.
  * `GET /api/projects/{project_id}` - Get details for a single project.
  * `PATCH /api/projects/{project_id}` - Update a project's details.

* **Tasks**
  * `GET /api/tasks` - List all tasks, optionally filtered by `?project_id=` parameter.
  * `GET /api/projects/{project_id}/tasks` - List all tasks for a project (convenience endpoint).
  * `POST /api/tasks` - Create a new task (requires `project_id` in request body).
  * `GET /api/tasks/{task_id}` - Get details for a single task.
  * `PATCH /api/tasks/{task_id}` - Update a task's details.

* **Task Planning Agent**
  * `GET /api/tasks/{task_id}/messages` - Get task planning conversation history.
  * `POST /api/tasks/{task_id}/messages` - Send message to task planning agent with structured response including explicit edit arrays.
  * `POST /api/tasks/{task_id}/apply-edits` - Apply structured document edits with separate `task_specification_edits` and `task_implementation_plan_edits` fields.
  * `POST /api/tasks/{task_id}/state-transition` - Progress task through design/planning states.

* **Codebases**
  * `GET /api/codebases` - List all codebases.
  * `POST /api/codebases` - Create a new codebase.
  * `GET /api/codebases/{codebase_id}` - Get details for a single codebase.
  * `PATCH /api/codebases/{codebase_id}` - Update a codebase's details.
  * `DELETE /api/codebases/{codebase_id}` - Delete a codebase.

* **Architecture Documents**
  * `GET /api/codebases/{codebase_id}/architecture_document/` - Get complete architecture document information including content and hash for conflict detection.
  * `PUT /api/codebases/{codebase_id}/architecture_document/` - Update architecture document content with conflict detection using SHA256 content hashing.
  * `POST /api/codebases/{codebase_id}/architecture_document/generate` - Generate or update architecture document using AI.

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

### Database Schema & Data Models 🗄️

The application uses modern SQLAlchemy 2.0 models with type annotations and a SQLite database (with PostgreSQL migration path).

#### Core Entities

**Project**: High-level container for related tasks and codebases
- Contains project details (name, description, status), creation metadata
- Has many-to-many relationships with Codebases and ContextProviderResources

**Task**: Individual work items with lifecycle management
- Links to Projects, stores task specifications and implementation plans
- Manages state transitions (Designing → Planning → Ready → In Progress → Done)
- Supports document versioning and conversation history

**Codebase**: Represents local software repositories
- Stores path, metadata, and architecture document content with conflict detection
- Maintains SHA256 content hashes for synchronization with file system

#### Configuration & Context

**ContextProviderResource**: External linkable resources for project/task context
- Represents GitHub repos, Jira tickets, Slack threads, web pages
- Many-to-many relationships with Projects and Tasks for flexible resource sharing

**Configuration**: Hierarchical settings storage
- Generic key-value system supporting nested configurations
- JSON column for complex data structures with Pydantic validation

**ProjectConversationMessage**: Q&A agent conversation history
- Supports multiple message types: user, assistant, tool_call, tool_result
- Stores both text content and structured JSON data for tool interactions
- Implements sliding window pattern to manage conversation length

#### Database Design Principles

- **Modern SQLAlchemy 2.0**: Uses `Mapped[]` annotations and relationship patterns
- **Type Safety**: Full type annotation support with optional nullable fields
- **Resource Sharing**: Many-to-many relationships prevent duplication of shared resources
- **Extensibility**: JSON fields and generic configuration system support future enhancements
- **Migration Ready**: Clear upgrade path from SQLite to PostgreSQL for multi-user scenarios

## UI/UX Component Design 🎨

This section breaks down the primary views of the application into their core components, detailing the current implementation and planned features.

### Application Layout & Navigation

**Global Layout Component** (`components/Layout.tsx`):
* **Navigation Bar**: Fixed header with DevBoard branding and navigation links
  * **Logo**: Blue "DB" icon with "DevBoard" text link to dashboard
  * **Active Navigation**: Visual indicators for current route (Projects, Codebases, Settings)
  * **Responsive Design**: Horizontal layout with consistent spacing and hover effects
  * **Dark Mode Support**: Automatic theme switching with dark/light color schemes
* **Content Area**: Centered max-width container with consistent padding
* **Navigation Links**: 
  * `/projects` - Project dashboard and management
  * `/codebases` - Codebase configuration and architecture documents
  * `/settings` - Global application configuration

### 1. Project Dashboard View (`views/ProjectDashboard.tsx`)
The main landing page displaying all projects with creation and management capabilities.

**Current Implementation:**
* **Project Grid Layout**: Responsive card-based display of projects
* **Create Project Button**: Prominent action button for new project creation
* **Project Cards**: Individual project tiles with:
  * Project name and description
  * Creation date and last updated timestamp
  * Quick action buttons (View, Edit, Delete)
  * Status indicators and progress metrics
* **Loading States**: Skeleton placeholders during data fetching
* **Empty State**: Guidance for users with no projects

**Planned Enhancements:**
* **Project Filtering**: Search and filter by name, status, or date
* **Kanban Board Toggle**: Switch between card grid and kanban board views
* **Bulk Operations**: Multi-select for batch project operations

### 2. Individual Project Detail View (`views/ProjectDetail.tsx`)
Comprehensive project management interface with tabbed navigation.

**Current Implementation:**
* **Project Header**: Project name, description, and metadata display
* **Tabbed Interface**:
  * **Project Details Tab**: Markdown editor for project documentation
  * **Tasks Tab**: List of all project tasks with status indicators
  * **Settings Tab**: Project-specific configuration options
* **Task Management**: 
  * Create new tasks with title and description
  * Task status indicators and quick actions
  * Navigate to individual task detail views
* **Real-time Chat**: Integrated Q&A agent interface (`components/Chat.tsx`)

**Chat Component Features:**
* **Message History**: Persistent conversation with Q&A agent
* **Real-time Messaging**: WebSocket integration for live responses
* **Typing Indicators**: Visual feedback during agent processing
* **Message Formatting**: Markdown support for rich text responses
* **Auto-scroll**: Automatic scroll to latest messages

### 3. Task Detail View (`views/TaskDetail.tsx`)
Comprehensive task management interface with state-based workflow.

**Current Implementation:**
* **Task Header**: 
  * Back navigation to parent project
  * Task title and status dropdown for manual state changes
  * Metadata display (creation date, assigned codebase, remote task ID)
* **Three-Tab Interface**:
  * **Task Specification Tab**: Markdown editor with toggle between view/edit modes
  * **Implementation Plan Tab**: Structured plan document with inline editing
  * **Planning Agent Tab**: Conversational interface for task planning
* **Document Editing Features**:
  * **Inline Edit Mode**: Toggle between readonly and edit states
  * **Auto-save Functionality**: Automatic content persistence
  * **Markdown Rendering**: Rich text display with `react-markdown`
  * **Edit/Save Actions**: Clear visual feedback for document state

**State-Based Action Buttons**:
* **Pending State**: "Start Design" button to begin task specification
* **Designing State**: "Begin Planning" to transition to planning phase
* **Planning State**: "Start Implementation" to trigger implementation agent
* **Implementation State**: Live progress monitoring and agent controls
* **Complete State**: "Create Pull Request" workflow trigger

### 4. Codebases Management (`views/Codebases.tsx`)
Centralized interface for managing local codebases and architecture documents.

**Current Implementation:**
* **Codebase Listing**: Table/card view of all configured codebases
* **Add Codebase Form**: Path validation and repository detection
* **Codebase Actions**:
  * Edit codebase metadata (name, description)
  * View/Edit architecture documents
  * Delete codebase configuration
* **Architecture Document Management**:
  * View existing `ARCHITECTURE.md` files
  * Generate new architecture documents using AI
  * Edit and update architecture content
  * Conflict detection for concurrent file system changes

### 5. Global Settings View (`views/Settings.tsx`)
Comprehensive configuration management with tabbed organization.

**Current Implementation:**
* **Integration Configuration**:
  * **Configuration Cards**: Visual status indicators for each integration
  * **Field-Level Editing**: Individual configuration field management using `ConfigurationForm.tsx`
  * **Environment Variable Integration**: Display of value sources (env, database, defaults)
  * **Connection Testing**: Real-time validation with immediate feedback
  * **Masked Secrets**: Secure display of API keys and tokens
* **Configuration Components**:
  * **ConfigurationForm**: Dynamic form generation based on schema
  * **ConfigurationField**: Individual field component with type-specific inputs
  * **Field Types**: String, boolean, integer, number inputs with validation
  * **Value Source Indicators**: Clear labeling of configuration value origins

**Integration Management Features:**
* **Status Indicators**: Visual connection state (Connected, Disconnected, Error)
* **Test Connection**: On-demand connection verification
* **Error Messaging**: Detailed error feedback for troubleshooting
* **Field Validation**: Real-time validation with user-friendly error messages

### Component Design Patterns & Standards

**1. TypeScript Interface Design:**
```typescript
// Consistent prop interface patterns
interface ComponentProps {
  data: ApiDataType
  onAction: (id: number) => void
  loading?: boolean
  className?: string
}

// Flexible event handler patterns
type EventHandler<T = void> = (data: T) => void | Promise<void>
```

**2. Consistent State Patterns:**
```typescript
// Standard loading/error state management
const [data, setData] = useState<DataType[]>([])
const [loading, setLoading] = useState(true)
const [error, setError] = useState<string | null>(null)

// Edit mode patterns for inline editing
const [isEditing, setIsEditing] = useState(false)
const [editedContent, setEditedContent] = useState(originalContent)
const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
```

**3. Accessibility & User Experience:**
* **Keyboard Navigation**: Full keyboard accessibility for all interactive elements
* **ARIA Labels**: Proper screen reader support with descriptive labels
* **Focus Management**: Logical tab order and focus indicators
* **Loading States**: Skeleton screens prevent layout shift during loading
* **Error Boundaries**: Graceful error handling with fallback UI components

### Frontend Behavior Patterns & User Experience

**1. Data Loading & State Management:**
* **Progressive Loading**: Components render immediately with loading states, then populate with data
* **Error Recovery**: Failed API requests show retry options and clear error messages
* **Optimistic Updates**: UI updates immediately for better perceived performance, with rollback on API failure
* **Skeleton Screens**: Loading placeholders match the structure of loaded content to prevent layout shift

**2. Form Handling & Validation:**
* **Real-time Validation**: Field-level validation as users type with immediate feedback
* **Unsaved Changes Warning**: Browser prompt when navigating away from forms with unsaved data
* **Auto-save Indicators**: Visual feedback showing when content is automatically saved
* **Field State Management**: Clear indication of field sources (environment, database, default values)

**3. Navigation & User Flow:**
* **Breadcrumb Navigation**: Clear path indication for nested views (Project > Task > Details)
* **Back Button Behavior**: Browser back button works correctly with React Router state
* **Deep Linking**: All application states are URL-addressable and shareable
* **Tab Persistence**: Active tab selection persists across page refreshes and navigation

**4. Interactive Elements & Feedback:**
* **Button States**: Loading, disabled, and active states with appropriate visual feedback
* **Hover Effects**: Consistent hover states for interactive elements
* **Click Feedback**: Visual confirmation of user interactions (button presses, link clicks)
* **Drag & Drop**: Future kanban board functionality with drag-and-drop task management

**5. Real-time Features:**
* **WebSocket Connection**: Persistent connection for agent progress and chat functionality
* **Live Updates**: Agent progress streams to the UI in real-time during long-running operations
* **Connection Status**: Visual indicators for WebSocket connection state
* **Reconnection Logic**: Automatic reconnection with exponential backoff on connection loss

**6. Accessibility & Inclusive Design:**
* **Screen Reader Support**: All interactive elements have proper ARIA labels and roles
* **Keyboard Navigation**: Full application functionality available via keyboard shortcuts
* **Focus Indicators**: Clear visual focus states for keyboard users
* **Color Contrast**: WCAG compliant color combinations for text and background elements
* **Responsive Text**: Text scales appropriately across different screen sizes and zoom levels

## Key Artifact Schemas 📝

### 1. Task Specification Schema
A structured Markdown document created collaboratively between users and the Task Planning Agent during the **Designing** phase. Used to capture task requirements, context, and acceptance criteria before implementation planning begins.

**Template Structure**: `/backend/devboard/templates/task_specification.md`
- **Objective**: Clear, specific goal statement
- **Context & Background**: Current state, problem description, stakeholder needs
- **Requirements**: Functional and non-functional requirements as checklists
- **Acceptance Criteria**: Testable success criteria and quality gates
- **Resources & References**: Related documentation, dependencies, external references
- **Constraints & Assumptions**: Technical constraints and timeline assumptions

### 2. Implementation Plan Schema
The formal contract between Planning and Implementation agents. A comprehensive Markdown document providing all necessary context to execute the task without ambiguity or additional research.

**Template Structure**: `/backend/devboard/templates/implementation_plan.md`
- **Summary**: High-level approach and technical strategy
- **Technical Analysis**: Architecture impact, dependencies, risk assessment
- **Implementation Steps**: Phased approach with specific files, testing, and time estimates
- **Testing Strategy**: Unit test requirements, integration scenarios, performance validation
- **Definition of Done**: Completion criteria including code review, tests, and documentation

### 3. Architecture Document Schema
A living representation of codebases generated and maintained by the Codebase Investigation Agent. Provides comprehensive technical documentation for development teams.

**Template Structure**: `/backend/devboard/templates/architecture_document.md`
- **Overview**: Purpose, goals, target audience
- **Architecture Overview**: System architecture, component interactions, data flow
- **Project Structure**: Directory organization, key files, module organization
- **Technology Stack**: Languages, frameworks, dependencies, build tools
- **Key Components**: Major modules, responsibilities, interfaces
- **Configuration & Environment**: Environment variables, deployment considerations
- **Development Patterns**: Code organization, naming conventions, error handling


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
  Implements a self-building registry system where configuration schemas automatically register themselves using class attributes. The registry builds itself from `config_key` attributes on Pydantic models, eliminating manual registration. Context providers and integrations check the registry for valid configurations before initialization, enabling graceful degradation with proper logging for missing or invalid configurations.

* **Configuration Schema Types**:
  - **Integration Schemas**: Handle API credentials and connection details for external services (Slack, GitHub, Jira), inheriting from BaseSettings to automatically load from environment variables with appropriate prefixes
  - **Context Provider Schemas**: Define behavior parameters and defaults for data retrieval components, including lookback periods, query limits, and associated agent models
  - **Agent Configuration Schemas**: Specify LLM parameters such as model names, context token limits, temperature settings, and other inference parameters

* **Configuration Service Interface**:
  Provides a unified API for configuration management with methods for getting, setting, validating, and listing configurations. Returns detailed validation results with specific error messages for missing environment variables or invalid values. Supports hierarchical key-based access and provider status checking across all configuration types.
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

## Observability & Monitoring

### Pydantic Logfire Integration

The application uses Pydantic Logfire for comprehensive observability and performance monitoring:

* **Configuration**: Hardcoded sensible defaults with environment-based overrides:
  * Service name: `devboard`
  * Environment detection from `ENVIRONMENT` variable (defaults to `development`)
  * Console logging enabled for development environments
  * Remote telemetry enabled only when `LOGFIRE_TOKEN` environment variable is present

* **Automatic Instrumentation**:
  * **FastAPI**: Complete HTTP request/response instrumentation with status codes, timing, and error tracking
  * **SQLAlchemy**: Database query instrumentation with performance metrics and query analysis
  * **HTTPx**: External API request instrumentation for integration monitoring

* **Service-Level Instrumentation**:
  * **Context Assembly Service**: Tracks resource discovery, categorization, and eager context loading with detailed metrics
  * **QA Agent Service**: Monitors chat interactions, context assembly timing, and AI inference performance
  * **Integration Service**: Tests connection success/failure rates with error categorization
  * **Context Providers**: Performance tracking for resource retrieval and context generation

* **Error Tracking**: Structured error logging with exception context and stack traces for debugging

* **Performance Monitoring**: Request timing, database query performance, and agent response times

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

### Modern Registry Architecture

The application uses a modern, type-safe registry pattern that prioritizes testability and maintainability:

* **Generic Registry Base Class**: 
  * `Registry[T]` provides a generic, type-safe foundation for all registries
  * Requires explicit `list[T]` initialization and `key_attr` parameter for clarity
  * Immutable after construction to prevent accidental modifications
  * Simple API with `get()`, `list_keys()`, `list_values()` methods

* **Instance-Based Pattern**: 
  * All registries are singleton instances (not classes) enabling dependency injection
  * Services accept registry instances as constructor parameters for testability
  * Tests can create isolated registry instances with mock data
  * No global state manipulation required for test isolation

* **Specialized Registry Subclasses**:
  * `ContextProviderRegistry` extends `Registry[type[BaseContextProvider]]` with `get_provider_for_uri()` method
  * Domain-specific logic implemented directly in registry subclasses
  * No generic `find_by()` methods - specialized implementations for clarity

* **Domain-Colocated Singletons**:
  * `context_provider_registry` in `devboard/context_providers/registry.py`  
  * `config_schema_registry` in `devboard/config/registry.py`
  * `integration_registry` in `devboard/integrations/registry.py`
  * Each registry located with its domain for intuitive discovery and maintenance

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

### Template System
Centralized template management for consistent document structure across the application.
* **Template Types**: Enumerated template categories including task specifications, implementation plans, and architecture documents
* **Template Service**: Generic service interface with `get_template(template_type: TemplateType)` method for retrieving structured document templates
* **File-Based Storage**: Templates stored as separate Markdown files in `devboard/templates/` directory for easy maintenance
* **Backward Compatibility**: Legacy template methods maintained during transition period

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