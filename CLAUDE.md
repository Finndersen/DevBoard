# Overview
We are working to develop an application as described in @PROJECT_SPECIFICATION.md, using the implementation plan in @IMPLEMENTATION_PLAN.md.

As part of the development process, if changes are made to the design or implementation details, make appropriate corresponding updates to the above two files.
Do not add implementation status (e.g. "Fully implemented") to the Project Specification document, only to Implementation Plan

# Backend Development Guidelines
## Overview
@backend/README.md

## Coding Style
- Use newer SQLAlchemy 2.0 style (e.g. use `select()` instead of `session.query()`)



# Frontend Development Guidelines

- Types must be imported using type-only imports (e.g. `import type { XYZ } from '...'`)