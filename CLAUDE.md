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

## Core Principles
* **Keep components small** and focused on a single responsibility.
* **Abstract reusable logic** into custom hooks and utility functions.
* **Never mutate state or props directly**; always create new objects or arrays.

## TypeScript
* **Type all props**, state, and function arguments.
* Use **`interface` for object shapes** (like props) and **`type` for unions/intersections**.
* **Avoid `any`**. Prefer `unknown` for better type safety when the type is truly unknown.
* Use **generics** to create reusable, type-safe components and functions.
* Use **string enums** for sets of related constants (e.g., status strings).

## Component Design
* **Default to functional components and hooks.**
* **Destructure props** and provide default values for optional ones.
* Use **`useState` for simple local state** and **`useReducer` for complex state logic**.
* **Organize files by feature**, co-locating component files (`.tsx`, `.css`, `.test.tsx`).

## Performance
* Use **`React.memo`**, **`useCallback`**, and **`useMemo`** to prevent unnecessary re-renders and expensive calculations.
* **Conditionally render components** instead of hiding them with CSS.
* Use **unique and stable IDs as `key` props** in lists, not array indices.
* **Code-split your application** with `React.lazy` and `Suspense`.

## Code Quality
* Name components with **PascalCase** and variables/functions with **camelCase**.
* Use **error boundaries** to catch runtime errors and prevent the entire app from crashing.
* **Write unit tests** for components and critical logic.