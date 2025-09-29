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
  * **UPDATED**: Consolidated Task API architecture - moved task creation to `/api/tasks/` while keeping project task listing at `/api/projects/{id}/tasks` for convenience. Added task list endpoint at `/api/tasks/` with optional project filtering.
* [x] **Task 2.4: Implement Configuration API Endpoints**
  * Create `GET`, `POST`, `PATCH`, `DELETE` endpoints for the generic Configuration table.
  * Create endpoints for managing Context Provider Resources with M2M linking to Projects and Tasks.
  * **UPDATED**: Implemented find-or-create pattern for resource sharing and cascade deletion when resources become orphaned.
  * FastAPI application setup with CORS and router integration.

### Epic 3: Configuration Framework & Integration Layer ✅

**Major Architectural Improvements**:

**Modern Registry Architecture**: Refactored registry system to use modern, type-safe, instance-based pattern:
- **Generic Base Class**: Created `Registry[T]` generic base class for type safety and consistency across all registries
- **Instance-Based Pattern**: Converted from class-based to instance-based registries with singleton pattern for improved testability
- **Dependency Injection**: All services now accept registry instances as constructor parameters enabling test isolation
- **Simplified API**: Removed `find_by()` methods in favor of direct implementation in specialized registry subclasses
- **Domain Colocation**: Registries located in domain directories (`config/registry.py`, `integrations/registry.py`, `context_providers/registry.py`)
- **Service Centralization**: Services remain in `services/` directory for clear architectural layer separation

**Circular Dependency Resolution**: Resolved circular dependency between integrations and configuration system:
- **Centralized Configuration**: Created `config/integration_configs.py` containing all integration configuration schemas
- **Module Import Order**: Configuration registry now imports integration configs without circular dependencies
- **Factory Pattern Optimization**: Converted integration `create()` methods from async to sync for better performance
- **Code Deduplication**: Refactored context provider `create_instance()` methods to delegate to integration `create()` methods

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
  * Build `integration_registry` singleton instance (domain-colocated in `integrations/registry.py`) for mapping integration type names to integration classes
  * Add factory method pattern with **sync** `create()` classmethod for configuration-based instantiation
  * Implement standardized error handling with `IntegrationConfigurationError` and other custom exceptions
  * **UPDATED**: Refactored to use modern instance-based `Registry[T]` pattern with explicit `key_attr` parameter and dependency injection support
  * **UPDATED**: Resolved circular dependency by centralizing integration configuration schemas in `config/integration_configs.py`
* [x] **Task 3.5: Add Integration Connection Testing**
  * Implement `test_connection()` method for all integration classes
  * Create `IntegrationService` for handling connection testing logic with detailed error reporting
  * Add integration testing API endpoint with proper HTTP status codes and structured error responses

### Epic 4: Context Provider Layer ✅

* [x] **Task 4.1: Build Context Provider Base Classes with Registry**
  * Define abstract base class with EAGER/ON_DEMAND strategy interface and high-level query tools.
  * Implement `context_provider_registry` singleton instance extending `Registry[type[BaseContextProvider]]` for managing provider classes.
  * Add `ContextProviderUnavailable` exception hierarchy for configuration error handling.
  * Define factory method pattern with **sync** `create_instance()` class method for each provider.
  * **UPDATED**: Refactored to use modern instance-based registry with specialized `get_provider_for_uri()` method and dependency injection support.
  * **UPDATED**: Eliminated code duplication by delegating to integration `create()` methods in context provider factories.
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
* [x] **Task 5.3: Registry Architecture Modernization**
  * **Generic Registry Foundation**: Implemented `Registry[T]` base class with type-safe, immutable design requiring explicit `list[T]` and `key_attr` parameters
  * **Instance-Based Pattern**: Converted all registries from class-based to instance-based singleton pattern with dependency injection support
  * **Service Dependency Injection**: Updated all services (`ContextAssemblyService`, `ConfigService`, `IntegrationService`, `ResourceService`) to accept registry instances as constructor parameters
  * **Test Infrastructure**: Removed complex registry clearing fixtures, enabling clean test isolation through registry instance injection
  * **Simplified API**: Removed generic `find_by()` methods, implementing specialized logic directly in registry subclasses for better clarity
  * **Result**: 145 tests passing with modern, testable architecture while maintaining full functionality
* [ ] **Task 5.4: Validate Multi-Source Context Assembly**
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

### Epic 7: Global Settings & Configuration View ✅

