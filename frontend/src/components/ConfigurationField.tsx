import React, { useState } from 'react'
import { EyeIcon, EyeSlashIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import type { ConfigurationFieldInfo } from '../lib/api'

interface ConfigurationFieldProps {
  field: ConfigurationFieldInfo
  value: string | number | boolean | null
  onChange: (fieldName: string, value: string | number | boolean | null) => void
  overrideEnabled: boolean
  onOverrideToggle: (fieldName: string, enabled: boolean) => void
  disabled?: boolean
}

export const ConfigurationField: React.FC<ConfigurationFieldProps> = ({ 
  field, 
  value, 
  onChange, 
  overrideEnabled,
  onOverrideToggle,
  disabled = false 
}) => {
  const [showSecret, setShowSecret] = useState(false)
  
  // Determine if field has default or env values available for override
  const hasDefaultValue = field.default_value !== null && field.default_value !== undefined
  const hasEnvValue = field.env_value !== null && field.env_value !== undefined
  const hasOverridableValue = hasDefaultValue || hasEnvValue
  
  // Input should be disabled when override is off and there's a value to fall back to
  const isInputDisabled = disabled || (!overrideEnabled && hasOverridableValue)
  
  const displayValue = field.is_secret && !showSecret 
    ? value ? `${value.toString().substring(0, 4)}****${value.toString().slice(-4)}` : ''
    : typeof value === 'boolean' ? String(value) : (value || '')

  const renderInput = () => {
    const baseClasses = `
      block w-full rounded-md border-0 px-3 py-1.5 
      text-gray-900 dark:text-gray-100 shadow-sm 
      ring-1 ring-inset ring-gray-300 dark:ring-gray-600 
      placeholder:text-gray-400 dark:placeholder:text-gray-500
      focus:ring-2 focus:ring-inset focus:ring-indigo-600 dark:focus:ring-indigo-400
      disabled:bg-gray-50 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-400 disabled:cursor-not-allowed
      dark:bg-gray-700 sm:text-sm sm:leading-6
    `.trim()

    const inputProps = {
      id: field.name,
      name: field.name,
      required: field.required,
      disabled: isInputDisabled,
      className: baseClasses,
      placeholder: '',
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange(field.name, e.target.value)
    }

    switch (field.type) {
      case 'boolean':
        return (
          <input
            {...inputProps}
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(field.name, e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-600 disabled:bg-gray-50 dark:disabled:bg-gray-800 dark:bg-gray-700"
          />
        )
      case 'integer':
      case 'number':
        return (
          <input
            {...inputProps}
            type="number"
            step={field.type === 'number' ? 'any' : '1'}
            value={typeof value === 'boolean' ? String(value) : (value || '')}
            onChange={(e) => {
              const val = e.target.value
              if (val === '') {
                onChange(field.name, '')
              } else {
                const numVal = field.type === 'integer' ? parseInt(val, 10) : parseFloat(val)
                onChange(field.name, isNaN(numVal) ? val : numVal)
              }
            }}
          />
        )
      case 'string':
      default:
        if (field.is_secret) {
          return (
            <div className="relative">
              <input
                {...inputProps}
                type={showSecret ? 'text' : 'password'}
                value={displayValue}
                autoComplete="off"
              />
              {value && (
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 flex items-center pr-3"
                  onClick={() => setShowSecret(!showSecret)}
                  aria-label={showSecret ? 'Hide password' : 'Show password'}
                >
                  {showSecret ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              )}
            </div>
          )
        }
        return <input {...inputProps} type="text" value={typeof value === 'boolean' ? String(value) : (value || '')} />
    }
  }

  const formatValueForDisplay = (val: string | number | boolean | null | undefined, isSecret: boolean): string => {
    if (val === null || val === undefined) {
      return ''
    }
    
    const strValue = String(val)
    
    if (isSecret && strValue.length > 8) {
      // Show first 4 and last 4 characters with **** in between
      return `${strValue.substring(0, 4)}****${strValue.slice(-4)}`
    } else if (isSecret && strValue.length > 0) {
      // For shorter secrets, show first few characters with ****
      return `${strValue.substring(0, Math.min(2, strValue.length))}****`
    }
    
    return strValue
  }

  const renderValueSourceIndicator = () => {
    if (!hasOverridableValue) {
      return null
    }

    return (
      <div className="mt-2 space-y-1">
        {/* Show current fallback value */}
        {hasEnvValue && (
          <div className="text-xs text-gray-600 dark:text-gray-400">
            {field.env_var_name}: {formatValueForDisplay(field.env_value, field.is_secret)}
          </div>
        )}
        {hasDefaultValue && !hasEnvValue && (
          <div className="text-xs text-gray-600 dark:text-gray-400">
            Default: {formatValueForDisplay(field.default_value, field.is_secret)}
          </div>
        )}
        
        {/* Override status indicator */}
        {overrideEnabled && (
          <div className="flex items-center">
            <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 dark:text-amber-400 mr-1" />
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Overriding {hasEnvValue ? 'environment variable' : 'default value'}
            </span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label htmlFor={field.name} className="block text-sm font-medium leading-6 text-gray-900 dark:text-gray-100">
          {field.name.toUpperCase()}
          {field.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        
        {/* Override toggle - only show if field has overridable values */}
        {hasOverridableValue && !disabled && (
          <div className="flex items-center space-x-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">Override</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={overrideEnabled}
                onChange={(e) => onOverrideToggle(field.name, e.target.checked)}
              />
              <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>
        )}
      </div>
      
      {field.description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{field.description}</p>
      )}
      
      {renderInput()}
      {renderValueSourceIndicator()}
    </div>
  )
}