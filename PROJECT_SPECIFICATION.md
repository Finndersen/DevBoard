# Project Specification: “DevBoard” (Version 3)

## Overview

DevBoard is a "developer command centre" application designed to be a comprehensive project management system and an AI-powered developer assistant. It runs locally on a user's machine, integrating with essential developer tools like Jira, Slack, Notion, and GitHub. By ingesting project context from these sources, DevBoard provides AI agents with the necessary information to assist in the planning, development, and delivery of tasks. Users can query for project status, manage tasks, and delegate implementation work to AI agents, all from a unified interface.

## Architecture & Tech Stack 🏛️

The system will be built on a local client-server architecture, ensuring access to local file systems for code repository management.

- **Deployment**: A container-based approach (e.g., Docker) is recommended, with local code repositories mounted as volumes to provide necessary file system access.

- **Backend**:
    - **Framework**: An asynchronous Python web server using FastAPI.
    - **Database**: SQLAlchemy as the ORM with a local SQLite database for initial phases, offering a clear migration path to PostgreSQL for future multi-user support.
    - **Real-time Communication**: WebSockets will be used for streaming agent progress and other real-time updates to the frontend.

- **Frontend**: A modern, web-based UI built with a framework like React.

- **Long-Running Tasks**:
    - **Challenge**: AI agent sessions are long-running and cannot be handled within a single synchronous API request.
    - **Proposed Solution**: A background task queue is required. A lightweight option like Dramatiq or FastAPI's built-in `BackgroundTasks` will be used for initial phases. The flow will be: API triggers a background job -> job streams updates via WebSockets -> UI displays real-time progress.

- **Multi-User Collaboration (Phase 3 Goal)**:
    - While the initial focus is a local-first single-user experience, the architecture should not preclude future collaboration. This would likely involve a shared backend and database where project and task data can be synced between users.

## Logical Objects & Entities 🧱

### 1. Project

A high-level representation of a large piece of work, analogous to a Jira Epic.

- **Project Details**: A central Markdown document containing the project overview, technical details, and status.
- **Context Providers**: Associated with various context sources like Slack channels, Notion pages, etc.

### 2. Task

A self-contained piece of work, often linked to a remote ticket in Jira or Asana.

- **Attributes**:
    - **Status**: A state machine tracking progress: `Pending` -> `Planning` -> `Awaiting Approval` -> `Implementing` -> `In Review` -> `Complete`.
    - **Description**: Detailed text description.
    - **Links**: References to the parent Project, remote task ID, and relevant GitHub repositories/PRs.
    - **AI State**: A `conversation_id` to resume agent sessions and a structured `Implementation Plan` artifact.

### 3. Context Provider

An interface for providing project and task context from external data sources.

- **Authentication**: Users will provide credentials (API keys, Personal Access Tokens) via the UI or environment variables. For Slack, the approach will aim to use `xoxc` and `xoxd` tokens to avoid workspace app installation.

- **API / Interface**:
    - `can_handle_uri(resource_uri)`: Determines if the provider can handle a given resource link.
    - `get_resource(resource_uri)`: Retrieves the full content of a small-scope resource (e.g., a single Slack message, a single Jira ticket).
    - `get_relevant_context(resource_uri, query)`: Retrieves context relevant to a specific query from a larger-scope resource (e.g., an entire Slack channel, a large document). 
      - This may be implemented using RAG, an agent, or by summarizing content with a high-context LLM.
      - For complex resource like a Slack channel, the context provider may need some kind of mechanism for tracking/storing message data and updating content incrementally over time instead of re-reading from scratch (need to store state in DB/file). Alternatively, it could rely on the provider's native search capabilities initially.
      - For something really massive and complex like a codebase, could maintain a high level project structure/architecture and have an AI agent interactively search using tools to get context
    - `get_mcp_tools()`: Returns a list of tools specific to this provider that can be passed to task Planning or Implementation agents to enable dynamic access to resources. Relevant tools from all context providers will be merged into a unified MCP server which will be configured for AI agents.
    - `update_content()`: Performs a refresh of any locally cached content for a large-scope resource.

### 4. Codebase

Represents a software codebase relevant to a project or task.
- A project could potentially have multiple relevant codebases, however for simplicity may be best to restrict each task to a single codebase
- Could theoretically support multiple codebases per Github repository (for monorepo setups), but maybe initially have a 1-to-1 mapping for simplicity
- **Architecture Document**: Each codebase can have an associated `ARCHITECTURE.md` file stored in its repository. This document is created and incrementally updated by an AI agent to prevent it from becoming stale.

## AI Agents & Orchestration 🤖

### 1. Project Q&A Agent

- **Function**: Answers questions about a project's status and context.
- **Context**:
    - Project overview document.
    - Full list of tasks and their statuses.
    - List of available large-scale context provider resources with associated descriptions
- **Tools/Capabilities**:
    - Conversational interaction.
    - `retrieve_relevant_project_context(query)`: A tool for on-demand, targeted context fetching from providers to manage context window limitations. OR, a `get_relevant_context(resource_uri, query)` tool to get context from specific large-scale resources.
    - Reading more details & state of individual tasks 
    - Updating project details/summary and status
