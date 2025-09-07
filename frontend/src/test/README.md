# Frontend Testing Documentation

This directory contains the testing setup and utilities for the DevBoard frontend application.

## Testing Stack

- **Vitest**: Fast test runner with Vite integration
- **React Testing Library**: Component testing with user-centric approach
- **MSW (Mock Service Worker)**: API mocking for realistic HTTP testing
- **jsdom**: DOM environment for testing React components
- **@testing-library/jest-dom**: Enhanced DOM assertions

## Test Structure

```
src/
├── test/
│   ├── setup.ts              # Global test setup and configuration
│   ├── utils.tsx              # Custom render function and test utilities
│   ├── mocks/
│   │   └── handlers.ts        # MSW request handlers for API mocking
│   └── README.md              # This documentation
├── components/__tests__/      # Component tests
├── views/__tests__/           # View component tests
└── lib/__tests__/             # Utility and API tests
```

## Running Tests

```bash
# Run tests in watch mode
npm test

# Run tests once
npm run test:run

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

## Testing Patterns

### Component Testing

- **User-centric testing**: Focus on what users see and do, not implementation details
- **Mock external dependencies**: Use MSW for API calls, mock React Router hooks
- **Test user interactions**: Use `@testing-library/user-event` for realistic user interactions
- **Accessibility testing**: Use semantic queries (`getByRole`, `getByLabelText`) to ensure accessibility

### API Testing

- **Comprehensive coverage**: Test all HTTP methods (GET, POST, PUT, DELETE, PATCH)
- **Error handling**: Test network errors, 404s, 500s, and other error scenarios  
- **Request validation**: Verify correct headers, body content, and URL construction
- **Response parsing**: Test JSON parsing and TypeScript interface compliance

### Mock Data

- **Factory functions**: Use factory functions for creating consistent test data
- **MSW handlers**: Centralized API mocking with realistic responses
- **Flexible mocking**: Override default handlers for specific test scenarios

## Best Practices

1. **Test behavior, not implementation**: Focus on what the user sees and does
2. **Use descriptive test names**: Clearly describe what is being tested
3. **Arrange, Act, Assert**: Structure tests with clear setup, action, and verification
4. **Mock external dependencies**: Keep tests isolated and predictable
5. **Test error scenarios**: Ensure proper error handling and user feedback
6. **Clean up after tests**: Reset mocks and state between tests

## Writing New Tests

### Component Test Template

```typescript
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../test/utils'
import MyComponent from '../MyComponent'

describe('MyComponent', () => {
  it('renders component correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const user = userEvent.setup()
    render(<MyComponent />)
    
    await user.click(screen.getByRole('button', { name: /click me/i }))
    
    await waitFor(() => {
      expect(screen.getByText('Success')).toBeInTheDocument()
    })
  })
})
```

### API Test Template

```typescript
import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { apiClient } from '../api'

describe('API Client', () => {
  it('makes correct API call', async () => {
    server.use(
      http.get('*/api/endpoint', () => {
        return HttpResponse.json({ data: 'mock response' })
      })
    )

    const result = await apiClient.getData()
    expect(result).toEqual({ data: 'mock response' })
  })
})
```

## Debugging Tests

- Use `screen.debug()` to see the rendered DOM
- Use `--ui` flag to run tests in interactive mode
- Check network requests in MSW handlers
- Use `console.log` for debugging test data flow

## Coverage Goals

- **Statements**: > 90%
- **Branches**: > 85%
- **Functions**: > 90%
- **Lines**: > 90%

Focus on testing critical user paths and error scenarios rather than achieving 100% coverage for its own sake.