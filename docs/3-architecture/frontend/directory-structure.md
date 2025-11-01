# Frontend Directory Structure

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > [Frontend](./INDEX.md) > Directory Structure

## Overview

React/TypeScript application with feature-based component organization. Location: `/frontend/src/`

## Directory Tree

```
frontend/src/
├── components/              # Feature-based UI components
│   ├── ui/                 # Primitive UI library (Button, Card, Input, Textarea, Modal, StatusBadge, Markdown, ErrorBoundary, ErrorMessage)
│   ├── layout/             # App shell, tabs, navigation (AppShell, Layout, TabBar, Tab, TabContentContainer, TopBar, NavigationMenu)
│   ├── chat/               # Conversation system (AgentChat, ConversationChat, ConversationInput, ConversationMessage, ConversationMessageList, ConversationModelSelector, PendingMessage, AgentReasoning, ToolCallDisplay)
│   ├── approvals/          # Hierarchical tool approval UI
│   │   ├── common/         # Generic approval components (PendingApprovalsList, ApprovalActions)
│   │   └── documents/      # Document-specific approvals (DocumentEditApproval, DocumentApprovalModal)
│   ├── documents/          # Document viewing (DocumentEditViewer, DocumentContentViewer, DocumentDiffModal, InlineChangeHighlighter)
│   ├── configuration/      # Settings UI (ConfigurationForm, ConfigurationField, ConfigurationList, ConfigurationListItem, ConfigurationSection, AgentConfigurationSelector, AgentModelSelector)
│   ├── notifications/      # NotificationsPanel
│   └── __tests__/          # Component tests
├── views/                  # Page components
│   ├── Home.tsx           # Project/codebase dashboard
│   ├── ProjectDetail.tsx  # Project Q&A
│   ├── TaskDetail.tsx     # Task specification/planning
│   ├── Settings.tsx       # Configuration UI
│   └── __tests__/         # View tests
├── hooks/                  # Custom React hooks
│   ├── useApi.ts          # Generic API with loading/error states
│   ├── useAsyncOperation.ts # Async operation standardization
│   ├── useCodebases.ts    # Codebase CRUD operations
│   ├── useEditableField.ts # Edit/save/cancel pattern
│   ├── useKeyboardShortcuts.ts # Global keyboard handlers
│   ├── useModal.ts        # Modal state management
│   ├── useProjects.ts     # Project CRUD operations
│   ├── useTabTitle.ts     # Dynamic tab titles
│   ├── useTasks.ts        # Task CRUD operations
│   ├── useURLSync.ts      # URL/tab state sync
│   └── index.ts           # Hook exports
├── stores/                 # Zustand state management
│   ├── uiStore.ts         # Tabs, navigation (localStorage persistence)
│   ├── dataStore.ts       # Normalized entity cache with Maps
│   ├── conversationStore.ts # Conversation state management
│   ├── notificationStore.ts # Notification state
│   ├── projectUIStore.ts  # Project UI state
│   └── taskUIStore.ts     # Task UI state
├── services/
│   ├── ActivityManager.ts # Background operation tracking
│   ├── WebSocketManager.ts # WebSocket singleton (connection pooling, auto-reconnect)
│   └── toolApprovalConfig.ts # Tool approval configuration
├── lib/
│   ├── api.ts             # Typed HTTP client with NDJSON streaming
│   └── streaming.ts       # Streaming utilities
├── contexts/               # React context providers
│   ├── DarkModeContext.tsx
│   ├── ApprovalsContext.tsx
│   └── PendingMessagesContext.tsx
├── styles/                 # Design system
│   ├── designSystem.ts    # Colors, typography, layouts
│   ├── inputStyles.ts     # Standardized input styling
│   └── messageStyles.ts   # Message component styles
├── utils/                  # Utilities
│   ├── agentRoles.ts      # Agent role utilities
│   ├── approvalKeys.ts    # Approval key generation
│   ├── diffUtils.ts       # Diff utilities
│   └── toolTypeUtils.ts   # Tool type utilities
├── test/                   # Test configuration
│   ├── setup.ts
│   ├── utils.tsx
│   └── mocks/             # MSW API mocks
├── App.tsx                 # Routing
├── main.tsx                # Entry point + Immer
└── index.css               # Global styles
```

## Component Hierarchy

**Tier 1 - UI Library** (`components/ui/`): Primitive components with theming, no business logic

**Tier 2 - Features** (`components/`): Domain components using UI library
- `layout/`: Application shell, tab system
- `chat/`: Event-based conversations with streaming
- `approvals/`: Tool approval workflows (common + document-specific)
- `documents/`: Diff viewer, read-only display
- `configuration/`: Dynamic forms, agent model selection
- `notifications/`: Notification panel

**Tier 3 - Views** (`views/`): Page-level components combining features, managing page state, URL routing

## Key Directories

### Hooks (`src/hooks/`)

State management and data fetching:
- State: `useModal`, `useAsyncOperation`, `useEditableField`
- API: `useApi`, `useProjects`, `useTasks`, `useCodebases`
- UI: `useTabTitle`, `useURLSync`, `useKeyboardShortcuts`

### Stores (`src/stores/`)

Zustand with Immer:
- `uiStore`: Tab/navigation state with localStorage persistence
- `dataStore`: Normalized entity cache (Maps for efficient lookups)
- `conversationStore`: Conversation state management
- `notificationStore`: Notification state
- `projectUIStore`: Project-specific UI state
- `taskUIStore`: Task-specific UI state

### Services (`src/services/`)

- `ActivityManager.ts`: Background operation tracking
- `WebSocketManager.ts`: Singleton with connection pooling (max 10), auto-reconnect with backoff, message routing to stores
- `toolApprovalConfig.ts`: Tool approval configuration and rules

### Lib (`src/lib/`)

- `api.ts`: Typed HTTP client with sync/streaming methods, NDJSON parsing, error handling
- `streaming.ts`: Streaming utilities for NDJSON processing

### Styles (`src/styles/`)

- `designSystem.ts`: Centralized colors, typography, layouts, transitions
- `inputStyles.ts`: Theme-aware form elements with disabled/feedback states
- `messageStyles.ts`: Message component styling utilities

### Build Configuration

- **Vite** (`vite.config.ts`): Fast builds, HMR, path aliases
- **TypeScript** (`tsconfig.json`): Strict type checking, path mappings
- **Tailwind** (`tailwind.config.js`): Custom design system, dark mode

## Import Patterns

Components use relative imports adjusted for nesting:

```typescript
// UI library
import { Button } from '../ui/Button'

// Cross-feature
import { DocumentDiffModal } from '../documents/DocumentDiffModal'

// Stores/services
import { useUIStore } from '../../stores/uiStore'
import { apiClient } from '../../lib/api'
```