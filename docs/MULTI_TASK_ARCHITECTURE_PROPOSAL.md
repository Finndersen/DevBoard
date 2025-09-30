# Multi-Task Architecture Proposal: Browser Tab-Style Interface

## Overview

This document proposes a significant architectural enhancement to DevBoard to support multi-task workflows with browser tab-style navigation, persistent conversation states, and concurrent agent operations. The current single-context architecture needs evolution to support power users managing multiple active tasks and conversations simultaneously.

## Problem Statement

### Current Architecture Limitations

1. **Component-Scoped State Loss**: When switching between tasks, all conversation history, draft messages, and form states are lost
2. **Single-Context Design**: Current routing assumes one active context at a time
3. **WebSocket Connection Limits**: No mechanism for maintaining multiple active conversations
4. **Poor Multi-Tasking Experience**: Users must constantly re-initialize contexts when switching tasks
5. **No Background Processing**: Agents can't continue work while user focuses on other tasks

### User Experience Pain Points

- Lost conversation context when switching between tasks
- Inability to monitor multiple agent conversations simultaneously
- No persistent draft states for task specifications or plans
- Lack of background activity awareness
- Constant re-loading and re-initialization

## Requirements

### Functional Requirements

1. **Tab-Based Navigation**: Browser-style tabs for quick switching between active contexts
2. **Persistent Conversation States**: Maintain conversation history, draft messages, and scroll positions across tab switches
3. **Background Agent Operations**: Continue agent conversations and operations when not actively viewing
4. **Multi-Context Awareness**: Global notifications and activity indicators across all active contexts
5. **State Preservation**: Maintain form states, edit modes, and unsaved changes across navigation
6. **Performance**: Instant tab switching without re-initialization delays

### Non-Functional Requirements

1. **Memory Efficiency**: Intelligent cleanup of inactive contexts
2. **Scalability**: Support for 10+ concurrent active contexts
3. **Reliability**: Robust error handling and state recovery
4. **Responsiveness**: Sub-100ms tab switching performance

## Proposed Architecture

### 1. Centralized State Management with Zustand

Replace component-scoped state with a series of centralized stores, each with a distinct responsibility. This follows a "separation of concerns" principle for cleaner, more maintainable state.

#### A. UIStore (Formerly NavigationStore)
This store is the single source of truth for the application's UI shell state, primarily managing the tabs.

```typescript
interface TabState {
  id: string; // A unique ID for the tab instance, e.g., a UUID
  type: 'task' | 'project' | 'codebase' | 'settings';
  entityId: string; // The ID of the entity being displayed, e.g., task ID
  title: string;
  hasUnsavedChanges: boolean;
  lastActivity: Date;
}

interface UIStore {
  tabs: TabState[];
  activeTabId: string | null;
  
  // Actions
  openTab: (tabData: Omit<TabState, 'id'>) => void;
  closeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  updateTab: (tabId: string, updates: Partial<TabState>) => void;
}
```

#### B. DataStore
This store acts as a normalized, client-side cache for all core business entities. It prevents data duplication and provides a single point for data fetching and updates.

```typescript
interface DataStore {
  projects: Map<string, Project>;
  tasks: Map<string, Task>;
  // Other entities like codebases would be added here
  
  // Loading and error states per entity
  loading: { projects: Set<string>; tasks: Set<string> };
  errors: { projects: Map<string, Error>; tasks: Map<string, Error> };
  
  // Actions with specific, type-safe methods
  fetchProject: (projectId: string) => Promise<void>;
  fetchTask: (taskId: string) => Promise<void>;
  updateTask: (taskId: string, updates: Partial<Task>) => Promise<void>;
}
```

#### C. ConversationStore
Manages the state of all agent conversations. Note that the WebSocket connection itself is *not* stored in the state to ensure the state is fully serializable.

```typescript
interface ConversationState {
  id: string;
  messages: ConversationMessage[];
  draftMessage: string;
  scrollPosition: number;
  isTyping: boolean;
  pendingToolApprovals: ToolApproval[];
  lastActivity: Date;
}

interface ConversationStore {
  conversations: Map<string, ConversationState>;
  
  // Actions
  addConversation: (conversationId: string) => void;
  addMessage: (conversationId: string, message: ConversationMessage) => void;
  setDraftMessage: (id: string, draft: string) => void;
  closeConversation: (id: string) => void;
}
```

#### D. Entity-Specific UI Stores (Example: TaskUIStore)
These stores handle the transient UI state for a specific view, such as edit modes or scroll positions, keeping the core `DataStore` clean.

