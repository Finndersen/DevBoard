# Backend Architecture

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > Backend

## Purpose

This section details the backend implementation built with Python, FastAPI, and SQLAlchemy. Learn about code organization, key components, development patterns, and API endpoints.

## Technology Stack

- **Framework**: FastAPI with async Python 3.12+
- **ORM**: SQLAlchemy 2.0 with `Mapped[]` annotations
- **Migrations**: Alembic for database versioning
- **Validation**: Pydantic V2 for request/response schemas
- **AI Framework**: PydanticAI for agent conversations
- **Testing**: Pytest with async support
- **Observability**: Pydantic Logfire

## Documents

### [Directory Structure](./directory-structure.md)
Complete backend code organization including API routers, services, repositories, database models, agents, context providers, and integrations.

### [Components](./components.md)
Key classes and services including routers (API endpoints), services (business logic), repositories (data access), agents (AI interactions), context providers (external context), and integrations (API clients).

**Location**: `backend/devboard/`

### [Patterns](./patterns.md)
Development patterns and conventions including dependency injection, type hinting, error handling, SQLAlchemy 2.0 usage, and async patterns.

### [API Reference](./api-reference.md)
Complete endpoint documentation for all API routes including Projects, Tasks, Conversations, Codebases, Configurations, and Settings.

## Related Sections

- **[System Design](../system-design.md)**: Overall architecture context
- **[Database Schema](../database-schema.md)**: Data model details
- **[Frontend](../frontend/INDEX.md)**: Client-side implementation
- **[Development - Getting Started](../../6-development/getting-started.md)**: Setup instructions
