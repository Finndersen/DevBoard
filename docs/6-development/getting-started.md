# Getting Started

**Navigation**: [Documentation Home](../INDEX.md) > [Development](./INDEX.md) > Getting Started

## Overview

Local development environment setup for DevBoard.

## Prerequisites

**Required**:
- **Docker**: Latest stable (database and services)
- **Python 3.12+**: Backend development
- **Node.js 18 LTS+**: Frontend development
- **uv**: Python package installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **npm**: Included with Node.js

**Optional**:
- **Git**: Version control (for cloning)
- **PostgreSQL**: Alternative to SQLite (production-like setup)

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/devboard.git
cd devboard
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# OR
.venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e .

# Set up database
alembic upgrade head

# Create .env file
cp .env.example .env
# Edit .env with your API keys
```

**Minimum .env Configuration**:
```bash
# At least one LLM provider required
OPENAI_API_KEY=your_key_here
# OR
ANTHROPIC_API_KEY=your_key_here
# OR
GOOGLE_API_KEY=your_key_here

# Optional: External integrations
GITHUB_ACCESS_TOKEN=your_token
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=your_token
SLACK_BOT_TOKEN=your_token
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
```

## Running the Application

### Start Backend

```bash
cd backend
source .venv/bin/activate
uvicorn devboard.api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend available at: `http://localhost:8000`
API docs: `http://localhost:8000/docs`

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend available at: `http://localhost:5173`

## Verify Installation

1. **Check Backend Health**: Visit `http://localhost:8000/health`
2. **Check Frontend**: Visit `http://localhost:5173`
3. **Run Tests**:
   - Backend: `cd backend && pytest`
   - Frontend: `cd frontend && npm test`

## Development Workflow

1. **Code Changes**: Edit files in `backend/` or `frontend/`
2. **Hot Reload**: Both backend (--reload) and frontend (Vite) auto-reload on changes
3. **Run Tests**: Run relevant tests before committing
4. **Linting**:
   - Backend: `ruff check . && ruff format .`
   - Frontend: `npm run lint`

## Common Issues

**Backend won't start**:
- Check Python version: `python --version` (must be 3.12+)
- Verify virtual environment activated
- Check .env file exists with at least one LLM API key

**Frontend won't start**:
- Check Node version: `node --version` (must be 18+)
- Delete `node_modules` and run `npm install` again
- Check for port conflicts (default: 5173)

**Database errors**:
- Run migrations: `alembic upgrade head`
- Check database file permissions
- Delete `backend/devboard.db` and re-run migrations for fresh start

**LLM API errors**:
- Verify API keys are valid
- Check key has quota/credits
- Test key directly with provider's API

## Docker Alternative

For containerized development:

```bash
# Build and start services
docker-compose up --build

# Run migrations
docker-compose exec backend alembic upgrade head
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## Next Steps

- **Explore Codebase**: Review [Architecture](../3-architecture/INDEX.md) documentation
- **Make Changes**: See [Contributing](./contributing.md) guide
- **Run Tests**: See [Testing](./testing.md) guide
- **Deploy**: See [Deployment](./deployment.md) guide

## See Also

- [Contributing](./contributing.md) - Development workflow
- [Testing](./testing.md) - Testing guidelines
- [Deployment](./deployment.md) - Deployment procedures
- [Architecture](../3-architecture/INDEX.md) - System architecture