```typescript
interface TaskUIState {
  editMode: 'specification' | 'plan' | null;
  unsavedChanges: Record<string, string>;
  scrollPosition: number;
}

interface TaskUIStore {
  tasksUIState: Map<string, TaskUIState>; // Keyed by task ID
  
  // Actions
  updateTaskUIState: (taskId: string, state: Partial<TaskUIState>) => void;
}
```

### 2. Singleton Services for Background Operations

Critical background operations will be handled by singleton services that are instantiated once and live outside the React/Zustand lifecycle. This is the correct place to manage non-serializable objects like WebSocket connections.

#### WebSocketManager (Service)
```typescript
// This is a singleton class, not a Zustand store
class WebSocketManager {
  connections: Map<string, WebSocket>;
  
  createConnection(conversationId: string): WebSocket {
    // ... implementation
    // On message, this manager calls an action on the ConversationStore
    // e.g., conversationStore.getState().addMessage(...)
  }
  
  cleanupConnection(conversationId: string): void {
    // ...
  }
  
  // Global message routing
  routeMessage(message: any): void {
    // ...
  }
}

export const webSocketManager = new WebSocketManager();
```

#### ActivityManager (Service)
```typescript
// This is a singleton class, not a Zustand store
class ActivityManager {
  activeOperations: Map<string, AgentOperation>;
  
  startBackgroundOperation(conversationId: string, operation: AgentOperation): void {
    // ...
  }
  
  // On completion, it can call actions on stores to update state
  // and trigger UI notifications.
  notifyCompletion(conversationId: string, result: any): void {
    // ...
  }
}

export const activityManager = new ActivityManager();
```

## User Interface Design Recommendations

### 1. Tab Bar Component

```typescript
interface TabBarProps {
  tabs: TabState[];
  activeTabId: string | null;
  onTabSwitch: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
  onNewTab: () => void;
}
```

**Design Features**:
- Browser-style tabs with close buttons
- Activity indicators (pulsing dot for active agent conversations)
- Unsaved changes indicators (modified dot)
- Drag-and-drop tab reordering
- Tab overflow handling with scrolling
- Context menu for tab management (close others, close all, etc.)

### 2. Global Activity Indicator

**Features**:
- Notification bell with count badge
- Background activity status (agents working, messages received)
- Quick access dropdown to jump to active conversations
- Progress indicators for long-running operations

### 3. Conversation Persistence UI

**Features**:
- Draft message preservation with visual indicators
- Conversation continuation banners ("Agent was working while you were away")
- Scroll position restoration
- Tool approval queues with global notifications

### 4. Multi-Context Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [Tab 1: Task ABC] [Tab 2: Project XYZ] [Tab 3: Settings] [+]│ ← Tab Bar
├─────────────────────────────────────────────────────────────┤
│                                                     🔔 (3)  │ ← Activity Indicator
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                   Active Tab Content                       │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │   Task Details  │  │      Agent Conversation        │   │
│  │                 │  │                                 │   │
│  │                 │  │  [Draft message preserved...]   │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 5. Background Activity Visualization

**In Non-Active Tabs**:
- Subtle animation on tab for agent activity
- Badge count for new messages
- Color coding for different activity types

**Global Notifications**:
- Toast notifications for completed operations
- Sound/visual alerts for tool approval requests
- Progress bars for long-running background tasks

## Implementation Strategy

The rollout will be phased to de-risk the migration and deliver value incrementally.

### Phase 1: Build the Foundation (Week 1-2)

1.  **Install and Configure Zustand**.
2.  **Implement the UI Shell**: Create the main layout components (`Sidebar`, `TabBar`, `MainContentArea`).
3.  **Create the `UIStore`**: Implement the core tab management logic (`openTab`, `closeTab`, `switchTab`).
4.  **Wire the UI Shell**: Connect the `TabBar` and `MainContentArea` to the `UIStore`. The UI should be able to add, switch, and close tabs.
5.  **Migrate a Simple View**: Migrate the **Settings page** to be the first component that opens in a tab. This validates the core tab mechanism with a low-risk component before tackling more complex views.

### Phase 2: Core Feature Migration (Week 3)

1.  **Create `DataStore` and `ConversationStore`**.
2.  **Implement `WebSocketManager`** as a singleton service.
3.  **Migrate `ConversationChat` and `TaskDetail`**: Refactor these components to fetch data from the `DataStore` and manage their state via the new stores.

### Phase 3: Background Processing & UX Polish (Week 4)

