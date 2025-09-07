import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../test/utils'
import { ConfigurationField } from '../ConfigurationField'
import type { ConfigurationFieldInfo } from '../../lib/api'

describe('ConfigurationField', () => {
  const mockOnChange = vi.fn()

  const baseField: ConfigurationFieldInfo = {
    name: 'test_field',
    type: 'string',
    required: true,
    description: 'Test field description',
    current_value: 'test_value',
    value_source: 'database',
    is_secret: false,
    env_value_present: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders string field with label and input', () => {
    render(
      <ConfigurationField
        field={baseField}
        value="test_value"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('TEST_FIELD')).toBeInTheDocument() // Label is uppercase
    expect(screen.getByText('Test field description')).toBeInTheDocument()
    expect(screen.getByDisplayValue('test_value')).toBeInTheDocument()
    expect(screen.getByText('*')).toBeInTheDocument() // Required indicator
  })

  it('renders boolean field as checkbox', () => {
    const booleanField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'boolean',
      current_value: true,
    }

    render(
      <ConfigurationField
        field={booleanField}
        value={true}
        onChange={mockOnChange}
      />
    )

    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeInTheDocument()
    expect(checkbox).toBeChecked()
  })

  it('renders integer field with number input', () => {
    const integerField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'integer',
      current_value: 42,
    }

    render(
      <ConfigurationField
        field={integerField}
        value={42}
        onChange={mockOnChange}
      />
    )

    const numberInput = screen.getByRole('spinbutton')
    expect(numberInput).toBeInTheDocument()
    expect(numberInput).toHaveValue(42)
    expect(numberInput).toHaveAttribute('step', '1')
  })

  it('renders number field with decimal support', () => {
    const numberField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'number',
      current_value: 3.14,
    }

    render(
      <ConfigurationField
        field={numberField}
        value={3.14}
        onChange={mockOnChange}
      />
    )

    const numberInput = screen.getByRole('spinbutton')
    expect(numberInput).toBeInTheDocument()
    expect(numberInput).toHaveValue(3.14)
    expect(numberInput).toHaveAttribute('step', 'any') // Component uses 'any' for number fields
  })

  it('masks secret field values', () => {
    const secretField: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
      current_value: 'secret_token_123456',
    }

    render(
      <ConfigurationField
        field={secretField}
        value="secret_token_123456"
        onChange={mockOnChange}
      />
    )

    // Should display masked value
    expect(screen.getByDisplayValue('secr****3456')).toBeInTheDocument()
  })

  it('toggles secret field visibility', async () => {
    const user = userEvent.setup()
    const secretField: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
      current_value: 'secret_token_123456',
    }

    render(
      <ConfigurationField
        field={secretField}
        value="secret_token_123456"
        onChange={mockOnChange}
      />
    )

    // Initially masked
    expect(screen.getByDisplayValue('secr****3456')).toBeInTheDocument()

    // Click show button
    const showButton = screen.getByRole('button', { name: /show password/i })
    await user.click(showButton)

    // Should show full value
    expect(screen.getByDisplayValue('secret_token_123456')).toBeInTheDocument()

    // Click hide button
    const hideButton = screen.getByRole('button', { name: /hide password/i })
    await user.click(hideButton)

    // Should be masked again
    expect(screen.getByDisplayValue('secr****3456')).toBeInTheDocument()
  })

  it('calls onChange when input value changes', async () => {
    const user = userEvent.setup()

    render(
      <ConfigurationField
        field={baseField}
        value=""
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('textbox')
    await user.type(input, 'test')

    // Each character is typed individually
    expect(mockOnChange).toHaveBeenNthCalledWith(1, 'test_field', 't')
    expect(mockOnChange).toHaveBeenNthCalledWith(2, 'test_field', 'e')  
    expect(mockOnChange).toHaveBeenNthCalledWith(3, 'test_field', 's')
    expect(mockOnChange).toHaveBeenNthCalledWith(4, 'test_field', 't')
  })

  it('calls onChange when checkbox is toggled', async () => {
    const user = userEvent.setup()
    const booleanField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'boolean',
    }

    render(
      <ConfigurationField
        field={booleanField}
        value={false}
        onChange={mockOnChange}
      />
    )

    const checkbox = screen.getByRole('checkbox')
    await user.click(checkbox)

    expect(mockOnChange).toHaveBeenCalledWith('test_field', true)
  })

  it('calls onChange with number type for integer fields', async () => {
    const user = userEvent.setup()
    const integerField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'integer',
    }

    render(
      <ConfigurationField
        field={integerField}
        value=""
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    await user.type(input, '42')

    // Each character typed individually: '4' (becomes 4), then '2' (becomes 2)
    expect(mockOnChange).toHaveBeenNthCalledWith(1, 'test_field', 4)
    expect(mockOnChange).toHaveBeenNthCalledWith(2, 'test_field', 2)
  })

  it('shows environment variable indicator when set via environment', () => {
    const envField: ConfigurationFieldInfo = {
      ...baseField,
      value_source: 'environment',
      env_var_name: 'TEST_ENV_VAR',
      env_value_present: true,
    }

    render(
      <ConfigurationField
        field={envField}
        value="env_value"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Set via TEST_ENV_VAR')).toBeInTheDocument()
  })

  it('shows override warning when database value overrides environment', () => {
    const overrideField: ConfigurationFieldInfo = {
      ...baseField,
      value_source: 'database',
      env_var_name: 'TEST_ENV_VAR',
      env_value_present: true,
    }

    render(
      <ConfigurationField
        field={overrideField}
        value="override_value"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Overriding TEST_ENV_VAR')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reset to environment/i })).toBeInTheDocument()
  })

  it('resets to environment value when reset button is clicked', async () => {
    const user = userEvent.setup()
    const overrideField: ConfigurationFieldInfo = {
      ...baseField,
      value_source: 'database',
      env_var_name: 'TEST_ENV_VAR',
      env_value_present: true,
    }

    render(
      <ConfigurationField
        field={overrideField}
        value="override_value"
        onChange={mockOnChange}
      />
    )

    const resetButton = screen.getByRole('button', { name: /reset to environment/i })
    await user.click(resetButton)

    expect(mockOnChange).toHaveBeenCalledWith('test_field', null)
  })

  it('shows default value indicator', () => {
    const defaultField: ConfigurationFieldInfo = {
      ...baseField,
      value_source: 'default',
      default_value: 'default_value',
    }

    render(
      <ConfigurationField
        field={defaultField}
        value="default_value"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Using default: default_value')).toBeInTheDocument()
  })

  it('shows available environment variable hint', () => {
    const hintField: ConfigurationFieldInfo = {
      ...baseField,
      value_source: 'default',
      env_var_name: 'TEST_ENV_VAR',
      env_value_present: false,
    }

    render(
      <ConfigurationField
        field={hintField}
        value="some_value"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Can be set via TEST_ENV_VAR')).toBeInTheDocument()
  })

  it('disables input when disabled prop is true', () => {
    render(
      <ConfigurationField
        field={baseField}
        value="test_value"
        onChange={mockOnChange}
        disabled={true}
      />
    )

    const input = screen.getByDisplayValue('test_value')
    expect(input).toBeDisabled()
  })

  it('handles empty/null values gracefully', () => {
    render(
      <ConfigurationField
        field={baseField}
        value={null}
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('textbox')
    expect(input).toHaveValue('')
  })

  it('handles empty string for secret fields', () => {
    const secretField: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
      current_value: '',
    }

    render(
      <ConfigurationField
        field={secretField}
        value=""
        onChange={mockOnChange}
      />
    )

    // Secret fields are password inputs, find by ID
    const input = document.getElementById('test_field')
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('type', 'password')
  })

  it('displays field name as label', () => {
    const fieldWithLongName: ConfigurationFieldInfo = {
      ...baseField,
      name: 'very_long_field_name_with_underscores',
    }

    render(
      <ConfigurationField
        field={fieldWithLongName}
        value="test"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('VERY_LONG_FIELD_NAME_WITH_UNDERSCORES')).toBeInTheDocument()
  })

  it('shows required indicator only for required fields', () => {
    const optionalField: ConfigurationFieldInfo = {
      ...baseField,
      required: false,
    }

    render(
      <ConfigurationField
        field={optionalField}
        value="test"
        onChange={mockOnChange}
      />
    )

    expect(screen.queryByText('*')).not.toBeInTheDocument()
  })

  it('handles boolean field with null value', async () => {
    const user = userEvent.setup()
    const booleanField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'boolean',
      current_value: null,
    }

    render(
      <ConfigurationField
        field={booleanField}
        value={null}
        onChange={mockOnChange}
      />
    )

    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).not.toBeChecked()

    await user.click(checkbox)
    expect(mockOnChange).toHaveBeenCalledWith('test_field', true)
  })

  it('maintains input type attributes correctly', () => {
    const secretField: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
    }

    render(
      <ConfigurationField
        field={secretField}
        value="secret"
        onChange={mockOnChange}
      />
    )

    // Secret fields with values have toggle button, find by ID
    const input = document.getElementById('test_field')
    expect(input).toHaveAttribute('type', 'password')
  })

  it('shows description when provided', () => {
    const fieldWithDescription: ConfigurationFieldInfo = {
      ...baseField,
      description: 'This is a detailed description of the field',
    }

    render(
      <ConfigurationField
        field={fieldWithDescription}
        value="test"
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('This is a detailed description of the field')).toBeInTheDocument()
  })

  it('handles missing description gracefully', () => {
    const fieldWithoutDescription: ConfigurationFieldInfo = {
      ...baseField,
      description: undefined,
    }

    render(
      <ConfigurationField
        field={fieldWithoutDescription}
        value="test"
        onChange={mockOnChange}
      />
    )

    // Should still render the field without errors
    expect(screen.getByDisplayValue('test')).toBeInTheDocument()
  })
})