# Overview
We are working to develop an application as described in @docs/INDEX.md

# Global Guidelines
- After making changes to the design or implementation details, ALWAYS:
  - Consider whether corresponding changes need to be made in the Frontend application
  - Add or update any relevant tests to cover the changes
  - Run tests to ensure everything works as expected
  - Update documentation in docs/ accordingly


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
- Do not use `db_session.commit()` unless transaction management is explicitly required (should be handled automatically by request lifecycle)

## Testing
- Tests mirror source structure (`devboard/agents/base_agent.py` → `tests/agents/test_base_agent.py`)
- Use fixtures from `backend/devboard/tests/conftest.py`, `@pytest.mark.asyncio`, TestClient with mocked dependencies
- Only mock data-layer repositories or external integrations — never Service classes or methods
- Run: `uv run --frozen --active pytest -q --tb=short 2>&1` (never filter with grep)

## Development Process
- `make format` — reformat code and remove unused imports
- `make lint` — check for linting errors

## Patterns
- Use logfire for logging instead of standard logging module
- when there is an error in a tool, raise ModelRetry exception instead of returning an error text string

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
- Vitest + React Testing Library + MSW; colocated in `__tests__/` directories
- User-centric queries, `renderHook` for custom hooks, MSW for API mocking
- Never filter output with grep

## Scripts
- `pnpm dev` / `pnpm build` / `pnpm lint`
- `NO_COLOR=1 pnpm test:run 2>&1` — all tests (no ANSI color codes) | `NO_COLOR=1 pnpm test <file>` — specific file | `pnpm test:coverage`
- Console output from app code is suppressed globally via `onConsoleLog: () => false` in `vitest.config.ts`