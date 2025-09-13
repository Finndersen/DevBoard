import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render, createMockConfigurationResponse } from '../../test/utils'
import { ConfigurationForm } from '../ConfigurationForm'

describe('ConfigurationForm', () => {
  const defaultProps = {
    configKey: 'integration.github.main',
    title: 'GitHub Integration',
    onSave: vi.fn(),
    onTestConnection: vi.fn(),
  }

  const mockConfig = createMockConfigurationResponse({
    key: 'integration.github.main',
    fields: [
      {
        name: 'api_token',
        type: 'string',
        required: true,
        description: 'GitHub API token',
        current_value: null,
        value_source: 'environment',
        is_secret: true,
        env_var_name: 'GITHUB_API_TOKEN',
        env_value_present: false,
      },
      {
        name: 'base_url',
        type: 'string',
        required: false,
        description: 'GitHub API base URL',
        current_value: 'https://api.github.com',
        value_source: 'default',
        is_secret: false,
        default_value: 'https://api.github.com',
        env_value_present: false,
      },
    ],
    validation_status: 'unconfigured',
    validation_errors: ['Missing required field: api_token'],
  })

  beforeEach(() => {
    vi.clearAllMocks()
    
    // Setup default API response
    server.use(
      http.get('*/api/configurations/integration.github.main/detail', () => {
        return HttpResponse.json(mockConfig)
      })
    )
  })

  it('renders configuration form with title and status', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    expect(screen.getByText('Unconfigured')).toBeInTheDocument()
  })

  it('loads configuration data on mount', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
      expect(screen.getByText('GitHub API token')).toBeInTheDocument()
      expect(screen.getByText('GitHub API base URL')).toBeInTheDocument()
    })
  })

  it('displays loading state initially', () => {
    render(<ConfigurationForm {...defaultProps} />)

    // Should show loading skeleton
    expect(document.querySelectorAll('.animate-pulse')).toHaveLength(1)
  })

  it('shows validation errors when configuration is invalid', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Configuration Issues:')).toBeInTheDocument()
      expect(screen.getByText('Missing required field: api_token')).toBeInTheDocument()
    })
  })

  it('displays different status indicators correctly', async () => {
    const validConfig = {
      ...mockConfig,
      validation_status: 'valid' as const,
      validation_errors: [],
    }

    server.use(
      http.get('*/api/configurations/integration.github.main/detail', () => {
        return HttpResponse.json(validConfig)
      })
    )

    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Valid')).toBeInTheDocument()
    })

    const statusIcon = document.querySelector('.text-green-600')
    expect(statusIcon).toBeInTheDocument()
  })

  it('renders configuration fields with ConfigurationField component', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub API token')).toBeInTheDocument()
      expect(screen.getByText('GitHub API base URL')).toBeInTheDocument()
    })

    // Should have at least one input field (base_url is textbox, api_token is password)
    const textInputs = screen.getAllByRole('textbox')
    expect(textInputs.length).toBeGreaterThan(0)
  })

  it('enables save button only when there are changes', async () => {
    const user = userEvent.setup()
    
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    const saveButton = screen.getByRole('button', { name: /save changes/i })
    
    // Save button should be disabled initially (no changes)
    expect(saveButton).toBeDisabled()

    // Make a change to a field
    const baseUrlInput = screen.getByDisplayValue('https://api.github.com')
    await user.clear(baseUrlInput)
    await user.type(baseUrlInput, 'https://api.github.com/v3')

    // Save button should be enabled after changes
    expect(saveButton).not.toBeDisabled()
  })

  it('saves configuration changes when save button is clicked', async () => {
    const user = userEvent.setup()
    const onSaveMock = vi.fn()

    server.use(
      http.patch('*/api/configurations/integration.github.main/fields', async ({ request }) => {
        await request.json() // Consume request body
        return HttpResponse.json({
          ...mockConfig,
          validation_status: 'valid' as const,
          validation_errors: [],
        })
      })
    )

    render(<ConfigurationForm {...defaultProps} onSave={onSaveMock} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    // Make a change
    const baseUrlInput = screen.getByDisplayValue('https://api.github.com')
    await user.clear(baseUrlInput)
    await user.type(baseUrlInput, 'https://custom.github.com')

    // Save changes
    const saveButton = screen.getByRole('button', { name: /save changes/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(onSaveMock).toHaveBeenCalled()
    })
  })


  it('tests connection when test button is clicked', async () => {
    const user = userEvent.setup()
    const onTestConnectionMock = vi.fn()

    server.use(
      http.post('*/api/settings/integrations/github/test', () => {
        return HttpResponse.json({
          success: true,
        })
      })
    )

    render(<ConfigurationForm {...defaultProps} onTestConnection={onTestConnectionMock} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    const testButton = screen.getByRole('button', { name: /test connection/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(screen.getByText('Connection Test Successful')).toBeInTheDocument()
      expect(screen.getByText('Connection successful')).toBeInTheDocument()
      expect(onTestConnectionMock).toHaveBeenCalled()
    })
  })

  it('shows error message when connection test fails', async () => {
    const user = userEvent.setup()

    server.use(
      http.post('*/api/settings/integrations/github/test', () => {
        return HttpResponse.json({
          success: false,
          error_message: 'Invalid API token',
        })
      })
    )

    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    const testButton = screen.getByRole('button', { name: /test connection/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(screen.getByText('Connection Test Failed')).toBeInTheDocument()
      expect(screen.getByText('Invalid API token')).toBeInTheDocument()
    })
  })

  it('resets form when reset button is clicked', async () => {
    const user = userEvent.setup()
    
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    // Make a change
    const baseUrlInput = screen.getByDisplayValue('https://api.github.com')
    await user.clear(baseUrlInput)
    await user.type(baseUrlInput, 'https://custom.github.com')

    expect(baseUrlInput).toHaveValue('https://custom.github.com')

    // Reset form - this triggers a new API call to reload configuration
    const resetButton = screen.getByRole('button', { name: /reset/i })
    await user.click(resetButton)

    // Wait for the form to reload from API
    await waitFor(() => {
      const refreshedInput = screen.getByDisplayValue('https://api.github.com')
      expect(refreshedInput).toBeInTheDocument()
    }, { timeout: 3000 })
  })



  it('does not show test connection button when onTestConnection is not provided', async () => {
    render(<ConfigurationForm {...defaultProps} onTestConnection={undefined} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    expect(screen.queryByRole('button', { name: /test connection/i })).not.toBeInTheDocument()
  })

  it('calls onSave callback with configuration data', async () => {
    const user = userEvent.setup()
    const onSaveMock = vi.fn()

    const updatedConfig = {
      ...mockConfig,
      validation_status: 'valid' as const,
    }

    server.use(
      http.patch('*/api/configurations/integration.github.main/fields', () => {
        return HttpResponse.json(updatedConfig)
      })
    )

    render(<ConfigurationForm {...defaultProps} onSave={onSaveMock} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    // Make a change and save
    const baseUrlInput = screen.getByDisplayValue('https://api.github.com')
    await user.clear(baseUrlInput)
    await user.type(baseUrlInput, 'https://custom.github.com')

    const saveButton = screen.getByRole('button', { name: /save changes/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(onSaveMock).toHaveBeenCalledWith(updatedConfig)
    })
  })
})