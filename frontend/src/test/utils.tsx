import React, { type ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { PendingMessagesProvider } from '../contexts/PendingMessagesContext'
import { DarkModeProvider } from '../contexts/DarkModeContext'
import ConversationEventHandlerProvider from '../components/chat/ConversationEventHandlerProvider'

// Custom render function with providers
// eslint-disable-next-line react-refresh/only-export-components
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      <DarkModeProvider>
        <PendingMessagesProvider>
          <ConversationEventHandlerProvider>
            {children}
          </ConversationEventHandlerProvider>
        </PendingMessagesProvider>
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

// Mock documents for separate document API calls
export const mockDocuments = {
  // Project specification document
  1: {
    id: 1,
    document_type: 'project_specification',
    content: 'Test project specification content',
    content_hash: 'proj123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  // Task specification document
  3: {
    id: 3,
    document_type: 'task_specification',
    content: 'Test task specification content',
    content_hash: 'task123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  // Task implementation plan document
  4: {
    id: 4,
    document_type: 'task_implementation_plan',
    content: 'Test implementation plan content',
    content_hash: 'plan123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
}

export const createMockDocument = (overrides = {}) => ({
  id: 1,
  document_type: 'project_specification',
  content: 'Test document content',
  content_hash: 'hash123',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
})

export const createMockProject = (overrides = {}) => ({
  id: 1,
  name: 'Test Project',
  specification_document_id: 1,
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
  conversation_id: 3,
  specification_document_id: 3,
  implementation_plan_document_id: 4,
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
      env_value: null,
      db_value: 'test_value',
      default_value: null,
      is_secret: false,
      env_var_name: 'TEST_FIELD',
      is_overridden: false,
      effective_value: 'test_value',
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