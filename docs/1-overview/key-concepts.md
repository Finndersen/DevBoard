# Key Concepts

**Navigation**: [Documentation Home](../INDEX.md) > [Overview](./INDEX.md) > Key Concepts

## Core Domain Concepts

This document defines the fundamental abstractions and domain entities that DevBoard uses to organize development work and context. Understanding these concepts is essential for using and developing DevBoard.

## 1. Project

A **high-level container** representing a significant development initiative, analogous to a Jira Epic or GitHub milestone.

**Purpose**: Organize related work, maintain project-level documentation, and provide AI agents with comprehensive project context.

**Key Characteristics**:
- **Project Specification**: Central living document containing project overview, goals, and status
- **Context Sources**: Links to external resources (Slack channels, Notion pages, GitHub repos, Jira boards)
- **Task Organization**: Contains and organizes related development tasks
- **AI Interaction**: Supports conversational Q&A about project status and context

**Lifecycle**: Projects are long-lived containers that persist throughout initiative development and beyond.

## 2. Task

A **discrete unit of work** representing a specific development deliverable, often corresponding to a Jira ticket or GitHub issue.

**Purpose**: Break down projects into manageable work items with clear specifications and implementation plans.

**Lifecycle States**:
- **Defining** → **Designing** → **Planning** → **Implementing** → **In Review** → **Complete**

**Key Characteristics**:
- **Task Specification**: Detailed requirements document developed collaboratively with AI
- **Implementation Plan**: Technical execution plan created through agent interaction
- **External Links**: References to Jira tickets, GitHub PRs, and other relevant resources
- **Context Awareness**: Access to project context plus task-specific resources

**State Transitions**: Tasks progress through well-defined states with different agent roles supporting each phase.

## 3. Codebase

A **local or remote code repository** that represents a software system relevant to projects and tasks.

**Purpose**: Provide AI agents with access to code structure, architecture, and development patterns.

**Key Characteristics**:
- **Architecture Documentation**: Living `ARCHITECTURE.md` files maintained by AI agents
- **Local Integration**: Direct access to local file systems for code analysis
- **Multi-Project Sharing**: Same codebase can be referenced by multiple projects
- **Version Awareness**: Understanding of Git history and branching strategies

**Integration**: Codebases are registered in DevBoard and linked to projects/tasks for context.

## 4. Context Provider

An **intelligent abstraction** that gathers and processes information from external sources to provide relevant context to AI agents.

**Purpose**: Transform raw data from external tools into actionable context for project and task management.

**Provider Types**:
- **GitHub**: Pull requests, issues, commits, repository structure
- **Jira**: Tickets, projects, workflows, comments
- **Slack**: Conversations, channels, thread discussions
- **Codebase**: Local file analysis, architecture documentation
- **Web Pages**: Documentation sites, technical resources

**Context Strategies**:
- **Eager Loading**: Small resources loaded immediately into agent context
- **On-Demand**: Large resources queried specifically when needed

## 5. Integration

A **technical connector** that provides authenticated access to external service APIs.

**Purpose**: Handle the low-level communication with external tools, managing authentication, rate limits, and error conditions.

**Responsibilities**:
- **Authentication**: Secure credential management
- **API Communication**: Direct service interaction
- **Error Handling**: Graceful failure management
- **Rate Limiting**: Respect service constraints

**Distinction from Context Providers**: Integrations handle API communication; context providers process and normalize data.

## 6. External Resource

A **reference to external content** that can be shared across multiple projects and tasks.

**Purpose**: Avoid duplication while maintaining links to relevant external context sources.

**Characteristics**:
- **URI-Based**: Unique identifiers for external content (URLs, URIs)
- **Shareable**: Same resource can be linked to multiple projects/tasks
- **Describable**: Human or AI-generated descriptions for context

**Examples**: GitHub repository URLs, Jira ticket links, Slack thread URLs, documentation pages.

## Relationships Between Concepts

- **Projects contain Tasks**: One-to-many relationship for organizing work
- **Projects and Tasks link to External Resources**: Many-to-many relationship for context
- **Projects and Tasks reference Codebases**: Many-to-many relationship for code context
- **Context Providers use Integrations**: Providers depend on integrations for API access
- **External Resources are accessed via Context Providers**: Providers fetch and process resource content
