# Overview
We are working to develop an application as described in @docs/INDEX.md

# Global Guidelines
- After making changes to the design or implementation details, ALWAYS:

  - Consider whether corresponding changes need to be made in the Frontend application
  - Add or update any relevant tests to cover the changes
  - Run tests to ensure everything works as expected


# Backend Development Guidelines
## Overview
@backend/README.md

## Architecture Patterns
- **Layered Structure**: API (routers) → Services (business logic) → Repositories (data access)
  - In services, never access the DB session of repositories directly, only use repository methods
  - Never access the dependency attributes of a service (e.g. repositories) directly, always use service methods
  - Never call db_session.commit() unless transaction management is explicitly required
- **Dependency Injection**: Use FastAPI dependencies for DB sessions and services (`Depends(get_db)`, factory functions in `api/dependencies/`)
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
- NEVER patch Service classes or methods doing testing, only lower level dependencies such as data-layer repositories or filesystem/git/external integrations

## Development Process
- Run `make format` to automatically reformat code and remove unused imports instead of manually editing
- Run `make lint` to check for linting errors after making changes

## Patterns
- Use logfire for logging instead of standard logging module

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
- **Command**: Use `pnpm test *`, NOT `timeout XXX pnpm test *`
- **Patterns**: User-centric queries, renderHook for custom hooks, MSW for API mocking