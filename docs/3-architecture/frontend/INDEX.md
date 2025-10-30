# Frontend Architecture

**Navigation**: [Documentation Home](../../INDEX.md) > [Architecture](../INDEX.md) > Frontend

## Purpose

This section details the frontend implementation built with React, TypeScript, and modern web technologies. Learn about component organization, state management, real-time updates, and design patterns.

## Technology Stack

- **Framework**: React 19+ with TypeScript
- **Build System**: Vite with HMR
- **State Management**: Zustand with Immer middleware
- **Styling**: Tailwind CSS with custom design system
- **Routing**: React Router v7+
- **Testing**: Vitest + React Testing Library + MSW
- **Real-time**: WebSocket integration for live updates

## Documents

### [Directory Structure](./directory-structure.md)
Complete frontend code organization including components, views, hooks, stores, services, and utilities.

### [Components](./components.md)
UI component library, layout system, chat components, approval system, document viewers, configuration UI, and notification system.

**Location**: `frontend/src/components/`

### [Patterns](./patterns.md)
React development patterns including component architecture, custom hooks, design system approach, state management, type-safe API integration, and theme support.

### [Streaming](./streaming.md)
Real-time updates implementation including WebSocket integration, NDJSON parsing, event-based chat, and streaming conversation architecture.

## Related Sections

- **[System Design](../system-design.md)**: Overall architecture context
- **[Backend API Reference](../backend/api-reference.md)**: API endpoints consumed by frontend
- **[AI Agents - Conversation System](../../4-ai-agents/conversation-system.md)**: Event-based communication
- **[Development - Getting Started](../../6-development/getting-started.md)**: Setup instructions
