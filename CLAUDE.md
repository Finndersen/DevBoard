# Overview
We are working to develop an application as described in @docs/INDEX.md

# Documentation Structure
The `docs/` directory contains comprehensive documentation which you should read as required.

```
docs/
├── INDEX.md                              # Main documentation entry point
├── MAINTENANCE_GUIDE.md                  # Guide for maintaining documentation
├── 1-overview/
│   ├── INDEX.md                          # Overview section entry
│   ├── vision-and-goals.md              # Strategic objectives
│   ├── key-concepts.md                  # Core domain concepts
│   └── user-workflows.md                # User interaction patterns
├── 2-features/
│   ├── INDEX.md                          # Features section entry
│   ├── project-management.md            # Project management capabilities
│   ├── task-management.md               # Task lifecycle and workflows
│   ├── codebase-documentation.md        # Codebase documentation features
│   ├── configuration-system.md          # Configuration management
│   ├── document-collaboration.md        # Document editing features
│   └── file-change-viewer.md            # File change viewing
├── 3-architecture/
│   ├── INDEX.md                          # Architecture section entry
│   ├── system-design.md                 # High-level system design
│   ├── database-schema.md               # Database models and relationships
│   ├── api-design.md                    # API design principles
│   ├── backend/
│   │   ├── INDEX.md                      # Backend architecture entry
│   │   ├── directory-structure.md       # Backend code organization
│   │   ├── components.md                # Backend component descriptions
│   │   ├── patterns.md                  # Backend development patterns
│   │   └── api-reference.md             # API endpoint documentation
│   └── frontend/
│       ├── INDEX.md                      # Frontend architecture entry
│       ├── directory-structure.md       # Frontend code organization
│       ├── components.md                # Frontend component architecture
│       ├── patterns.md                  # Frontend development patterns
│       └── streaming.md                 # NDJSON streaming implementation
├── 4-ai-agents/
│   ├── INDEX.md                          # AI Agents section entry
│   ├── agent-architecture.md            # Role-based agent architecture
│   ├── conversation-system.md           # Event-based conversation patterns
│   ├── tools-and-capabilities.md        # Tool system and approval workflows
│   ├── context-assembly.md              # Context gathering strategies
│   ├── configuration.md                 # Agent configuration system
│   └── claude-code-integration.md       # Claude Code CLI integration
├── 5-integrations/
│   ├── INDEX.md                          # Integrations section entry
│   ├── external-services.md             # GitHub, Jira, Slack integrations
│   ├── context-providers.md             # Context provider architecture
│   └── llm-providers.md                 # LLM provider support
├── 6-development/
│   ├── INDEX.md                          # Development section entry
│   ├── getting-started.md               # Setup and local development
│   ├── testing.md                       # Testing strategies and patterns
│   ├── deployment.md                    # Deployment instructions
│   └── contributing.md                  # Contribution guidelines
└── archive/
    ├── ARCHITECTURE.md                   # Legacy architecture docs
    └── PROJECT_SPECIFICATION.md          # Legacy specification docs
```

# Global Guidelines
- After making changes to the design or implementation details, ALWAYS:
  - make appropriate corresponding updates to the documentation in `docs/`
  - Consider whether corresponding changes need to be made in the Frontend application
  - Add or update any relevant tests to cover the changes
  - Run tests to ensure everything works as expected


# Backend Development Guidelines
## Overview
@backend/README.md

## Architecture Patterns
- **Layered Structure**: API (routers) → Services (business logic) → Repositories (data access)
- **Dependency Injection**: Use FastAPI dependencies for DB sessions and services (`Depends(get_db)`, factory functions in `api/dependencies/`)
- **Generic Repository**: `BaseRepository[T]` provides type-safe CRUD operations
- **Event Streaming**: Use `stream_conversation_events()` helper for NDJSON streaming responses
- **Configuration**: Hierarchical resolution (environment > database > defaults)

## Database Patterns
- **SQLAlchemy 2.0**: Use `Mapped[]` annotations, `select()` statements, bidirectional relationships with `back_populates`
- **Polymorphic Conversations**: Single Conversation model for all entities (Project/Task/Codebase) using `entity_type`/`entity_id`
- **Conflict Detection**: Document model uses SHA-256 `content_hash` for optimistic locking
- **Lazy Initialization**: Conversations created via `get_or_create_for_entity()` when accessing entity details

## Testing
- **Structure**: Tests mirror source (`devboard/agents/base_agent.py` → `tests/agents/test_base_agent.py`)
- **Fixtures**: Use available fixtures in `backend/devboard/tests/conftest.py`
- **Async Tests**: Use `@pytest.mark.asyncio` decorator
- **API Testing**: Use TestClient with mocked dependencies

## Development Process
- Run `make format` to automatically reformat code and remove unused imports instead of manually editing
- Run `make lint` to check for linting errors after making changes


# Frontend Development Guidelines

## Architecture Patterns
- **Three-Tier Structure**: UI Components (`components/ui/`) → Feature Components (`components/`) → Views (`views/`)
- **Custom Hooks**: Encapsulate API calls, loading states, error handling in `hooks/` (e.g., `useEditableField`)
- **Design System**: Centralized styles in `styles/` (designSystem.ts, inputStyles.ts, messageStyles.ts)
- **State Management**: Zustand stores with Immer middleware in `stores/` (UIStore, DataStore, ConversationStore, etc.)
- **Type-Safe API**: Discriminated unions for events with type guards, comprehensive TypeScript coverage

## Coding Style
- **Type Imports**: Use type-only imports (`import type { XYZ } from '...'`)
- **TypeScript**: Type all props/state/args, use `interface` for objects, `type` for unions, avoid `any`
- **Components**: Functional components with hooks, destructure props, PascalCase naming
- **State**: Use `useState` for simple state, `useReducer` for complex logic, never mutate directly

## Testing
- **Framework**: Vitest + React Testing Library + MSW (API mocking)
- **Structure**: Colocated tests in `__tests__/` directories
- **Command**: Use `npm run test *`, NOT `timeout XXX npm run test *`
- **Patterns**: User-centric queries, renderHook for custom hooks, MSW for API mocking