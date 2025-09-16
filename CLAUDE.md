# Overview
We are working to develop an application as described in @PROJECT_SPECIFICATION.md, using the implementation plan in @IMPLEMENTATION_PLAN.md.

# Development Process
- After making changes to the design or implementation details, ALWAYS:
  - make appropriate corresponding updates to the Project Specification document and Implementation plan.
  - Consider whether corresponding changes need to be made in the Frontend application
  - Add or update any relevant tests to cover the changes
  - Run tests to ensure everything works as expected
- Do not add implementation status (e.g. "Fully implemented") to the Project Specification document, only to Implementation Plan


# Backend Development Guidelines
## Overview
@backend/README.md

## Coding Style
- Use newer SQLAlchemy 2.0 style (e.g. use `select()` instead of `session.query()`)


## Testing
- Consider the available fixtures in `backend/devboard/tests/conftest.py` when writing tests


# Frontend Development Guidelines

- Types must be imported using type-only imports (e.g. `import type { XYZ } from '...'`)
- use `npm run test *` to run tests, DO NOT use `timeout XXX npm run test *` 
