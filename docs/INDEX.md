# DevBoard Documentation

## What is DevBoard?

DevBoard is a **developer command center** application that serves as a comprehensive project management system and AI-powered developer assistant. It provides a unified platform for managing projects and tasks while intelligently orchestrating context from multiple sources (GitHub, Jira, Slack, local codebases) to enable AI-driven assistance throughout the development lifecycle.

The system runs locally on your machine while integrating with cloud-based developer tools, combining the benefits of local-first architecture with the power of distributed development ecosystems. DevBoard uses sophisticated AI agents that understand your complete project context to help with specification writing, implementation planning, code analysis, and development execution.

## Documentation Structure

### [1. Overview](./1-overview/INDEX.md)
High-level understanding of what DevBoard is, its vision, core concepts, and user workflows. Start here to understand the "why" and "what" of the system.

**Key topics:**
- Vision and strategic objectives behind DevBoard
- Core domain concepts: Projects, Tasks, Codebases, Context Providers, External Resources
- User workflows and conversational interface philosophy

### [2. Features](./2-features/INDEX.md)
Comprehensive catalog of DevBoard's capabilities including project management, task workflows, codebase documentation, configuration system, and document collaboration. Learn what users can accomplish with DevBoard.

**Key topics:**
- Project and task management with AI assistance
- AI-assisted task lifecycle: specification → planning → implementation
- Codebase documentation maintenance
- Configuration system for integrations and agent settings

### [3. Architecture](./3-architecture/INDEX.md)
Technical system design, database schema, API structure, and implementation details for both backend (Python/FastAPI) and frontend (React/TypeScript). Understand how DevBoard is built.

**Key topics:**
- Local-first client-server architecture with FastAPI and React
- Database schema: SQLAlchemy 2.0 models, entities and relationships
- API design patterns and endpoint structure
- Backend components: routers, services, repositories, agents
- Frontend patterns: React components, Zustand state management, WebSocket streaming

### [4. AI Agents](./4-ai-agents/INDEX.md)
Deep dive into the AI agent system including architecture, conversation patterns, tool capabilities, Claude Code integration, and configuration. Learn how intelligent agents power DevBoard's capabilities.

**Key topics:**
- Role-based agent architecture: Roles define behavior, Engines handle execution
- Agent roles: ProjectQA, TaskSpecification, TaskPlanning, TaskImplementation
- Event-driven conversation system with structured events
- Tool system with approval workflows and virtual tool calling
- Context assembly from multiple sources

### [5. Integrations](./5-integrations/INDEX.md)
External service integrations (GitHub, Jira, Slack), context provider architecture, and LLM provider support. Understand how DevBoard connects to your development ecosystem.

**Key topics:**
- External services: GitHub, Jira, Slack integrations
- Context provider architecture with URI-based resource system
- LLM providers: OpenAI, Anthropic (Claude), Google (Gemini)
- Graceful degradation and error resilience patterns

### [6. Development](./6-development/INDEX.md)
Getting started guide, testing strategies, deployment instructions, and contribution guidelines. Everything needed to develop, test, and deploy DevBoard.

**Key topics:**
- Prerequisites: Docker, Python 3.12+, Node.js, uv, npm
- Setup and running locally (backend with FastAPI, frontend with Vite)
- Testing strategies: pytest (backend), vitest (frontend)
- Docker deployment and production configuration


## Additional Resources

- **Source Code**: Explore the codebase in `backend/` (Python) and `frontend/` (TypeScript/React)
- **Tests**: See `backend/tests/` and `frontend/src/**/__tests__/` for test suites
