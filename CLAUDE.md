# Overview
We are working to develop an application as described in @docs/INDEX.md

# Global Guidelines
- When planning and making code changes in this repo, ALWAYS:
  - Consider whether corresponding changes need to be made in the Frontend application
  - Add or update any relevant tests to cover the changes
  - Run tests to ensure everything works as expected
  - Make appropriate updates to the documentation in `docs/` accordingly


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
- Use fixtures from `backend/tests/conftest.py`, `@pytest.mark.asyncio`, TestClient with mocked dependencies
- Only mock data-layer repositories or external integrations — never Service classes or methods
- Run: `uv run --frozen --active pytest -q --tb=short 2>&1` (never filter with grep)
- If failure output is truncated, pipe to a temp file and read from the start: `uv run --frozen --active pytest -q --tb=short > /tmp/pytest.txt 2>&1; head -100 /tmp/pytest.txt`

## Development Process
- `make lint` — auto-fix formatting and lint issues with ruff (~1-2s, run frequently during iteration)
- `make typecheck` — type-check with pyright (~40s)
- `make validate` — run lint + typecheck together; use as a final gate before marking work complete, not on every iteration

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

## Design System Rules
- **Never hardcode** Tailwind color, border-color, or background-color classes — always use design system tokens from `styles/designSystem.ts`
- **Text colors**: Use `textColors.primary` (headings/labels), `textColors.secondary` (descriptions), `textColors.muted` (placeholders/timestamps), `textColors.accent` (links)
- **Borders**: Use `borderColors.default` (panels/cards/dividers), `borderColors.input` (form inputs/selects), `borderColors.focus` (focus rings)
- **Surfaces/backgrounds**: Use `surfaces.raised` (cards, modals, dropdowns), `surfaces.sunken` (inset sections, code blocks), `surfaces.base` (page background)
- **Status messages**: Use `<Alert variant="error|warning|info|success">` component — not raw colored `div` elements
- **Status colors inline**: Use `statusColors.error.*`, `statusColors.warning.*`, `statusColors.success.*`, `statusColors.info.*` for `bg`/`text`/`border`/`icon`
- **Hover states**: Use `hoverColors.subtle` (list rows, sidebar items) or `hoverColors.default` (buttons, clickable elements)
- **Containers**: Use `<Card>` or `<Surface variant="raised">` for elevated containers; `<Surface variant="sunken">` for inset containers

## Coding Style
- **Type Imports**: Use type-only imports (`import type { XYZ } from '...'`)
- **TypeScript**: Type all props/state/args, use `interface` for objects, `type` for unions, avoid `any`
- **Components**: Functional components with hooks, destructure props, PascalCase naming
- **State**: Use `useState` for simple state, `useReducer` for complex logic, never mutate directly

## Testing
- Vitest + React Testing Library + MSW; colocated in `__tests__/` directories
- User-centric queries, `renderHook` for custom hooks, MSW for API mocking
- Never filter output with grep
- When a test fails, read the **beginning** of the output to find the failing file/test name — Vitest prints it early. Use `| head -80` or pipe to a temp file; do NOT grep for `FAIL`/`×`/`failed` as Vitest's format makes these unreliable

## Scripts
- `pnpm dev` / `pnpm build` / `pnpm lint`
- `NO_COLOR=1 pnpm test:run 2>&1` — all tests (no ANSI color codes) | `NO_COLOR=1 pnpm test <file>` — specific file | `pnpm test:coverage`
- Console output from app code is suppressed globally via `onConsoleLog: () => false` in `vitest.config.ts`