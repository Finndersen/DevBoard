# Frontend Components

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Frontend](./INDEX.md) > Components

## Overview

Three-tier component architecture: primitive UI components, feature-specific components, and page-level views.

**Location**: `frontend/src/components/`

## UI Component Library

**Location**: `frontend/src/components/ui/`

Standard primitives with consistent theming and variants:

- **Button** (`Button.tsx`): Variants (primary, secondary, outline, ghost), sizes (sm, md, lg), loading/disabled states, icon support
- **Card** (`Card.tsx`): Flexible container with padding options, hover effects, click handlers
- **Input** (`Input.tsx`): Form input with labels, error states, left/right icons, accessibility
- **Textarea** (`Textarea.tsx`): Multi-line input matching Input theming
- **Modal** (`Modal.tsx`): Sizes (sm, md, lg, xl), escape/click-outside handling, focus trap, ARIA attributes
- **StatusBadge** (`StatusBadge.tsx`): Semantic colors (default, success, warning, error, info)
- **Markdown** (`Markdown.tsx`): Markdown rendering with syntax highlighting
- **ErrorBoundary** (`ErrorBoundary.tsx`): React error boundary with fallback UI
- **ErrorMessage** (`ErrorMessage.tsx`): Standardized error display with retry actions

## Layout Components

**Location**: `frontend/src/components/layout/`

Application shell with browser-style tab system:

- **AppShell** (`AppShell.tsx`): Main shell with tab management, activity indicators, deep linking. Layout: top bar, tab bar, content area.
- **Layout** (`Layout.tsx`): Root layout component with theme provider
- **TabBar** (`TabBar.tsx`): Horizontal scrolling tabs, reordering, close buttons
- **Tab** (`Tab.tsx`): Individual tab with entity icons, activity indicators (● default, ⚡ agent running, 🔴 action required)
- **TabContentContainer** (`TabContentContainer.tsx`): Content wrapper for tab views
- **TopBar** (`TopBar.tsx`): Navigation bar with branding, notifications, theme toggle
- **NavigationMenu** (`NavigationMenu.tsx`): Slide-out menu with quick links

## Chat Components

**Location**: `frontend/src/components/chat/`

Event-based agent conversation system with streaming support.

### ConversationChat

**File**: `ConversationChat.tsx`

Core chat rendering `list[ConversationEvent]` from API.

**Event Rendering**:
- `event_type="text_message"` → ConversationMessage component
- `event_type="tool_call"` → ToolCallDisplay component
- `event_type="tool_result"` → Matched to parent ToolCall via `findToolResult()` helper
- `event_type="tool_call_request"` → Tool approval UI

**Tool Call/Result Matching**: `findToolResult()` searches forward from ToolCall position by `tool_call_id`, passes result to ToolCallDisplay for integrated display.

### ToolCallDisplay

Expandable card displaying tool invocation with arguments and results.

**Collapsed**: Tool icon, name, status indicator (spinner/checkmark/X), timestamp, color-coded border
**Expanded**: Arguments section (JSON), result section with "Returned:" timestamp
**Interactive**: Click to toggle, stop propagation on expanded content for text selection

### Other Chat Components

- **AgentChat** (`AgentChat.tsx`): Wrapper with clear history button and modal confirmation
- **ConversationMessage** (`ConversationMessage.tsx`): Role-based styling, markdown rendering, copy functionality
- **ConversationMessageList** (`ConversationMessageList.tsx`): Scrollable message list container with auto-scroll
- **ConversationInput** (`ConversationInput.tsx`): Input field with send button, enter-to-send
- **ConversationModelSelector** (`ConversationModelSelector.tsx`): Model selection dropdown for conversation settings
- **PendingMessage** (`PendingMessage.tsx`): Pending/sending state with retry capability
- **AgentReasoning** (`AgentReasoning.tsx`): Agent reasoning/thinking display

### Event Handler System

**ConversationEventHandlerProvider** (`ConversationEventHandlerProvider.tsx`): React Context provider that maintains event handler registries for processing conversation events with side effects. Enables decoupled event handling separate from UI rendering.

**Registries**:
- Tool Result Handlers: React to successful tool executions (document edits, workflow actions, etc.)
- System Event Handlers: React to system-level events (task updates, conversation changes, workflow transitions)

**Architecture**: Provider wraps parent views (TaskDetail, ProjectDetail) at TabContentContainer level, ensuring single registry per conversation context. Child components register handlers via hooks that execute automatically when matching events stream through ConversationChat.

**Hooks** (`hooks/useConversationEventHandlers.ts`):
- `useToolResultHandler(matcher, handler)`: Register handlers for specific tool completions. Matcher receives tool name and event, handler receives ToolResult. Error results automatically filtered out.
- `useSystemEventHandler(matcher, handler)`: Register handlers for system events. Matcher receives SystemEvent, handler processes data (e.g., refetch on task status change).
- `useEventHandlerRegistryForStream()`: Internal hook for ConversationChat to retrieve registry for stream processor integration.