- **Model**: Fast & cheap model with a large context window (e.g., Gemini Flash).
- **Implementation**:
  - Can run in app within API request using framework like PydanticAI

### 2. Context Provider Investigation Agent (Sub-Agent)

- **Function**: Acts as a sub-agent to implement the `get_relevant_context()` API for a context provider.
- **Context**:
    - A resource URI (e.g., Slack channel link, Notion page).
    - A specific user query.
- **Tools/Capabilities**:
  - Context-provider specific tools for exploring resources, e.g.:
      - Search a Slack channel.
      - Explore and query Notion documents.
      - Summarize large documents (e.g., PDF).
      - Explores a website/webpage following links
- **Model**: Fast & cheap model with a large context window (e.g., Gemini Flash).
- **Implementation**:
  - Can initially run in app within API request using framework like PydanticAI, may need to offlload to background task

### 3. Codebase Investigation Agent

- **Function**: Generates and maintains the `ARCHITECTURE.md` file for a codebase.
- **Context**:
    - The full codebase (explored agentially via tools)
- **Tools/Capabilities**:
    - Can be triggered to create the `ARCHITECTURE.md` document if it doesn't exist.
    - Can perform incremental updates to the document to reflect changes in the code.
- **Model**: Powerful reasoning model (e.g., Gemini Pro).
- **Implementation**:
  - Possibly wrapping a single-shot Gemini CLI agent run in a background task.


### 4. Task Investigation & Planning Agent

- **Function**: Produces detailed implementation plan with enough granularity to facilitate implementation without further research/investigation
- **Context**:
    - The task description.
    - Access to all configured context providers.
- **Tools/Capabilities**:
    - Queries context providers for relevant information.
    - Asks clarifying questions to the user.
    - Generates a detailed, structured Implementation Plan.
    - Allows the user to conversationally review, update, and approve the plan.
    - Runs as a background task.
- **Model**: Intelligent model with a large context window (e.g., Gemini Pro).
- **Implementation**:
  - Can  run in app as background task/job using framework like Pydantic AI

### 5. Task Implementation Agent

- **Function**: Executes the approved Implementation Plan.
- **Context**:
    - Task description
    - The approved Implementation Plan.
- **Tools/Capabilities**:
    - Performs code changes.
    - Runs tests.
    - Can be interactively guided by the user to iterate on the solution.
    - Can respond to PR review comments.
- **Model**: Agent with strong agential/tool-use capabilities (e.g., Claude via Claude Code SDK).
- **Implementation**:
    - Claude Code SDK running in a background task , resuming from previous conversation state if applicable.
    - Provided with a unified MCP server combining tools from all configured context providers.

### 6. Post-Task Review Agent

- **Function**: After a task is complete, this agent reviews the outcome to reconcile learnings and update project documentation.
- **Context**:
    - The completed task and its associated artifacts (e.g., PR, code changes).
- **Tools/Capabilities**:
    - Updates the main `Project Details` document.
    - Triggers the `Codebase Investigation Agent` to update the `ARCHITECTURE.md` file.
- **Model**: Reasoning model (e.g., Gemini Pro).
- **Implementation**:
    - Can run in app within API request using framework like PydanticAI or as a background task if it needs to do more extensive work.

## Features & Phased Rollout 🚀

### Global

- **Phase 1**: UI for managing user-level agent configurations (e.g., custom slash commands, `CLAUDE.md` prompt guidance, MCP server configuration).
- **Phase 2**: A unified MCP (tool) server that provides integrations from all configured context providers to the Implementation Agent.

### Context Providers

- **Phase 1**: Initial integrations for Slack, GitHub, Jira, Notion, and local documents (e.g., PDF). Large-scale resources will rely on the provider's native search capabilities.
- **Phase 2**: More sophisticated handling of large-scale resources, such as generating local summaries or indexes of Slack conversations for faster retrieval.

### Project

- **Phase 1**: A project view with the editable Project Details document. A project-level chat interface for the Q&A agent.
- **Phase 2**: The ability to conversationally provide project status updates, which an agent then uses to update the formal Project Details document.

### Task

- **Phase 1**:
    - Create tasks manually or by linking a Jira/Asana ID.
    - Trigger the investigation/planning phase to generate an Implementation Plan.
    - Manually or conversationally edit and approve the plan.
    - Trigger the Implementation Agent.
    - Basic visualization of agent progress (e.g., streaming logs).
    - Trigger an agent to create a GitHub PR after implementation.
- **Phase 2**:
    - Detailed visualization of implementation agent activity (sub-tasks, tool use).
    - Continue conversation with the implementation agent during the PR lifecycle to respond to feedback.
    - Trigger the Post-Task Review Agent upon task completion.

### CLI

- **Phase 2**: A CLI command for starting an interactive agent session for a specific task, automatically loading its context and conversation history.

### Multi-User Collaboration

- **Phase 3**: A mechanism to sync Project and Task data between multiple users collaborating on the same project.