**Major Feature Complete - Dynamic Configuration System**: Implemented comprehensive configuration management system with:
- **Dynamic Schema Discovery**: Backend-driven form generation avoiding frontend hardcoded schemas
- **Value Source Tracking**: Environment variables > Database > Default precedence with visual indicators  
- **Environment Variable Override**: UI capability to override environment variables with clear warnings
- **Empty String Validation**: Proper null handling and validation for cleared fields
- **Connection Testing**: Integrated integration testing with proper configuration loading
- **Environment File Support**: Automatic `.env` file loading from current directory and home directory at startup

* [x] **Task 7.1: Extend Configuration Framework for LLM Providers**
  * Added OpenAI integration configuration schema with API key and organization ID support.
  * Added Anthropic integration configuration schema with API key support.
  * Added Gemini integration configuration schema with API key support (changed from Google).
  * Updated configuration initialization to register new LLM provider schemas.
* [x] **Task 7.2: Implement Agent Configuration Schemas**
  * Created QAAgentConfig, PlanningAgentConfig, ImplementationAgentConfig, and InvestigationAgentConfig with model selection.
  * Implemented model hierarchy logic and fallback system for agent configuration.
  * Added agent configuration registration to the configuration framework.
* [x] **Task 7.3: Build Settings API Endpoints**
  * Extended existing `/api/configurations` endpoints to support prefix filtering for settings management.
  * **UPDATED**: Added `/api/configurations/{config_key}/detail` endpoint providing field-level metadata including value sources, environment variable names, and validation info.
  * **UPDATED**: Added `/api/configurations/{config_key}/fields` PATCH endpoint for field-level updates with empty string to null conversion.
  * Implemented `/api/settings/integrations/{integration_type}/test` for on-demand connection testing with immediate results and detailed error information.
  * Added `/api/settings/agents/available-models` endpoint to get dynamic model lists based on working LLM providers.
* [x] **Task 7.4: Implement Global Settings Frontend**
  * **COMPLETED**: Created comprehensive settings view with tabbed interface (Integrations, AI Providers).
  * **COMPLETED**: Built dynamic configuration forms using `ConfigurationField` and `ConfigurationForm` components with:
    - Value source indicators (environment/database/default)
    - Environment variable override warnings and reset functionality
    - Secret field masking/revealing with eye icon toggle
    - Field validation with proper empty string handling
    - Uppercase field name display
  * **COMPLETED**: Integrated connection testing with proper state management and result clearing.
  * **COMPLETED**: Added dark mode support for all text and UI elements.
* [x] **Task 7.5: Add Connection Testing & Validation**
  * **COMPLETED**: Implemented on-demand connection testing for all integration types with immediate response handling.
  * **COMPLETED**: Added comprehensive form validation with detailed error messaging for configuration fields.
  * **COMPLETED**: Fixed integration connection testing by updating all integration `create()` methods to use `config_service` for proper database configuration loading.
  * **COMPLETED**: Implemented API key masking and reveal functionality with toggle button in configuration forms.
  * **COMPLETED**: Added proper test result state management that clears when switching between configurations.
* [x] **Task 7.6: Environment Variable Support**
  * **COMPLETED**: Added python-dotenv dependency and automatic `.env` file loading at startup from current directory and home directory.
  * **COMPLETED**: Implemented comprehensive environment variable handling in configuration service with proper precedence (environment > database > default).
  * **COMPLETED**: Added environment variable override capability through UI with clear visual indicators and reset functionality.

### Epic 8: Architecture Document Management ✅

**Major API Improvements**: Implemented comprehensive architecture document management with conflict detection and streamlined UI experience:

- **Merged API Endpoints**: Consolidated separate `/architecture/status` and `/architecture/content` endpoints into single `/architecture_document/` endpoint for better performance
- **Conflict Detection**: SHA256 content hashing prevents data loss when documents are modified externally
- **Enhanced UI**: Full-width document editing with dropdown codebase selection for improved usability

* [x] **Task 8.1: Backend API Improvements**
  * **COMPLETED**: Added new schemas `ArchitectureDocument`, `ArchitectureUpdateRequest`, and `ArchitectureUpdateResponse` for comprehensive architecture document operations
  * **COMPLETED**: Implemented `GET /api/codebases/{id}/architecture_document/` endpoint combining status and content in single call
  * **COMPLETED**: Implemented `PUT /api/codebases/{id}/architecture_document/` endpoint with SHA256-based conflict detection
  * **COMPLETED**: Updated `POST /api/codebases/{id}/architecture_document/generate` to use new URL structure
  * **COMPLETED**: Enhanced `CodebaseInvestigationService` with `get_architecture_document()` and `update_architecture_content()` methods
  * **COMPLETED**: Added content hashing utility and comprehensive conflict detection logic

