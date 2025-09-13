import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../test/utils'
import { ConfigurationField } from '../ConfigurationField'
import type { ConfigurationFieldInfo } from '../../lib/api'

describe('ConfigurationField', () => {
  const mockOnChange = vi.fn()
  const mockOnOverrideToggle = vi.fn()

  const baseField: ConfigurationFieldInfo = {
    name: 'test_field',
    type: 'string',
    required: true,
    description: 'Test field description',
    effective_value: 'test_value',
    env_value: null,
    db_value: 'test_value',
    default_value: null,
    is_secret: false,
    is_overridden: true,
    env_var_name: 'TEST_FIELD'
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
        overrideEnabled={true}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByText('TEST_FIELD')).toBeInTheDocument()
    expect(screen.getByText('Test field description')).toBeInTheDocument()
    expect(screen.getByDisplayValue('test_value')).toBeInTheDocument()
    expect(screen.getByText('*')).toBeInTheDocument() // Required indicator
  })

  it('shows override toggle when field has overridable values', () => {
    const fieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      env_value: 'env_value',
      is_overridden: false
    }

    render(
      <ConfigurationField
        field={fieldWithEnv}
        value="env_value"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByText('Override')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })

  it('shows env var source info when env value exists', () => {
    const fieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      env_value: 'env_test_value',
      is_overridden: false,
      effective_value: 'env_test_value'
    }

    render(
      <ConfigurationField
        field={fieldWithEnv}
        value="env_test_value"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByText(/TEST_FIELD: env_test_value/)).toBeInTheDocument()
  })

  it('shows default value source info when default value exists', () => {
    const fieldWithDefault: ConfigurationFieldInfo = {
      ...baseField,
      env_value: null,
      default_value: 'default_value',
      is_overridden: false,
      effective_value: 'default_value'
    }

    render(
      <ConfigurationField
        field={fieldWithDefault}
        value="default_value"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByText(/Default: default_value/)).toBeInTheDocument()
  })

  it('disables input when override is off and overridable value exists', () => {
    const fieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      env_value: 'env_value',
      is_overridden: false
    }

    render(
      <ConfigurationField
        field={fieldWithEnv}
        value="env_value"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByDisplayValue('env_value')).toBeDisabled()
  })

  it('enables input when override is on', () => {
    render(
      <ConfigurationField
        field={baseField}
        value="test_value"
        onChange={mockOnChange}
        overrideEnabled={true}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByDisplayValue('test_value')).not.toBeDisabled()
  })

  it('shows override status indicator when overriding', () => {
    const fieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      env_value: 'env_value',
      is_overridden: true
    }

    render(
      <ConfigurationField
        field={fieldWithEnv}
        value="override_value"
        onChange={mockOnChange}
        overrideEnabled={true}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    expect(screen.getByText(/Overriding environment variable/)).toBeInTheDocument()
  })

  it('handles override toggle clicks', async () => {
    const user = userEvent.setup()
    const fieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      env_value: 'env_value',
      is_overridden: false
    }

    render(
      <ConfigurationField
        field={fieldWithEnv}
        value="env_value"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    const toggleCheckbox = screen.getByRole('checkbox')
    await user.click(toggleCheckbox)

    expect(mockOnOverrideToggle).toHaveBeenCalledWith('test_field', true)
  })

  it('handles secret fields correctly', () => {
    const secretField: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true
    }

    render(
      <ConfigurationField
        field={secretField}
        value="secret_value"
        onChange={mockOnChange}
        overrideEnabled={true}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    // Should show masked value initially
    expect(screen.getByDisplayValue(/secr\*\*\*\*alue/)).toBeInTheDocument()
  })

  it('censors secret values in source indicators', () => {
    const secretFieldWithEnv: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
      env_value: 'secret_env_token_1234567890',
      is_overridden: false
    }

    render(
      <ConfigurationField
        field={secretFieldWithEnv}
        value="secret_env_token_1234567890"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    // Should show censored env value in both input field and source indicator
    expect(screen.getByDisplayValue('secr****7890')).toBeInTheDocument()
    expect(screen.getByText(/: secr\*\*\*\*7890/)).toBeInTheDocument()
  })

  it('censors short secret values appropriately', () => {
    const secretFieldWithShortValue: ConfigurationFieldInfo = {
      ...baseField,
      is_secret: true,
      default_value: 'abc123',
      env_value: null,
      is_overridden: false
    }

    render(
      <ConfigurationField
        field={secretFieldWithShortValue}
        value="abc123"
        onChange={mockOnChange}
        overrideEnabled={false}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    // Should show censored short value in the source indicator
    // Note: input field shows the user-provided value, source indicator shows censored fallback value
    expect(screen.getByText(/Default: ab\*\*\*\*/)).toBeInTheDocument()
  })

  it('renders boolean field as checkbox', () => {
    const booleanField: ConfigurationFieldInfo = {
      ...baseField,
      type: 'boolean',
      effective_value: true
    }

    render(
      <ConfigurationField
        field={booleanField}
        value={true}
        onChange={mockOnChange}
        overrideEnabled={true}
        onOverrideToggle={mockOnOverrideToggle}
      />
    )

    const checkbox = screen.getByRole('checkbox', { name: /TEST_FIELD/ })
    expect(checkbox).toBeChecked()
  })
})