import React, { useState } from 'react'
import { EyeIcon, EyeSlashIcon, LockClosedIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import type { ConfigurationFieldInfo } from '../lib/api'

interface ConfigurationFieldProps {
  field: ConfigurationFieldInfo
  value: any
  onChange: (fieldName: string, value: any) => void
  disabled?: boolean
}

export const ConfigurationField: React.FC<ConfigurationFieldProps> = ({ 
  field, 
  value, 
  onChange, 
  disabled = false 
}) => {
  const [showSecret, setShowSecret] = useState(false)
  
  const isReadOnly = field.value_source === 'environment' || disabled
  const isOverridingEnv = field.value_source === 'database' && field.env_value_present
  const isDefault = field.value_source === 'default'
  
  const displayValue = field.is_secret && !showSecret 
    ? value ? `${value.toString().substring(0, 4)}****${value.toString().slice(-4)}` : ''
    : value || ''

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
      disabled: isReadOnly,
      className: baseClasses,
      placeholder: isDefault && field.default_value ? `Default: ${field.default_value}` : '',
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
            value={value || ''}
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
        return <input {...inputProps} type="text" value={value || ''} />
    }
  }

  const renderValueSourceIndicator = () => {
    if (field.value_source === 'environment') {
      return (
        <div className="flex items-center mt-1">
          <LockClosedIcon className="h-4 w-4 text-gray-500 dark:text-gray-400 mr-1" />
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Set via {field.env_var_name}
          </span>
        </div>
      )
    }

    if (isOverridingEnv) {
      return (
        <div className="flex items-center mt-1">
          <ExclamationTriangleIcon className="h-4 w-4 text-amber-500 dark:text-amber-400 mr-1" />
          <span className="text-xs text-amber-600 dark:text-amber-400">
            Overriding {field.env_var_name}
          </span>
          <button
            type="button"
            className="ml-2 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
            onClick={() => onChange(field.name, null)}
          >
            Reset to environment
          </button>
        </div>
      )
    }

    if (isDefault && field.default_value !== null && field.default_value !== undefined) {
      return (
        <div className="mt-1">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Using default: {String(field.default_value)}
          </span>
        </div>
      )
    }

    return null
  }

  return (
    <div className="space-y-1">
      <label htmlFor={field.name} className="block text-sm font-medium leading-6 text-gray-900 dark:text-gray-100">
        {field.name}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      
      {field.description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{field.description}</p>
      )}
      
      {renderInput()}
      {renderValueSourceIndicator()}
    </div>
  )
}