* [x] **Task 8.2: Frontend UI Overhaul**  
  * **COMPLETED**: Redesigned Codebases component to use dropdown selection instead of sidebar for better horizontal space utilization
  * **COMPLETED**: Integrated new combined API endpoint reducing API calls from 2 to 1 for common workflows
  * **COMPLETED**: Added inline markdown editor with conflict detection and user-friendly error handling
  * **COMPLETED**: Implemented ability to create new architecture documents manually
  * **COMPLETED**: Added content hash tracking for proper conflict resolution
  * **COMPLETED**: Enhanced UX with clear loading states, error messages, and edit/save workflows

* [x] **Task 8.3: API Client & Type Safety**
  * **COMPLETED**: Updated frontend API client with new `getArchitectureDocument()` and `updateArchitectureDocument()` methods
  * **COMPLETED**: Added TypeScript interfaces for new API responses and request structures
  * **COMPLETED**: Maintained backward compatibility while deprecating old endpoints

## Phase 2: Advanced Agent Features

### Epic 9: Task Planning Agent Implementation ✅

**Major Refactoring Complete - Task Planning Agent Architecture**: Successfully implemented and refined the Task Planning Agent system with significant architectural improvements:

**Schema Simplification & Clarity**: 
- **DocumentEdit Schema**: Simplified from `{find, replace, context, rationale}` to `{find, replace}` for cleaner, more precise editing
- **TaskPlanningResponse Structure**: Refactored from dictionary-based `edits` field to explicit `task_specification_edits` and `task_implementation_plan_edits` arrays
- **TaskResponse Schema**: Removed unnecessary frontend state management fields (`can_edit_*`, `agent_processing`, `messages_count`) allowing frontend to handle state during HTTP requests

**Template System Modernization**:
- **Generic Template Service**: Refactored from method-based to enum-driven `get_template(TemplateType)` interface
- **Centralized Template Storage**: Moved architecture document template to file-based storage in `devboard/templates/architecture_document.md`
- **Template Type Enum**: Added `TASK_SPECIFICATION`, `IMPLEMENTATION_PLAN`, and `ARCHITECTURE_DOCUMENT` template types
- **Service Integration**: Updated Codebase Investigation Service to use centralized template system

**Model Architecture & Inheritance**:
- **BaseConversationMessage**: Created shared abstract parent for `TaskConversationMessage` and `ProjectConversationMessage` with common fields (`role`, `content`, `tool_data`, `created_at`)
- **Conversation Model Simplification**: Reduced duplication by moving shared logic to base class while maintaining domain-specific relationships

**Agent Configuration Integration**:
- **LLMService Integration**: Replaced hardcoded "openai:gpt-4o-mini" with `llm_service.get_preferred_model_for_agent(AgentType.PLANNING)`
- **Dynamic Model Selection**: Agent now uses configured model preferences with fallback hierarchy
- **Centralized Configuration**: Consistent with other agents using the configuration framework

* [x] **Task 9.1: Implement Task Conversation History** 
  * **COMPLETED**: Added `TaskConversationMessage` model inheriting from `BaseConversationMessage` pattern
  * **COMPLETED**: Implemented conversation storage with role-based messages and structured tool data
  * **COMPLETED**: Full conversation history storage (sliding window optimizations deferred)

* [x] **Task 9.2: Enhanced Task Planning Agent with Interactive Document Crafting**
  * **COMPLETED**: **State-Based Workflow**: Implemented task state progression (Pending → Designing → Planning → Implementing)
  * **COMPLETED**: **Structured Response Format**: Agent returns JSON with explicit `task_specification_edits` and `task_implementation_plan_edits` arrays
  * **COMPLETED**: **Document Editing Tools**: Simplified find-replace edit capability with precise text matching
  * **COMPLETED**: **Context Research Integration**: Full access to context providers during design and planning phases via `get_relevant_context()` tool
  * **COMPLETED**: **State-Aware Prompting**: Different agent prompts and capabilities based on task state (Designing vs Planning)
  * **COMPLETED**: **Atomic Edit Application**: Batch edit processing with user approval workflow
  * **COMPLETED**: **Model Configuration**: Dynamic model selection via LLMService configuration

