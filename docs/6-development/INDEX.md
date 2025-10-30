# Development

**Navigation**: [Documentation Home](../INDEX.md) > Development

## Purpose

This section provides everything needed to set up, develop, test, and deploy DevBoard. Whether you're a new contributor or deploying to production, start here.

## Documents

### [Getting Started](./getting-started.md)
Prerequisites, setup instructions, running the application locally, and initial configuration.

### [Testing](./testing.md)
Testing strategy, test organization, running tests, backend testing (pytest), and frontend testing (vitest).

### [Deployment](./deployment.md)
Docker configuration, production setup, environment management, and deployment best practices.

### [Contributing](./contributing.md)
Development workflow, code standards, pull request process, and contribution guidelines.

## Quick Start

### Prerequisites
- **Docker**: For running services
- **Python 3.12+**: Backend development
- **Node.js (LTS)**: Frontend development
- **uv**: Python package installer
- **npm**: Node.js package manager

### Setup Commands

**Backend**:
```bash
cd backend
uv sync                    # Install dependencies
uv run alembic upgrade head # Run migrations
uv run uvicorn devboard.api.main:app --reload # Start server
```

**Frontend**:
```bash
cd frontend
npm install               # Install dependencies
npm run dev              # Start dev server
```

See [Getting Started](./getting-started.md) for detailed instructions.

## Related Sections

- **[Architecture - System Design](../3-architecture/system-design.md)**: Technical architecture overview
- **[Architecture - Backend](../3-architecture/backend/INDEX.md)**: Backend implementation details
- **[Architecture - Frontend](../3-architecture/frontend/INDEX.md)**: Frontend implementation details
- **[MAINTENANCE_GUIDE](../MAINTENANCE_GUIDE.md)**: Documentation maintenance guidelines
