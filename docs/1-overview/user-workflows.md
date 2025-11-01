# User Workflows

**Navigation**: [Documentation Home](../INDEX.md) > [Overview](./INDEX.md) > User Workflows

## Workflow Philosophy

DevBoard is designed around **conversational workflows** where users collaborate with AI agents to accomplish development tasks. The interface emphasizes **document-centric collaboration** where specifications, plans, and other artifacts are developed through interactive conversation.

## Core User Journeys

### Project Setup & Management

1. **Project Creation**: Define project goals, scope, and connect external resources
2. **Context Assembly**: Link relevant Slack channels, Jira boards, GitHub repositories
3. **Living Documentation**: Maintain project specifications through AI collaboration
4. **Progress Monitoring**: Track task completion and project health

**Key Activities**:
- Create new project with name and description
- Link external resources (Slack channels, Jira boards, GitHub repos)
- Ask project questions via conversational AI
- Edit project specifications collaboratively with agents
- Monitor task status and project progress

### Task Development Lifecycle

1. **Task Definition**: Create tasks from external tickets or manual entry
2. **Specification Development**: Collaboratively develop detailed requirements
3. **Implementation Planning**: Create technical execution strategies
4. **Execution & Monitoring**: Delegate work to agents and track progress
5. **Integration & Review**: Complete tasks and update project documentation

**Key Activities**:
- Create task linked to project
- Converse with specification agent to develop requirements
- Transition task through states (Defining → Planning → Implementing)
- Review and approve agent-proposed document edits
- Link external resources (Jira tickets, GitHub PRs)
- Complete task and update project status

## Interface Design Principles

### Document-Centric Interaction

DevBoard treats documents as first-class citizens in the development workflow:

- **Living Documents**: All specifications and plans evolve through conversation
- **Structured Editing**: Agents propose specific document changes for user approval
- **Version Awareness**: Changes tracked with conflict detection
- **Context Integration**: Documents reference and incorporate external context

**Example**: Task specifications start as templates and evolve through agent collaboration, with each change proposed and approved individually.

### Conversational Collaboration

Natural language interaction with context-aware AI agents:

- **Natural Language**: Interact with agents using natural conversation
- **Context Awareness**: Agents understand full project and task context
- **Persistent Sessions**: Conversations continue across sessions
- **Progressive Refinement**: Documents improve through iterative collaboration

**Example**: "Add acceptance criteria for user authentication" → Agent proposes specific edits → User reviews and approves.

### State-Driven Navigation

Clear progression through well-defined workflow states:

- **Clear Progression**: Visual indication of project and task states
- **Contextual Actions**: Available actions depend on current state
- **Guided Workflows**: System guides users through appropriate next steps
- **Flexible Control**: Users can override system suggestions when needed

**Example**: Task in "Planning" state shows planning agent; transitioning to "Implementing" state shows implementation agent.

## Frontend Architecture & Multi-Tasking Interface

### Browser-Style Tab System

DevBoard employs a **multi-task tab architecture** enabling users to work with multiple projects, tasks, and entities simultaneously without losing context.

**Key Features**:
- **Tab-Based Navigation**: Browser-style tabs for projects, tasks, codebases, and settings
- **Persistent State**: Tab state and conversation history preserved across sessions
- **Activity Indicators**: Visual feedback for agent activity, new messages, and required actions
- **Unsaved Changes**: Clear indication of pending edits with tab-level tracking
- **Deep Linking**: Shareable URLs for specific entities and conversations
- **Keyboard Navigation**: Full keyboard shortcuts for power users (Cmd+1-9, Cmd+W, Cmd+T)

**State Management**:
- **Zustand Stores**: Lightweight state management with Immer for immutable updates
- **Normalized Caching**: Efficient entity storage to prevent data duplication
- **LocalStorage Persistence**: Critical UI state survives page refreshes
- **Singleton Services**: WebSocket manager and activity tracking run in background

### Unified Home Dashboard

The **Home view** serves as the central command center displaying all projects and codebases in a unified interface.

**Dashboard Sections**:
- **Projects Section**: Grid view of all projects with create functionality
  - Click to open project in dedicated tab
  - Shows project name, description, and creation date
  - Empty state with guided creation flow
  - Real-time count of total projects

- **Codebases Section**: Grid view of all codebases with management tools
  - Click to open codebase details in dedicated tab
  - Inline delete functionality with confirmation
  - Shows codebase name, description, and local path
  - Create new codebase with path validation
  - Real-time count of total codebases

**Design Principles**:
- **Everything at a Glance**: No need to navigate between separate list views
- **Quick Actions**: Create new entities directly from dashboard
- **Visual Hierarchy**: Clear section separation with iconography
- **Responsive Layout**: Grid adapts to screen size (1/2/3 columns)
- **Loading States**: Unified loading indicator for all sections

### Entity-Specific Views

**Project Detail View**: Comprehensive project management interface
- Tabbed interface for Board, Editor (specification), and Settings
- Task list with status filtering and quick creation
- Agent conversation panel with project context displaying event timeline
- External resource links and integration status

**Task Detail View**: Focused task development interface
- Specification and implementation plan editors
- State-driven agent panels (different agents per task state)
- External link management (Jira, GitHub, etc.)
- Real-time collaboration with AI agents showing complete event streams

**Agent Conversation Display**: Streaming event-based chat interface
- **Text Messages**: Standard chat bubbles for user/agent messages with timestamps
- **Tool Call Panels**: Expandable cards showing tool invocations with visual status indicators
  - Collapsed state displays tool name, status icon, and call timestamp in header
  - Expanded state reveals tool arguments (JSON format) and execution results
  - Status indicators: Animated spinner for running tools, checkmark for success, X icon for errors
  - Timestamps: Call time in header, "Returned:" timestamp for results
- **Event Timeline**: Chronological display of all conversation events interleaved naturally
- **Real-Time Streaming**: Events appear progressively as they're generated by the agent
  - User message displays immediately when sent
  - Agent events stream in one-by-one as they occur
  - No waiting for agent completion - see progress as it happens
  - NDJSON streaming protocol for efficient incremental updates

**Settings View**: Unified configuration management
- Integration setup and testing
- Agent configuration per role with engine and model selection
- Codebase registration and management
- Environment variable display and override

### Background Operations & Notifications

**WebSocket Management**: Singleton service managing multiple concurrent agent conversations
- Connection pooling (max 10 concurrent)
- Automatic reconnection with exponential backoff
- Message routing to conversation stores
- Connection status indicators

**Activity Tracking**: Real-time monitoring of background agent operations
- Tab activity badges (●, ⚡, 🔴)
- Unified notification panel for all events
- Tool approval workflow integration
- Navigation to relevant entity from notifications

**Notification Types**:
- **Tool Approvals**: High-priority agent action requests
- **Agent Complete**: Task/operation completion alerts
- **Agent Blocked**: Error or blocking conditions
- **New Messages**: Conversation updates while viewing other tabs
