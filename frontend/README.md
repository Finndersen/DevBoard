# DevBoard Frontend

React frontend for the DevBoard developer command centre application. Built with React 18, TypeScript, and Vite for a modern development experience.

## Overview

DevBoard is an AI-powered developer command centre that provides project management, task tracking, and intelligent Q&A agents. The frontend offers a clean, responsive interface with dark mode support for managing development workflows.

## Features

- **Project Management**: Create, view, and organize development projects
- **Task Management**: Kanban-style board with drag-and-drop task organization
- **AI Chat Agents**: Integrated Q&A agents for project-specific assistance
- **Settings Management**: Configure integrations and AI providers
- **Responsive Design**: Mobile-friendly interface with dark/light mode
- **Type Safety**: Full TypeScript implementation with strict type checking

## Tech Stack

- **React 18** - Modern React with hooks and functional components
- **TypeScript** - Full type safety and better developer experience
- **Vite** - Fast build tool with hot module replacement
- **Tailwind CSS** - Utility-first CSS framework with dark mode
- **React Router** - Client-side routing and navigation
- **Heroicons** - Beautiful SVG icons

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── Chat.tsx        # Chat interface for AI agents
│   └── Layout.tsx      # Main application layout
├── views/              # Page-level components
│   ├── ProjectDashboard.tsx    # Project overview and grid
│   ├── ProjectDetail.tsx       # Individual project view
│   ├── TaskDetail.tsx          # Task details and editing
│   └── Settings.tsx            # Application settings
├── lib/                # Utilities and services
│   └── api.ts          # Centralized API client
├── App.tsx             # Main application component
└── main.tsx           # Application entry point
```

## Development

### Prerequisites

- Node.js 18+
- pnpm package manager
- DevBoard backend running on `http://localhost:8000`

### Installation

Install dependencies:
```bash
pnpm install
```

### Running the Application

Start the development server:
```bash
pnpm dev
```

The application will be available at `http://localhost:5173` with hot reload enabled.

### Building for Production

Build the application:
```bash
pnpm build
```

Preview the production build:
```bash
pnpm preview
```

## Configuration

### Environment Variables

Create a `.env` file in the frontend directory:

```env
# Backend API URL (optional, defaults to http://localhost:8000)
VITE_API_BASE_URL=http://localhost:8000
```

### API Client

The application uses a centralized API client (`src/lib/api.ts`) that provides type-safe methods for all backend interactions:

```typescript
// Example usage
import { apiClient } from '../lib/api'

// Get all projects
const projects = await apiClient.getProjects()

// Create a new task
const task = await apiClient.createTask(projectId, {
  title: 'New Task',
  description: 'Task description',
  status: 'Pending'
})
```

## Key Components

### Project Dashboard
- Grid view of all projects with status indicators
- Create new projects with modal dialog
- Project search and filtering capabilities

### Project Detail
- Tabbed interface (Board, Details, Settings)
- Kanban board with task status columns
- Integrated chat interface for project Q&A
- Task creation and management

### Task Detail
- Comprehensive task information display
- Task status and metadata
- Direct access to task-specific chat agent

### Settings
- Integration management (GitHub, Jira, Slack)
- AI provider configuration (OpenAI, Claude, etc.)
- General application preferences

## Styling

The application uses Tailwind CSS with a custom configuration supporting:
- Dark/light mode with system preference detection
- Responsive breakpoints for mobile/tablet/desktop
- Custom color palette aligned with the DevBoard brand
- Consistent spacing and typography scales

## Type Safety

All components and API interactions are fully typed with TypeScript:
- Interface definitions for all data models
- Strict type checking for API responses
- Component prop validation
- Event handler type safety

## Contributing

1. Follow the existing code style and patterns
2. Use TypeScript interfaces for all data structures
3. Implement responsive design for all new components
4. Add proper error handling and loading states
5. Test components across different screen sizes and themes

## Available Scripts

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm preview` - Preview production build
- `pnpm lint` - Run ESLint
- `pnpm type-check` - Run TypeScript compiler check
