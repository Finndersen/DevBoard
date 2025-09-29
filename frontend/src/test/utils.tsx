import React, { type ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { ApprovalsProvider } from '../contexts/ApprovalsContext'
import { PendingMessagesProvider } from '../contexts/PendingMessagesContext'
import { DarkModeProvider } from '../contexts/DarkModeContext'

// Custom render function with providers
// eslint-disable-next-line react-refresh/only-export-components
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      <DarkModeProvider>
        <ApprovalsProvider>
          <PendingMessagesProvider>
            {children}
          </PendingMessagesProvider>
        </ApprovalsProvider>
      </DarkModeProvider>
    </BrowserRouter>
  )
}

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options })

// Re-export everything from @testing-library/react
// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react'

// Override render export
export { customRender as render }

// Test data factories
export const createMockProject = (overrides = {}) => ({
  id: 1,
  name: 'Test Project',
  specification: {
    id: 1,
    document_type: 'project_specification',
    content: 'Test project specification content',
    content_hash: 'proj123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  description: 'A mock project for testing frontend components and API integrations',
  default_conversation_id: 1,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
})

export const createMockTask = (overrides = {}) => ({
  id: 1,
  project_id: 1,
  title: 'Test Task',
  status: 'Pending',
  codebase_id: null,
  remote_task_id: null,
  default_conversation_id: 3,
  specification: {
    id: 3,
    document_type: 'task_specification',
    content: 'Test task specification content',
    content_hash: 'task123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  implementation_plan: {
    id: 4,
    document_type: 'implementation_plan',
    content: 'Test implementation plan content',
    content_hash: 'plan123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
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
  is_valid: true,
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