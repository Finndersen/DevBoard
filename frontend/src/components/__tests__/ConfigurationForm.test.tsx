import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render, createMockConfigurationResponse } from '../../test/utils'
import { ConfigurationForm } from '../ConfigurationForm'

describe('ConfigurationForm', () => {
  const mockConfig = createMockConfigurationResponse({
    key: 'integration.github.main',
    fields: [
      {
        name: 'api_token',
        type: 'string',
        required: true,
        description: 'GitHub API token',
        env_value: null,
        db_value: null,
        default_value: null,
        is_secret: true,
        env_var_name: 'GITHUB_API_TOKEN',
        is_overridden: false,
        effective_value: null,
      },
      {
        name: 'base_url',
        type: 'string',
        required: false,
        description: 'GitHub API base URL',
        env_value: null,
        db_value: null,
        default_value: 'https://api.github.com',
        is_secret: false,
        env_var_name: 'GITHUB_BASE_URL',
        is_overridden: false,
        effective_value: 'https://api.github.com',
      },
    ],
    is_valid: false,
    validation_errors: ['Missing required field: api_token'],
  })

  const defaultProps = {
    config: mockConfig,
    title: 'GitHub Integration',
    onSave: vi.fn(),
    onTestConnection: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders configuration form with title and status', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    expect(screen.getByText('Invalid')).toBeInTheDocument()
  })

  it('loads configuration data on mount', async () => {
    render(<ConfigurationForm {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
      expect(screen.getByText('GitHub API token')).toBeInTheDocument()
      expect(screen.getByText('GitHub API base URL')).toBeInTheDocument()
    })
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
      is_valid: true,
      validation_errors: [],
    }

    render(<ConfigurationForm {...defaultProps} config={validConfig} />)

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

    // First enable override for base_url field
    const allCheckboxes = screen.getAllByRole('checkbox')
    // Find the override toggle for base_url (it should be the second checkbox after any other checkboxes)
    const baseUrlOverrideToggle = allCheckboxes.find(checkbox => {
      const container = checkbox.closest('.space-y-1')
      return container?.querySelector('label[for="base_url"]')
    })
    await user.click(baseUrlOverrideToggle!)
    
    // Now make a change to the field
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
          is_valid: true,
          validation_errors: [],
        })
      })
    )

    render(<ConfigurationForm {...defaultProps} onSave={onSaveMock} />)

    await waitFor(() => {
      expect(screen.getByText('GitHub Integration')).toBeInTheDocument()
    })

    // First enable override for base_url field  
    const allCheckboxes = screen.getAllByRole('checkbox')
    const baseUrlOverrideToggle = allCheckboxes.find(checkbox => {
      const container = checkbox.closest('.space-y-1')
      return container?.querySelector('label[for="base_url"]')
    })
    await user.click(baseUrlOverrideToggle!)

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

    // First enable override for base_url field  
    const allCheckboxes = screen.getAllByRole('checkbox')
    const baseUrlOverrideToggle = allCheckboxes.find(checkbox => {
      const container = checkbox.closest('.space-y-1')
      return container?.querySelector('label[for="base_url"]')
    })
    await user.click(baseUrlOverrideToggle!)

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
      is_valid: true,
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

    // First enable override for base_url field  
    const allCheckboxes = screen.getAllByRole('checkbox')
    const baseUrlOverrideToggle = allCheckboxes.find(checkbox => {
      const container = checkbox.closest('.space-y-1')
      return container?.querySelector('label[for="base_url"]')
    })
    await user.click(baseUrlOverrideToggle!)

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