* [x] **Task 9.3: Task Planning API Layer**
  * **COMPLETED**: `GET /api/tasks/{task_id}/messages` - Task conversation history endpoint
  * **COMPLETED**: `POST /api/tasks/{task_id}/messages` - Send message to planning agent endpoint with structured response storage
  * **COMPLETED**: `POST /api/tasks/{task_id}/apply-edits` - Apply structured document edits endpoint with separate field handling
  * **COMPLETED**: `POST /api/tasks/{task_id}/state-transition` - Manual state progression endpoint
  * **COMPLETED**: Enhanced task response schemas with simplified field structure

* [x] **Task 9.4: Frontend TypeScript Interface Updates**
  * **COMPLETED**: Updated `Task` interface to match backend schema with all required fields
  * **COMPLETED**: Added `DocumentEdit`, `TaskPlanningResponse`, `TaskConversationMessage` interfaces
  * **COMPLETED**: Added `TaskPlanningRequest`, `ApplyEditsRequest`, `StateTransitionRequest` interfaces  
  * **COMPLETED**: Added API client methods: `getTaskMessages()`, `sendTaskMessage()`, `applyDocumentEdits()`, `transitionTaskState()`
  * **COMPLETED**: Maintained type safety across frontend-backend communication

### Epic 10: PydanticAI Deferred Tools Migration ✅

**Major Architecture Upgrade COMPLETED**: Successfully migrated to PydanticAI's deferred tools pattern for enhanced user control over AI agent document editing operations.

**Implemented Architecture**:
- **Deferred Tools Pattern**: All document editing uses `approval_required=True` tools that pause execution for user approval
- **PydanticAI Message Storage**: Store full PydanticAI messages as JSON with minimal metadata schema
- **Shared Agent Infrastructure**: Created `BaseAgent` abstract class and `AgentConversationService` for shared functionality
- **Interactive Approval Workflow**: API endpoints for tool approval/denial with feedback support

* [x] **Task 10.1: Database Schema Updates**
  * **COMPLETED**: `BaseConversationMessage` abstract class stores PydanticAI messages with `message_type` and `pydantic_content` (JSON) fields
  * **COMPLETED**: `MessageType` enum categorizes messages (USER_PROMPT, TOOL_CALL, TEXT_RESPONSE, TOOL_RESULT, STRUCTURED_RESPONSE)
  * **COMPLETED**: Factory method `from_pydantic_message()` for creating records from PydanticAI messages
  * **COMPLETED**: `ProjectConversationMessage` and `TaskConversationMessage` concrete implementations

* [x] **Task 10.2: Shared Base Agent Service**
  * **COMPLETED**: `BaseAgent[TDeps]` abstract base class with generic dependency support
  * **COMPLETED**: `create_document_edit_tool()` factory function with `requires_approval=True`
  * **COMPLETED**: Pre-validation using `DocumentEditorService` before showing edits to user
  * **COMPLETED**: `AgentConversationService` handles message storage and tool approval processing

* [x] **Task 10.3: Task Planning Agent Refactor**
  * **COMPLETED**: Split into `TaskSpecificationAgent` and `TaskPlanningAgent` for different states
  * **COMPLETED**: Deferred tools implementation with `ApprovalRequired` exception pattern
  * **COMPLETED**: Edit validation using `DocumentEditorService.apply_edits()` before user approval
  * **COMPLETED**: State-aware system prompts and tool availability

* [x] **Task 10.4: Shared API Infrastructure**
  * **COMPLETED**: `/agent/messages` endpoints for both tasks and projects
  * **COMPLETED**: `/agent/approve-tools` endpoints for tool approval/denial with feedback
  * **COMPLETED**: `PromptResponse` type with MESSAGE and TOOL_REQUEST variants
  * **COMPLETED**: Message history loading via `convert_messages_to_pydantic()`

* [x] **Task 10.5: Project Agent Integration**
  * **COMPLETED**: `ProjectAgent` inherits from `BaseAgent[BaseDeps]`
  * **COMPLETED**: Uses same PydanticAI message storage as Task agents
  * **COMPLETED**: Document editing capability via `create_document_edit_tool()`
  * **COMPLETED**: Consistent API patterns with task agents

* [ ] **Task 10.6: Frontend Deferred Tools UI**
  * **PENDING**: Tool approval interface needs implementation in frontend
  * **PENDING**: Diff preview for proposed document edits
  * **PENDING**: Conversation state management for pending approvals
  * **Backend Ready**: All API endpoints and response formats implemented