**Use Cases**:
- Refetch documents after agent edits them via MCP tools
- Update UI state when tasks transition between workflow states
- Refresh entity data when workflow actions complete (implementation plan creation, status transitions)
- Coordinate multiple component updates from single event (task status + conversation ID + plan ID)
- Switch to relevant tabs after tool execution (e.g., show Plan tab after plan update)

**Pattern**: Components register handlers on mount, handlers execute when matching events stream, handlers auto-cleanup on unmount. Multiple handlers can match single event. Supports async handlers with Promise.all() execution.

## Approval System

**Location**: `frontend/src/components/approvals/`

Hierarchical tool approval with generic and document-specific handling.

### Generic Approval (`approvals/common/`)

- **PendingApprovalsList** (`PendingApprovalsList.tsx`): Batch approval interface, approve/deny all functionality
- **ApprovalActions** (`ApprovalActions.tsx`): Action buttons with argument modification support

### Document-Specific (`approvals/documents/`)

- **DocumentEditApproval** (`DocumentEditApproval.tsx`): Document edit wrapper with diff preview
- **DocumentApprovalModal** (`DocumentApprovalModal.tsx`): Modal with full diff viewer

## Document Components

**Location**: `frontend/src/components/documents/`

Document viewing/editing with diff visualization.

- **DocumentEditViewer** (`DocumentEditViewer.tsx`): Diff viewer with modes (cards: side-by-side, unified: inline), syntax highlighting, toggle
- **DocumentContentViewer** (`DocumentContentViewer.tsx`): Read-only markdown display
- **DocumentDiffModal** (`DocumentDiffModal.tsx`): Full-screen diff modal with accept/reject
- **InlineChangeHighlighter** (`InlineChangeHighlighter.tsx`): Character-level diff highlighting
- **GitDiffViewer** (`GitDiffViewer.tsx`): Git diff viewer with syntax highlighting, collapsible file sections, line numbers (old/new), language auto-detection (30+ languages via Prism), dark mode support
- **AllFilesDiffViewer** (`AllFilesDiffViewer.tsx`): Multi-file diff container with refresh capability, statistics display, empty state handling, timestamp tracking

## Configuration Components

**Location**: `frontend/src/components/configuration/`

- **ConfigurationForm** (`ConfigurationForm.tsx`): Schema-driven form generation, field validation, source tracking (environment/database/default)
- **ConfigurationField** (`ConfigurationField.tsx`): Dynamic field renderer supporting text, number, boolean, select, textarea. Source indicators, disabled for env vars.
- **ConfigurationList** (`ConfigurationList.tsx`): List container for configuration items
- **ConfigurationListItem** (`ConfigurationListItem.tsx`): Individual configuration list item with edit/delete actions
- **ConfigurationSection** (`ConfigurationSection.tsx`): Collapsible configuration section grouping
- **AgentConfigurationSelector** (`AgentConfigurationSelector.tsx`): Agent configuration selection dropdown
- **AgentModelSelector** (`AgentModelSelector.tsx`): Engine selection dropdown, model dropdown filtered by engine's provider. "Default" option for supporting engines.

## Notification System

**Location**: `frontend/src/components/notifications/`

- **NotificationsPanel** (`NotificationsPanel.tsx`): Dropdown with notification types (tool approvals, agent complete, agent blocked, messages). Unread badges, click-to-navigate, mark-as-read.

## Custom Hooks

**Location**: `frontend/src/hooks/`

Type-safe data fetching and state management.

**State Management**:
- `useModal`: Modal state
- `useAsyncOperation`: Async operation standardization
- `useEditableField`: Edit/save/cancel pattern

**API Hooks**:
- `useApi`: Generic data fetching
- `useProjects`, `useTasks`, `useCodebases`: Entity CRUD operations

**UI Hooks**:
- `useTabTitle`: Dynamic tab title updates from entity data
- `useURLSync`: Bidirectional URL/tab state sync
- `useKeyboardShortcuts`: Global keyboard handlers

## Design System

**Location**: `frontend/src/styles/`

Centralized design tokens and styling utilities.

- **designSystem.ts**: Color palette, text/border colors, focus states, transitions, layout patterns
- **inputStyles.ts**: Base input styles, chat input, textarea, feedback input, disabled states, theme-aware styling
- **messageStyles.ts**: Message component styling utilities, role-based styling

## Views

**Location**: `frontend/src/views/`

Top-level page components.

- **Home** (`Home.tsx`): Unified dashboard with projects/codebases grids, create functionality
- **ProjectDetail** (`ProjectDetail.tsx`): Tabs (Board: task list, Editor: project spec, Settings). Agent conversation panel, task creation, resource linking.
- **TaskDetail** (`TaskDetail.tsx`): Task spec editor, implementation plan editor, state-driven agent panels (different agents per state)
- **Settings** (`Settings.tsx`): Integration setup, agent configuration per role, codebase registration

## API Client

**Location**: `frontend/src/lib/api.ts`

Typed HTTP client with TypeScript interfaces.

**Methods**:
- Synchronous: Return complete responses
- Async generators: Stream NDJSON events
- Coverage: Project/task/codebase CRUD, conversation messaging (standard/streaming), tool approval (standard/streaming), configuration management
