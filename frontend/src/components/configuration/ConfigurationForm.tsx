import React, { useState, useEffect } from 'react'
import { CheckCircleIcon, XCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../../lib/api'
import type { ConfigurationDetailResponse } from '../../lib/api'
import { ConfigurationField } from './ConfigurationField'

interface ConfigurationFormProps {
  config: ConfigurationDetailResponse
  title: string
  onSave?: (data: ConfigurationDetailResponse) => void
  onTestConnection?: () => void
}

type ConfigValue = string | number | boolean | null

// Type guard to ensure unknown values are valid configuration values
const toConfigValue = (value: unknown): ConfigValue => {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value
  }
  // Fallback for unexpected types
  return String(value)
}

export const ConfigurationForm: React.FC<ConfigurationFormProps> = ({
  config,
  title,
  onSave,
  onTestConnection
}) => {
  const [values, setValues] = useState<Record<string, ConfigValue>>({})
  const [overrideStates, setOverrideStates] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message?: string } | null>(null)

  useEffect(() => {
    // Initialize form values when config changes
    setError(null)
    setTestResult(null)  // Clear test result when config changes

    const initialValues: Record<string, ConfigValue> = {}
    const initialOverrideStates: Record<string, boolean> = {}
    config.fields.forEach(field => {
      initialValues[field.name] = toConfigValue(field.effective_value)
      initialOverrideStates[field.name] = field.is_overridden
    })
    setValues(initialValues)
    setOverrideStates(initialOverrideStates)
  }, [config])

  const handleFieldChange = (fieldName: string, value: string | number | boolean | null) => {
    setValues(prev => ({ ...prev, [fieldName]: value }))
  }

  const handleOverrideToggle = (fieldName: string, enabled: boolean) => {
    setOverrideStates(prev => ({ ...prev, [fieldName]: enabled }))

    if (config) {
      const field = config.fields.find(f => f.name === fieldName)
      if (field) {
        if (enabled) {
          // When enabling override, populate with effective value
          setValues(prev => ({ ...prev, [fieldName]: toConfigValue(field.effective_value) }))
        } else {
          // When disabling override, reset to effective value (which is the fallback when not overridden)
          setValues(prev => ({ ...prev, [fieldName]: toConfigValue(field.effective_value) }))
        }
      }
    }
  }

  const handleSave = async () => {
    if (!config) return

    try {
      setSaving(true)
      setError(null)

      // Send only fields where override is enabled or override state has changed
      const updatableFields: Record<string, ConfigValue> = {}
      config.fields.forEach(field => {
        const isOverrideEnabled = overrideStates[field.name]
        const wasOverridden = field.is_overridden

        if (isOverrideEnabled) {
          // Override is enabled - send the current value
          const newValue = values[field.name]
          const processedValue = (typeof newValue === 'string' && newValue.trim() === '') ? null : newValue
          updatableFields[field.name] = processedValue
        } else if (wasOverridden && !isOverrideEnabled) {
          // Override was disabled - send null to clear the database override
          updatableFields[field.name] = null
        }
      })

      if (Object.keys(updatableFields).length === 0) {
        setError('No changes to save')
        return
      }

      const result = await apiClient.updateConfigurationFields(config.key, updatableFields)

      // Update form values and override states with the result
      const newValues: Record<string, ConfigValue> = {}
      const newOverrideStates: Record<string, boolean> = {}
      result.fields.forEach(field => {
        newValues[field.name] = toConfigValue(field.effective_value)
        newOverrideStates[field.name] = field.is_overridden
      })
      setValues(newValues)
      setOverrideStates(newOverrideStates)

      onSave?.(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    if (!onTestConnection) return

    try {
      setTesting(true)
      setTestResult(null)
      
      // Extract integration type from config key (e.g., 'integration.github.main' -> 'github')
      const integrationType = config.key.split('.')[1]
      const result = await apiClient.testIntegrationConnection(integrationType)
      
      setTestResult({
        success: result.success,
        message: result.success ? 'Connection successful' : result.error_message
      })
      
      onTestConnection()
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : 'Connection test failed'
      })
    } finally {
      setTesting(false)
    }
  }

  const resetForm = () => {
    // Reset form values to original config values
    setError(null)
    setTestResult(null)

    const initialValues: Record<string, ConfigValue> = {}
    const initialOverrideStates: Record<string, boolean> = {}
    config.fields.forEach(field => {
      initialValues[field.name] = toConfigValue(field.effective_value)
      initialOverrideStates[field.name] = field.is_overridden
    })
    setValues(initialValues)
    setOverrideStates(initialOverrideStates)
  }

  const getStatusIndicator = () => {
    if (config.is_valid) {
      return (
        <div className="flex items-center text-green-600 dark:text-green-400">
          <CheckCircleIcon className="h-5 w-5 mr-1" />
          <span className="text-sm">Valid</span>
        </div>
      )
    } else {
      return (
        <div className="flex items-center text-red-600 dark:text-red-400">
          <XCircleIcon className="h-5 w-5 mr-1" />
          <span className="text-sm">Invalid</span>
        </div>
      )
    }
  }

  const hasChanges = () => {
    return config.fields.some(field => {
      const isOverrideEnabled = overrideStates[field.name]
      const wasOverridden = field.is_overridden

      // Check if override state changed
      if (isOverrideEnabled !== wasOverridden) {
        // Only consider it a change if:
        // 1. Enabling override, OR
        // 2. Disabling override but there was actually a db_value to clear
        return isOverrideEnabled || (wasOverridden && field.db_value !== null && field.db_value !== undefined)
      }

      // Check if value changed for overridden fields
      if (isOverrideEnabled) {
        const newValue = values[field.name]
        const dbValue = toConfigValue(field.db_value)

        // Convert empty strings to null for comparison
        const processedNewValue = (typeof newValue === 'string' && newValue.trim() === '') ? null : newValue
        const processedDbValue = (typeof dbValue === 'string' && dbValue.trim() === '') ? null : dbValue

        return processedNewValue !== processedDbValue
      }

      return false
    })
  }


  return (
    <div className="p-6 max-w-full lg:max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100">{title}</h2>
        {getStatusIndicator()}
      </div>

      {error && (
        <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-4">
          <div className="flex">
            <XCircleIcon className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          </div>
        </div>
      )}

      {config.validation_errors && config.validation_errors.length > 0 && (
        <div className="mb-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md p-4">
          <div className="flex">
            <ExclamationCircleIcon className="h-5 w-5 text-yellow-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">Configuration Issues:</p>
              <ul className="mt-2 text-sm text-yellow-700 dark:text-yellow-300 list-disc list-inside">
                {config.validation_errors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {testResult && (
        <div className={`mb-4 border rounded-md p-4 ${
          testResult.success 
            ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' 
            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
        }`}>
          <div className="flex">
            {testResult.success ? (
              <CheckCircleIcon className="h-5 w-5 text-green-400" />
            ) : (
              <XCircleIcon className="h-5 w-5 text-red-400" />
            )}
            <div className="ml-3">
              <p className={`text-sm font-medium ${
                testResult.success 
                  ? 'text-green-800 dark:text-green-200' 
                  : 'text-red-800 dark:text-red-200'
              }`}>
                Connection Test {testResult.success ? 'Successful' : 'Failed'}
              </p>
              {testResult.message && (
                <p className={`mt-1 text-sm ${
                  testResult.success 
                    ? 'text-green-600 dark:text-green-300' 
                    : 'text-red-600 dark:text-red-300'
                }`}>
                  {testResult.message}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <form className="space-y-6">
        {config.fields.map((field) => (
          <ConfigurationField
            key={field.name}
            field={field}
            value={values[field.name]}
            onChange={handleFieldChange}
            overrideEnabled={overrideStates[field.name] || false}
            onOverrideToggle={handleOverrideToggle}
          />
        ))}

        <div className="flex items-center justify-between pt-4">
          <div className="flex space-x-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !hasChanges()}
              className="bg-indigo-600 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>

            {onTestConnection && (
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testing}
                className="bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              >
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={resetForm}
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  )
}