* [ ] **Task 9.5: Frontend Task Planning Interface** (Updated)
  * **Three-Tab TaskDetail Interface**: Task Specification, Implementation Plan, Planning Agent tabs
  * **Document Editor Components**: Reuse existing ReactMarkdown + prose patterns with edit/view toggles
  * **Deferred Tool Approval UI**: Replace edit confirmation modal with deferred tool approval interface
  * **State Transition Controls**: UI buttons for progressing through design → planning → implementation
  * **Agent Conversation UI**: Chat interface with tool approval rendering and research summaries

### Epic 11: Conversation Model Refactor ✅

**Major Architecture Upgrade COMPLETED**: Successfully refactored the conversation messaging system from entity-specific models to a unified, polymorphic conversation architecture.

**Implemented Architecture**:
- **Polymorphic Conversations**: Single `Conversation` model with `parent_entity_type` and `parent_entity_id` for flexible entity associations
- **Unified Message Storage**: Single `ConversationMessage` table replacing separate `TaskConversationMessage` and `ProjectConversationMessage` tables
- **Sub-Conversation Support**: Optional `parent_conversation_id` for agent-to-agent internal conversations
- **Unified Repository**: Single `ConversationRepository` handling both conversations and messages, eliminating code duplication
- **Unified API**: Single `/conversations/{id}/messages` endpoint replacing entity-specific agent endpoints

* [x] **Task 11.1: Database Schema Refactor**
  * **COMPLETED**: Created `Conversation` model with polymorphic entity associations and optional parent conversation support
  * **COMPLETED**: Updated `ConversationMessage` model to reference conversations instead of entities directly
  * **COMPLETED**: Added `text_content` field for display-specific content that can differ from computed values
  * **COMPLETED**: Removed old `TaskConversationMessage` and `ProjectConversationMessage` models
  * **COMPLETED**: Database migration to new schema with table drops and recreation

* [x] **Task 11.2: Repository Layer Unification**
  * **COMPLETED**: Created unified `ConversationRepository` handling both conversation and message operations
  * **COMPLETED**: Implemented `get_or_create_for_entity()` for polymorphic conversation management
  * **COMPLETED**: Consolidated message CRUD operations into single repository
  * **COMPLETED**: Removed duplicate `ProjectConversationMessageRepository` and `TaskConversationMessageRepository`

* [x] **Task 11.3: Service Layer Updates**
  * **COMPLETED**: Updated `AgentConversationService` to work with conversation IDs instead of entity type/ID
  * **COMPLETED**: Created `get_conversation_agent()` dependency function for agent resolution based on conversation context
  * **COMPLETED**: Simplified service instantiation pattern with direct dependency injection

* [x] **Task 11.4: API Consolidation**
  * **COMPLETED**: Created unified `/conversations/{conversation_id}/messages` endpoints for all agent communication
  * **COMPLETED**: Updated project and task GET endpoints to include `default_conversation_id` in responses
  * **COMPLETED**: Removed duplicate entity-specific agent endpoints (`/projects/{id}/agent/messages`, `/tasks/{id}/agent/messages`)
  * **COMPLETED**: Maintained backward compatibility through conversation ID provision in entity responses

* [x] **Task 11.5: Testing & Documentation Updates**
  * **COMPLETED**: Rewrote conversation repository tests for new unified structure
  * **COMPLETED**: Updated PROJECT_SPECIFICATION.md with conversation architecture details
  * **COMPLETED**: Verified all existing functionality works with new architecture

**Benefits Achieved**:
- **Code Simplification**: Eliminated duplicate repository and service logic
- **API Consistency**: Single conversation API pattern across all entity types
- **Extensibility**: Easy to add new entity types (e.g., codebase conversations) without code duplication
- **Sub-Conversation Support**: Foundation for agent-to-agent internal conversations
- **Cleaner Frontend Integration**: Frontend only needs conversation ID to communicate with any agent
  * **Document Locking**: Disable editing during agent processing and pending approvals

* [ ] **Task 9.6: Document Structure Templates**
  * **Task Specification Template**: Structured markdown template with Objective, Context, Requirements, Acceptance Criteria
  * **Implementation Plan Template**: Technical plan template with Summary, Analysis, Steps, Testing Strategy
  * **Template Initialization**: Auto-populate new tasks with structured templates

* [ ] **Task 9.7: Task Implementation Agent**
  * Build Implementation Agent using Claude Code SDK with codebase access and GitHub PR creation.
  * Maintain existing "baton pass" handoff model from Planning Agent

* [ ] **Task 9.8: Add Background Task Runner**
  * Implement Huey/Dramatiq for long-running agent sessions with WebSocket progress updates.