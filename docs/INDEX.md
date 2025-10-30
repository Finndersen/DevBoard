# DevBoard Documentation

## What is DevBoard?

DevBoard is a **developer command center** application that serves as a comprehensive project management system and AI-powered developer assistant. It provides a unified platform for managing projects and tasks while intelligently orchestrating context from multiple sources (GitHub, Jira, Slack, local codebases) to enable AI-driven assistance throughout the development lifecycle.

The system runs locally on your machine while integrating with cloud-based developer tools, combining the benefits of local-first architecture with the power of distributed development ecosystems. DevBoard uses sophisticated AI agents that understand your complete project context to help with specification writing, implementation planning, code analysis, and development execution.

## Navigation Guide

Choose your path based on your role and objectives:

### 🎯 For Product Managers & Project Leads
Start with **[1. Overview](./1-overview/INDEX.md)** to understand DevBoard's vision, goals, and core concepts, then explore **[2. Features](./2-features/INDEX.md)** to learn about project management, task workflows, and configuration capabilities.

### 👨‍💻 For New Developers
Begin with **[6. Development](./6-development/INDEX.md)** for setup instructions, then review **[3. Architecture](./3-architecture/INDEX.md)** to understand the system design, and finally dive into **[4. AI Agents](./4-ai-agents/INDEX.md)** to learn how the agent system works.

### 🤖 For AI Agents Researching the Codebase
Load **[3. Architecture](./3-architecture/INDEX.md)** for technical implementation details, **[4. AI Agents](./4-ai-agents/INDEX.md)** for agent system specifics, and **[1. Overview - Key Concepts](./1-overview/key-concepts.md)** for domain model understanding.

### 🔧 For Contributors
Start with **[6. Development - Contributing](./6-development/contributing.md)** for development workflow, then review **[MAINTENANCE_GUIDE.md](./MAINTENANCE_GUIDE.md)** for documentation maintenance guidelines.

## Documentation Structure

### [1. Overview](./1-overview/INDEX.md)
High-level understanding of what DevBoard is, its vision, core concepts, and user workflows. Start here to understand the "why" and "what" of the system.

### [2. Features](./2-features/INDEX.md)
Comprehensive catalog of DevBoard's capabilities including project management, task workflows, codebase documentation, configuration system, and document collaboration. Learn what users can accomplish with DevBoard.

### [3. Architecture](./3-architecture/INDEX.md)
Technical system design, database schema, API structure, and implementation details for both backend (Python/FastAPI) and frontend (React/TypeScript). Understand how DevBoard is built.

### [4. AI Agents](./4-ai-agents/INDEX.md)
Deep dive into the AI agent system including architecture, conversation patterns, tool capabilities, Claude Code integration, and configuration. Learn how intelligent agents power DevBoard's capabilities.

### [5. Integrations](./5-integrations/INDEX.md)
External service integrations (GitHub, Jira, Slack), context provider architecture, and LLM provider support. Understand how DevBoard connects to your development ecosystem.

### [6. Development](./6-development/INDEX.md)
Getting started guide, testing strategies, deployment instructions, and contribution guidelines. Everything needed to develop, test, and deploy DevBoard.

## Maintenance

This documentation is a living system that evolves with the codebase. See **[MAINTENANCE_GUIDE.md](./MAINTENANCE_GUIDE.md)** for comprehensive guidelines on creating and updating documentation files.

## Additional Resources

- **Root Directory Files**: [PROJECT_SPECIFICATION.md](../PROJECT_SPECIFICATION.md) and [ARCHITECTURE.md](../ARCHITECTURE.md) contain the original comprehensive documentation (retained for reference)
- **Source Code**: Explore the codebase in `backend/` (Python) and `frontend/` (TypeScript/React)
- **Tests**: See `backend/tests/` and `frontend/src/**/__tests__/` for test suites
