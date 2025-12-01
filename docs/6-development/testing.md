# Testing

**Navigation**: [Documentation Home](../INDEX.md) > [Development](./INDEX.md) > Testing

## Overview

Comprehensive testing for DevBoard backend (pytest) and frontend (Vitest + React Testing Library).

## Backend Testing

**Location**: `backend/tests/`
**Framework**: pytest with pytest-asyncio
**Coverage Target**: 80%+ on new code
**Structure**: Mirrors source (`devboard/agents/base_agent.py` → `tests/agents/test_base_agent.py`)

### Running Tests

```bash
cd backend && source .venv/bin/activate

# All tests
pytest

# With coverage
pytest --cov=devboard --cov-report=html

# Specific file/test
pytest tests/test_repositories.py
pytest tests/test_repositories.py::test_create_project
```

### Test Categories

**Unit Tests**: Individual functions/methods, mock dependencies, fast
**Integration Tests**: Component interactions, test database, API endpoints with TestClient
**Repository Tests**: Database operations, CRUD testing

### Key Patterns

**Async Tests**: `@pytest.mark.asyncio`
**Database Fixtures**: `conftest.py` provides test session
**API Testing**: TestClient for endpoint testing
**Mocking**: `@patch` for external dependencies

## Frontend Testing

**Location**: `frontend/src/**/__tests__/`
**Frameworks**: Vitest, React Testing Library, MSW (API mocking)
**Coverage Target**: 75%+ on new code
**Structure**: Colocated `__tests__/` directories

### Running Tests

```bash
cd frontend

# All tests
pnpm test

# With coverage
pnpm test:coverage

# Watch mode
pnpm test:watch

# UI mode
pnpm test:ui
```

### Test Categories

**Component Tests**: React components with user interactions (`render`, `screen`, `fireEvent`)
**Hook Tests**: Custom hooks with `renderHook` and `act`
**Integration Tests**: Feature workflows with MSW API mocking

### Key Patterns

**User-Centric Queries**: Query by accessible roles/labels
**API Mocking**: MSW (Mock Service Worker) for realistic API testing
**Descriptive Names**: Clear test descriptions

## Testing Best Practices

- Test behavior, not implementation
- Keep tests simple and focused
- Use descriptive names
- Avoid test interdependencies
- Mock external dependencies
- Write tests as you code

### What to Test

**Backend**: Business logic, API contracts, database operations, error handling
**Frontend**: User interactions, state management, API integration, error/loading states

### What Not to Test

Framework internals, third-party libraries, generated code, trivial getters/setters, private details

## CI/CD

Tests run automatically on pull requests. PRs with failing tests cannot merge. Coverage reports generated and tracked.
