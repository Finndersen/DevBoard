# DevBoard

> An AI-powered developer command centre for intelligent project management and development workflow automation.

## Overview

DevBoard is a **local-first developer command centre** that transforms how developers manage projects, tasks, and development workflows by intelligently orchestrating context from multiple sources and enabling AI-driven assistance throughout the development lifecycle.

The platform combines traditional project management with advanced AI agent capabilities, allowing developers to collaborate with specialized AI agents for planning, implementation, and code analysis—all while maintaining comprehensive context from GitHub, Jira, Slack, and local codebases.

DevBoard formalizes the development workflow through a **state-driven task lifecycle** where specialized AI agents guide each phase—from requirements gathering through technical design to implementation. Each task maintains **living artifacts** including detailed specifications, implementation plans, and change summaries that serve as working documents for AI collaboration. The system creates a **continuous improvement feedback loop** where insights from completed tasks automatically update architecture documents, refine agent behavior, and enhance design guidelines, creating a self-optimizing development environment that learns from experience and continuously improves its assistance quality.

## Key Features

### 🤖 AI-Powered Development Assistance
- **Specialized AI Agents**: Project Q&A, Task Planning, Codebase Investigation, and Implementation agents
- **Multi-Engine Support**: Choose between internal PydanticAI, Claude Code CLI, or Gemini CLI for different agent roles
- **Context-Aware Intelligence**: Agents understand full project context from multiple integrated sources
- **Virtual Tool Calling**: Safe, user-approved AI operations with transparent decision-making

### 📊 Intelligent Project Management
- **Living Documentation**: Maintain project specifications through collaborative AI editing
- **Task Lifecycle Management**: Guided workflows from definition through implementation to completion
- **Multi-Source Context Assembly**: Automatic integration of GitHub PRs, Jira tickets, Slack discussions, and codebase documentation
- **Conversational Interface**: Natural language interaction for project status, planning, and execution

### 💻 Developer-Centric Workflow
- **Browser-Style Multi-Tasking**: Work on multiple projects and tasks simultaneously with persistent tab system
- **Unified Dashboard**: Single interface for all projects, tasks, and codebases
- **Real-Time Updates**: WebSocket-powered live agent progress and notifications
- **Keyboard Shortcuts**: Full keyboard navigation for power users (Cmd+1-9, Cmd+W, Cmd+T)

### 🔗 Seamless Integrations
- **GitHub**: Repository analysis, PR reviews, issue tracking, commit history
- **Jira**: Project management, ticket workflows, progress tracking
- **Slack**: Team communications, discussion threads, decision history
- **Local Codebases**: File system analysis, architecture documentation generation
- **Web Resources**: Documentation sites and technical references

### 🎨 Modern User Experience
- **Dark/Light Theme**: Comprehensive theme support with system preference detection
- **Responsive Design**: Optimized for desktop and mobile workflows
- **Real-Time Collaboration**: Live agent conversations with streaming responses
- **Tool Approval Workflow**: Transparent AI operations requiring user approval

## Architecture

DevBoard implements a **local client-server architecture** optimized for developer workflows:

### Backend Stack
- **Framework**: FastAPI with async Python, SQLAlchemy 2.0 ORM
- **AI Integration**: PydanticAI with multi-provider LLM support (OpenAI, Anthropic, Google)
- **Database**: SQLite (PostgreSQL migration path)
- **Real-Time**: WebSocket support for agent progress streaming
- **Observability**: Pydantic Logfire for comprehensive instrumentation

### Frontend Stack
- **Framework**: React 19+ with TypeScript, Vite build system
- **State Management**: Zustand with Immer middleware, normalized entity caching
- **Styling**: Tailwind CSS with custom design system
- **Testing**: Vitest + React Testing Library + MSW
- **Real-Time**: WebSocket integration for live updates

### Key Architectural Patterns
- **Local-First**: Primary data and processing on user's machine
- **Agent-Driven**: AI agents handle complex workflows with human oversight
- **Context-Aware**: Intelligent multi-source context assembly
- **Unified Conversations**: Polymorphic conversation architecture supporting all entity types
- **Browser-Style Tabs**: Multi-task interface with persistent state

### Sandboxing

Bash commands executed by Claude Code agents run in an OS-level sandbox by default, providing filesystem and network isolation to reduce risk from prompt injection and unintended modifications. See [Claude Code Integration](docs/4-ai-agents/claude-code-integration.md) for details on configuration and customisation.

## Getting Started

### Prerequisites
- **Python 3.12+** for backend development
- **Node.js (LTS)** for frontend development
- **Docker** for containerized deployment
- **uv** for Python package management

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd DevBoard
   ```

2. **Run setup** (installs dependencies and runs migrations):
   ```bash
   ./setup.sh
   ```

3. **Start development servers** (runs both backend and frontend):
   ```bash
   ./start.sh
   ```

4. **Access the Application**:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Configuration

Configure integrations and AI providers through the Settings interface or environment variables:

```bash
# AI Provider Configuration
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# External Service Integration
GITHUB_TOKEN=your_github_token
JIRA_EMAIL=your_jira_email
JIRA_API_TOKEN=your_jira_token
SLACK_BOT_TOKEN=your_slack_token
```

See `.env.example` for complete configuration options.

## Development

### Backend Development
```bash
cd backend
make lint         # Auto-fix formatting and lint issues with ruff
make typecheck    # Type-check with pyright (slow — run separately)
make validate     # Run lint + typecheck together
make test         # Run test suite
```

### Frontend Development
```bash
cd frontend
pnpm dev              # Development server with HMR
pnpm build            # Production build
pnpm test             # Run tests
pnpm type-check       # TypeScript compilation check
```

### Docker Deployment
```bash
docker-compose up -d  # Start all services
```

## Documentation

- **[Project Specification](PROJECT_SPECIFICATION.md)**: Comprehensive product vision, requirements, and feature documentation
- **[Architecture Documentation](ARCHITECTURE.md)**: Detailed technical implementation and system design
- **[Backend README](backend/README.md)**: Backend-specific development guide
- **API Documentation**: Available at `/docs` when running the backend

## Testing

DevBoard includes comprehensive test coverage:

- **Backend**: Pytest with async support and fixtures (`make test`)
- **Frontend**: Vitest + React Testing Library + MSW (`pnpm test`)
- **Integration**: End-to-end workflow testing across API and UI layers

## License

[License information to be added]

## Support

For questions, issues, or feature requests, please [open an issue](../../issues) on GitHub.

