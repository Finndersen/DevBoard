# Contributing

**Navigation**: [Documentation Home](../INDEX.md) > [Development](./INDEX.md) > Contributing

## Overview

Development workflow, code standards, and contribution process.

## Development Workflow

### Branch Strategy

- **Main Branch**: `master` - production-ready code
- **Feature Branches**: `feature/descriptive-name`
- **Bug Fix Branches**: `fix/issue-description`
- **Refactoring Branches**: `refactor/what-is-being-refactored`

### Creating a Branch

```bash
git checkout master && git pull origin master
git checkout -b feature/your-feature-name
# Make changes
git add . && git commit -m "Description"
git push origin feature/your-feature-name
```

## Code Standards

### Python (Backend)

**Formatting/Linting**: Ruff (`ruff format .`, `ruff check .`)
**Type Hints**: Required for all function parameters and return values
**Docstrings**: Required for public functions, classes, modules
**Import Organization**: Standard library, third-party, local (separated by blank lines)
**Async/Await**: Use for I/O operations

### TypeScript/React (Frontend)

**Linting**: ESLint (`npm run lint`)
**Type Safety**: TypeScript strict mode with comprehensive definitions
**Component Naming**: PascalCase
**Hooks Best Practices**: Complete dependency arrays, custom hooks start with "use"

### Database

**Migrations**: Alembic for schema changes (`alembic revision --autogenerate -m "Description"`)
**Models**: SQLAlchemy 2.0 patterns with `Mapped[]` annotations
**Relationships**: Define with proper `back_populates`

## Testing Requirements

### Backend

**Coverage**: 80%+ on new code
**Location**: Mirror source structure in `tests/`
**Naming**: Descriptive function names (e.g., `test_task_state_transition_from_planning_to_implementing`)
**Async Tests**: Mark with `@pytest.mark.asyncio`
**Run**: `pytest`

### Frontend

**Testing Library**: React Testing Library with user-centric queries
**Coverage**: 75%+ on new code
**Naming**: Descriptive test descriptions
**Run**: `npm test`

## Commit Guidelines

### Format

```
Brief description (50 chars or less)

More detailed explanation if needed (wrap at 72 characters).
Explain what and why.

- Bullet points for multiple changes

Fixes #123
```

### Types

- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `docs:` Documentation changes
- `test:` Test additions/modifications
- `chore:` Build process or auxiliary tools

### Best Practices

- Atomic commits (one logical change per commit)
- Descriptive messages (what and why, not how)
- Reference issues (`Fixes #123`, `Relates to #456`)
- GPG signing recommended

## Pull Request Process

### Before Creating PR

1. Update from main: `git rebase master`
2. Run tests: `pytest` (backend), `npm test` (frontend)
3. Run linters: `ruff check .` (backend), `npm run lint` (frontend)
4. Type check: `pyright` (backend), `npm run type-check` (frontend)

### Creating PR

**Push branch**: `git push origin feature/your-feature`

**PR Description Template**:
```markdown
## Description
Brief description

## Changes Made
- List of changes

## Testing
How to test:
1. Steps
2. Expected result

## Related Issues
Fixes #123

## Screenshots (if applicable)
[Add for UI changes]
```

### Review Process

1. Automated checks (CI: tests, linters, type checks)
2. Code review by team members
3. Address feedback
4. Approval
5. Squash and merge to main

### Responding to Feedback

- Be responsive and open
- Ask questions for clarification
- Update PR by pushing to same branch
- Mark conversations resolved when addressed

## Code Review Guidelines

### For Reviewers

- Constructive, specific, timely (1-2 business days)
- Check: correctness, tests, performance, security, style, documentation
- Use prefixes: "Question:", "Suggestion:", "Nit:"

### For Authors

- Be receptive, explain decisions
- Address feedback with code updates
- Reply to comments, request re-review after changes

## Documentation Requirements

**Code Documentation**: Docstrings, type hints, comments for complex logic
**Architecture Documentation**: Update `docs/` for significant changes. Markdown with consistent style, cross-reference related docs.

## Release Process

**Semantic Versioning**: MAJOR.MINOR.PATCH
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

**Steps**: Update version, update changelog, create tag, build artifacts, deploy, announce

## Getting Help

**Documentation**: `docs/` directory
**Architecture Guide**: [Architecture Overview](../3-architecture/overview.md)
**Issues**: Search existing issues
**Communication**: GitHub Issues and Discussions

## Maintenance

See [MAINTENANCE_GUIDE.md](../../MAINTENANCE_GUIDE.md) for dependency updates, security patches, performance optimization, technical debt management.

## See Also

- [Getting Started](./getting-started.md) - Development environment setup
- [Testing](./testing.md) - Testing guidelines
- [Deployment](./deployment.md) - Deployment procedures
