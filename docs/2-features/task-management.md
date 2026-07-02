# Task Management

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > Task Management

## Overview

DevBoard provides **AI-assisted task development** with clear lifecycle management. Tasks represent discrete units of work that progress through well-defined states, with different AI agent roles supporting each phase.

## Task Lifecycle

Tasks progress through defined states, each with specific purposes and agent support:

### Planning → Implementing → [PR Open →] Merged → Complete

**State Descriptions**:

- **Planning**: Collaborative specification development and implementation planning with AI
- **Implementing**: Execute development work with AI assistance (TaskImplementationRole agent)
- **PR Open** *(optional)*: GitHub PR created for the task; displays PR status and review comments inline
- **Merged**: Branch merged; post-merge housekeeping with TaskFinalisationRole (project spec updates, follow-up tasks)
- **Complete**: Task finished and delivered

## Core Workflow

### 1. Task Definition

Create tasks manually or by linking external tickets:

- **Manual Creation**: Enter task name, description, and project association
- **External Linking**: Link to Jira tickets, GitHub issues, or other work items
- **Project Association**: Every task belongs to a project
- **Initial State**: Tasks start in Planning state

### 2. Interactive Specification

Collaboratively develop detailed task requirements with AI:

- **Planning Agent**: TaskPlanningRole guides requirement gathering and planning
- **Structured Document**: Task specification follows consistent template
  - Objective: Clear, specific goal statement
  - Context & Background: Current state and problem description
  - Requirements: Functional and non-functional requirements
  - Acceptance Criteria: Testable success criteria
  - Resources & References: Related documentation
  - Constraints & Assumptions: Technical and timeline constraints
- **Conversational Development**: Refine specification through natural language
- **Approval Workflow**: Review and approve all document edits

**Example Interaction**:
```
User: "This task should support OAuth2 authentication"
Agent: [Proposes edit to Requirements section adding OAuth2 details]
User: [Reviews and approves edit]
```

### 3. Implementation Planning

Create technical execution plans through agent conversation:

- **Planning Agent**: TaskPlanningRole creates implementation strategies
- **Technical Focus**: Architecture decisions, component changes, testing approach
- **Structured Plan**: Implementation plan consists of discrete steps, each executable by a sub-agent
  - Overview: High-level approach and strategy
  - Steps: Ordered list with types (`code_change`, `documentation`, `validation`, `code_review`), dependencies, and detailed instructions
  - Status tracking: Each step progresses through `pending` → `running` → `complete`/`failed`/`skipped`
  - Dependency graph: Steps declare dependencies to control execution order and enable parallelism
- **Code Analysis**: Agent has access to codebase for informed planning
- **Context-Aware**: Agent understands task specification and project context

### 4. Execution Support

Delegate implementation work to specialized agents:

- **Implementation Agent**: TaskImplementationRole assists with coding
- **Tool Access**: Agent can search codebase, read files, execute commands
- **Guided Development**: Agent follows implementation plan
- **Progress Tracking**: Monitor implementation progress through file change diffs
- **Quality Focus**: Testing and code quality throughout implementation

**File Change Viewer**: Track implementation progress in real-time:
- **Changes Tab**: View all uncommitted file modifications directly in the task UI
- **Syntax Highlighted Diffs**: Color-coded changes with language-specific highlighting
- **Collapsible Files**: Each modified file shown collapsed by default for performance
- **Line Numbers**: Precise line tracking showing old and new line numbers
- **Statistics**: See additions/deletions per file and total changes
- **Refresh Capability**: Manually refresh to see latest changes with timestamps

### 5. PR Review & Completion

When a GitHub PR is created for the task:

- **PR Status Display**: GitHub PR status button in task header shows CI check status and links to the PR
- **Inline PR Comments**: GitHub review comments are displayed inline in the File Changes diff view at the corresponding file and line
- **Send to Agent**: Each PR review comment has a "Send to agent" button to forward it to the implementation agent for addressing
- **Completion**: Merge the PR and mark the task complete

## Task Behavior

### State-Driven Progression

Clear workflow from definition through completion:

- **Explicit Transitions**: User triggers state transitions
- **Agent Roles**: Different agents available in each state
- **Guided Workflow**: System suggests next steps
- **Flexible Control**: Can skip or revisit states as needed

### Collaborative Planning

Develop specifications and plans through AI conversation:

- **Natural Language**: Describe requirements in plain English
- **Iterative Refinement**: Improve documents over multiple interactions
- **Approval Required**: User reviews all proposed changes
- **Conflict Prevention**: Document versioning prevents concurrent edit issues

### Context-Aware

Access to project context plus task-specific resources:

- **Project Context**: Specification, goals, linked resources
- **Task Resources**: Task-specific external links
- **Codebase Access**: Agents can analyze relevant code
- **Conversation History**: Previous discussions inform agent responses

### External Integration

Link to Jira tickets, GitHub issues, and other external work items:

- **URI-Based Links**: Add external resource URLs
- **Bidirectional**: View external items from DevBoard, link back to DevBoard from external tools
- **Context Provider Integration**: External resources provide context to agents
- **Multiple Links**: Tasks can link to multiple external items

### Custom Fields

Attach metadata to tasks using globally-defined custom fields:

- **Field Types**: Text (free-form), Boolean (toggle), Enum (dropdown)
- **Field Management**: Define task-scoped fields in Settings → Custom Fields → Task Fields tab
- **Inline Editing**: View and edit field values via the collapsible panel in task detail (TagIcon button in the header)
- **Mandatory Enforcement**: Mandatory fields are required at task creation time

## Document-Centric

Maintain living specification and implementation plan documents:

- **Structured Templates**: Consistent document format across tasks
- **Evolutionary**: Documents improve through conversation
- **Version Tracked**: Changes tracked with conflict detection
- **Human Readable**: Markdown format, version-control friendly

## Use Cases

### New Feature Development
1. Create task in project for new feature
2. Converse with specification agent to develop detailed requirements
3. Create implementation plan with the planning agent
4. Transition to implementing and work with implementation agent
5. Complete implementation, create PR, address review feedback, and merge

### Bug Fix Task
1. Create task linked to GitHub issue
2. Develop specification describing bug and expected behavior
3. Create implementation plan identifying root cause and fix approach
4. Implement fix with agent assistance
5. Complete and update external issue

### Investigation Task
1. Create task for technical investigation
2. Use specification agent to define investigation scope and questions
3. Use planning agent to outline investigation approach
4. Use implementation agent to execute investigation and document findings
5. Complete with documented results

## Agent Roles by State

- **Planning**: TaskPlanningRole guides specification and implementation planning
- **Implementing**: TaskImplementationRole assists with coding
- **PR Open**: TaskPRReviewRole handles PR reviews, CI status detection, and inline comments
- **Merged**: TaskFinalisationRole handles post-merge housekeeping (project spec updates, follow-up tasks, archiving)
- **Complete**: No agent (task finished)