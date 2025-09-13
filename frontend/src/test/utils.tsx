import React, { type ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

// Custom render function with providers
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  )
}

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options })

// Re-export everything from @testing-library/react
export * from '@testing-library/react'

// Override render export
export { customRender as render }

// Test data factories
export const createMockProject = (overrides = {}) => ({
  id: 1,
  name: 'Test Project',
  specification: 'Test project specification',
  description: 'A mock project for testing frontend components and API integrations',
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
})

export const createMockTask = (overrides = {}) => ({
  id: 1,
  project_id: 1,
  title: 'Test Task',
  description: 'Test task description',
  status: 'Pending',
  codebase_id: null,
  remote_task_id: null,
  conversation_id: null,
  implementation_plan: null,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
})

export const createMockConfigurationResponse = (overrides = {}) => ({
  key: 'test.config.key',
  fields: [
    {
      name: 'test_field',
      type: 'string' as const,
      required: true,
      description: 'Test field',
      current_value: 'test_value',
      value_source: 'database' as const,
      is_secret: false,
      env_value_present: false,
    },
  ],
  validation_status: 'valid' as const,
  validation_errors: [],
  ...overrides,
})

// Helper functions for testing
export const waitForLoadingToFinish = () => 
  new Promise(resolve => setTimeout(resolve, 0))

export const mockNavigate = vi.fn()

// Mock React Router navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})