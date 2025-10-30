# Frontend Development Patterns

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Frontend](./INDEX.md) > Patterns

## Overview

Development patterns and conventions for DevBoard frontend. Focus on DevBoard-specific architectural decisions.

**Location**: `frontend/src/`

## Component Architecture

### Three-Tier Structure

**Tier 1: UI Components** (`components/ui/`): Primitive, reusable, no business logic, theme-aware
**Tier 2: Feature Components** (`components/`): Domain-specific, uses UI library, isolated concerns
**Tier 3: Views** (`views/`): Page-level, combines features, manages page state, routing integration

### Component Composition

Views compose feature components, which use UI primitives. Clear data flow from parent to child.

## Custom Hooks Pattern

**Data Fetching**: Encapsulate API calls, loading states, error handling in custom hooks (`hooks/`)

**Example Pattern**:
```typescript
function useProject(id: number): { project: Project | null, loading: boolean, error: Error | null }
```

**Editable Field Pattern** (`useEditableField`): Combines `useAsyncOperation` for edit/save/cancel workflow with loading/error states.

**Benefits**: Consistent error handling, logic reuse, simplified components.

## Design System

**Location**: `frontend/src/styles/`

**designSystem.ts**: Color palette, spacing, layout utilities, transitions. All Tailwind classes for consistency.

**inputStyles.ts**: Standardized form input styles across all input types (base, chat, textarea, feedback).

**messageStyles.ts**: Message component styling utilities, role-based styling (user, assistant, system).

**Theme-Aware**: All components support light/dark mode via Tailwind `dark:` prefix.

## Type-Safe API Integration

**Comprehensive Interfaces**: Full TypeScript coverage from API responses to UI components (`frontend/src/lib/api.ts`).

**Discriminated Unions for Events**:
```typescript
type ConversationEvent =
  | { event_type: 'text_message'; ... }
  | { event_type: 'tool_call'; ... }
  | { event_type: 'tool_result'; ... }
```

**Type Guards**: Switch statements on `event_type` provide exhaustive pattern matching and type narrowing.

**Benefits**: Compile-time error detection, IDE autocomplete, refactoring safety.

## State Management

### Zustand Store Pattern

**Location**: `frontend/src/stores/`

Lightweight reactive stores with Immer middleware for immutable updates.

**UIStore** (`uiStore.ts`): Tab management (tabs array, activeTabId, addTab, closeTab, setActiveTab)
**DataStore** (`dataStore.ts`): Normalized entity caching using Map-based storage (projects, tasks, codebases)
**ConversationStore** (`conversationStore.ts`): Conversation state management
**NotificationStore** (`notificationStore.ts`): Notification state and unread tracking
**ProjectUIStore** (`projectUIStore.ts`): Project-specific UI state (expanded sections, filters)
**TaskUIStore** (`taskUIStore.ts`): Task-specific UI state (editor modes, panel visibility)

**Benefits**: Simple API, immutable updates with Immer, TypeScript support, React hooks integration.

### Normalized Entity Caching

Map-based entity storage (`Map<number, Entity>`) prevents data duplication and enables efficient lookups by ID. Automatic UI updates when data changes.

## Error Handling

**Error Boundary** (`components/ui/ErrorBoundary.tsx`): React class component catching JavaScript errors with fallback UI and reload functionality.

**ErrorMessage Component** (`components/ui/ErrorMessage.tsx`): Standardized error display with retry actions.

**Pattern**: Wrap application routes in ErrorBoundary for graceful error handling.

## Performance Optimization

**Memoization**: `React.memo` for components, `useMemo` for expensive computations.

**Lazy Loading**: Route-based code splitting with `React.lazy` and `Suspense`.

**Pattern**: Split views at route level for faster initial load.

## Testing Patterns

**Component Testing**: React Testing Library with user-centric tests (`frontend/src/components/**/__tests__/`)

**Hook Testing**: `renderHook` from `@testing-library/react` for independent hook testing

**API Mocking**: Mock Service Worker (MSW) for realistic API testing with request handlers

**Test Location**: Tests colocated with components in `__tests__` directories

## DevBoard-Specific Patterns

### Event-Based Conversation System

**ConversationChat** renders `list[ConversationEvent]` from API. Events matched by type and rendered with appropriate components.

**Tool Call/Result Matching**: `findToolResult()` helper searches forward from ToolCall position by `tool_call_id` to pair ToolCall with ToolResult for integrated display.

### Tab System with Deep Linking

**useURLSync Hook**: Bidirectional synchronization between URL hash and tab state. URL format: `#entity-type:entity-id` (e.g., `#project:1`, `#task:5`).

**useTabTitle Hook**: Updates tab titles dynamically from entity data. Monitors entity changes and refreshes tab titles.

**Pattern**: Shareable URLs, browser back/forward support, persistent state across page reloads.

### Agent Configuration System

**Three-Layer Configuration**: Environment variables override database values, which override defaults.

**AgentModelSelector**: Engine selection dropdown filters available models by engine's supported provider. "Default" option for engines supporting configuration inheritance.

**Pattern**: Field-level source tracking (`environment`, `database`, `default`). Environment variables displayed as disabled fields.

### Tool Approval Hierarchy

**Generic Approval** (`components/approvals/common/`): Standard approval UI for all tools
**Document-Specific Approval** (`components/approvals/documents/`): Specialized approval with diff preview for document edits

**Pattern**: Type-specific approval components extend base approval functionality. Document approvals show full diff before user accepts/rejects.

### Streaming NDJSON Processing

**API Client**: Async generator methods for streaming endpoints. Parse NDJSON line-by-line, yield `ConversationEvent` objects.

**Pattern**: `for await (const event of apiClient.sendMessageStream(...))` for real-time event processing in React components.

## See Also

- [Directory Structure](./directory-structure.md) - Code organization
- [Components](./components.md) - Component implementations
- [Streaming](./streaming.md) - Real-time updates
- [System Design](../system-design.md) - Overall architecture