1.  **Implement `ActivityManager`** for tracking background agent work.
2.  **Build Global UI Elements**: Implement the global activity indicator and notification system.
3.  **Enhance Tab UX**: Add features like unsaved changes indicators and activity dots on the tabs.

### Phase 4: Optimization & Advanced Features (Week 5)

1.  **Performance Tuning**: Implement memory management and cleanup policies for inactive tabs.
2.  **URL Synchronization**: Connect the `UIStore` to the browser's URL to enable state restoration on refresh and back/forward navigation.
3.  **Advanced UX**: Implement drag-and-drop tab reordering, keyboard shortcuts, and context menus.

## Technical Considerations

### URL Synchronization
To ensure a seamless user experience, the application's state must be synchronized with the browser URL. This allows for state restoration on page refresh and enables the use of the browser's back/forward navigation buttons.
- **On Tab Switch**: A `useEffect` hook should listen for changes in the `UIStore`'s active tab and update the URL accordingly (e.g., `/app/task/TASK_ID`).
- **On Page Load**: The application should parse the URL on initial load to determine which tabs to open and which one should be active, dispatching the necessary actions to the `UIStore`.

### Memory Management

```typescript
// Cleanup policy for inactive tabs
interface CleanupPolicy {
  maxInactiveTabs: number // 10
  inactiveTimeoutMs: number // 30 minutes
  
  shouldCleanup: (tab: TabState) => boolean
  cleanup: (tabId: string) => void
}
```

### Error Handling

```typescript
interface ErrorRecovery {
  // WebSocket reconnection
  reconnectWebSocket: (conversationId: string) => void
  
  // State recovery from localStorage
  recoverState: () => void
  
  // Graceful degradation
  fallbackToSingleContext: () => void
}
```

### Performance Metrics

- **Tab Switch Time**: Target <100ms
- **Memory Usage**: <50MB per inactive tab
- **WebSocket Connections**: Max 10 concurrent
- **State Persistence**: Auto-save every 5 seconds

## Migration Considerations

### 1. Backward Compatibility

- Maintain existing URL patterns
- Gradual migration of components
- Fallback to current behavior if state management fails

### 2. Data Migration

- Preserve existing conversation history
- Convert current navigation state to tab format
- Maintain user preferences

### 3. Testing Strategy

- Unit tests for all new stores
- Integration tests for tab functionality
- Performance tests for multiple concurrent conversations
- User acceptance testing with power users

## Benefits

### For Users

1. **Improved Productivity**: No more lost context when switching tasks
2. **Better Multitasking**: Monitor multiple agent conversations simultaneously
3. **Reduced Cognitive Load**: Persistent state eliminates mental bookkeeping
4. **Faster Workflows**: Instant tab switching without re-initialization

### For Development

1. **Cleaner Architecture**: Centralized state management reduces component complexity
2. **Better Testing**: Isolated state stores are easier to test
3. **Enhanced Debugging**: Zustand DevTools provide excellent state inspection
4. **Future Extensibility**: Foundation for advanced features like workspace persistence

## Risks & Mitigation

### Risks

1. **Increased Complexity**: More moving parts in state management
2. **Memory Usage**: Multiple active contexts consume more memory
3. **WebSocket Limits**: Browser and server connection limits
4. **Migration Effort**: Significant refactoring required

### Mitigation

1. **Phased Implementation**: Gradual rollout with fallback options
2. **Intelligent Cleanup**: Automatic cleanup of inactive contexts
3. **Connection Pooling**: Efficient WebSocket management
4. **Comprehensive Testing**: Extensive testing before full deployment

## Success Metrics

### User Experience

- **Task Switch Time**: Reduce from 3-5 seconds to <100ms
- **Context Loss Events**: Eliminate 100% of conversation/form state loss
- **User Satisfaction**: Target 90%+ satisfaction with multitasking experience

### Technical Performance

- **Memory Usage**: <500MB total for 10 active tabs
- **CPU Usage**: <5% background processing overhead
- **Error Rate**: <1% WebSocket connection failures

## Conclusion

This architectural enhancement transforms DevBoard from a single-context application into a powerful multi-tasking developer command center. The browser tab-style interface with persistent state management addresses the core limitations that prevent efficient multi-task workflows.

The proposed Zustand-based architecture provides a solid foundation for advanced features while maintaining clean separation of concerns and excellent performance characteristics. The phased implementation approach ensures minimal disruption to current users while delivering immediate benefits to power users.

This change positions DevBoard as a true developer productivity platform capable of handling complex, multi-faceted development workflows that reflect the reality of modern software development.