# Architecture

**Navigation**: [Documentation Home](../INDEX.md) > Architecture

## Purpose

This section describes the technical implementation of DevBoard, including system design, database schema, API structure, and code organization for both backend and frontend. These documents focus on "how" the system is built.

## Overview

DevBoard implements a **local-first client-server architecture** with a monorepo structure:

- **Backend**: FastAPI (Python 3.12+) with async support, SQLAlchemy 2.0 ORM, PydanticAI agent framework
- **Frontend**: React 19+ with TypeScript, Vite build system, Zustand state management
- **Database**: SQLite (development) with PostgreSQL migration path
- **AI Integration**: PydanticAI framework with multi-provider LLM support (OpenAI, Anthropic, Google)
- **Observability**: Pydantic Logfire for monitoring and instrumentation
- **Deployment**: Docker containers with volume mounting for local repositories

## Core Principles

- **Local-First**: Primary data and processing on user's machine
- **Context-Aware**: Intelligent gathering and assembly of project context
- **Agent-Driven**: AI agents handle complex workflows with human oversight
- **Extensible**: Plugin architecture for integrations and context providers
- **Type-Safe**: Comprehensive TypeScript (frontend) and type hints (backend)

## Top-Level Documents

### [System Design](./system-design.md)
High-level architecture overview, deployment model, technology stack summary, and design principles. Start here for architectural understanding.

### [Database Schema](./database-schema.md)
Complete data model including entities, relationships, SQLAlchemy implementation, and persistence patterns. Essential for understanding data structures.

### [API Design](./api-design.md)
RESTful API principles, endpoint patterns, request/response formats, and general API architecture. Learn the API conventions used throughout DevBoard.

### [Worktree Management](./worktree-management.md)
Git worktree pool per codebase, slot allocation and locking, sticky reuse across agent sessions, and sandbox isolation.

## Backend Implementation

### [Backend Directory Structure](./backend/directory-structure.md)
Code organization, layered architecture, and module responsibilities.

### [Backend Components](./backend/components.md)
Key classes and services including routers, services, repositories, agents, context providers, and integrations.

### [Backend Patterns](./backend/patterns.md)
Development patterns including dependency injection, type hinting, error handling, and SQLAlchemy usage.

### [Backend API Reference](./backend/api-reference.md)
Complete API endpoint documentation with request/response schemas for all routes.

See [Backend INDEX](./backend/INDEX.md) for backend-specific navigation.

## Frontend Implementation

### [Frontend Directory Structure](./frontend/directory-structure.md)
Code organization, component hierarchy, and module responsibilities.

### [Frontend Components](./frontend/components.md)
UI library, layout system, chat components, approval system, hooks, and stores.

### [Frontend Patterns](./frontend/patterns.md)
React patterns, component architecture, custom hooks, state management, and design system.

### [Frontend Streaming](./frontend/streaming.md)
Real-time updates, WebSocket integration, NDJSON parsing, and event-based chat.

See [Frontend INDEX](./frontend/INDEX.md) for frontend-specific navigation.

## Related Sections

- **[Overview - Key Concepts](../1-overview/key-concepts.md)**: Domain model that architecture implements
- **[AI Agents](../4-ai-agents/INDEX.md)**: Agent system implementation details
- **[Development](../6-development/INDEX.md)**: Setup, testing, and deployment instructions
