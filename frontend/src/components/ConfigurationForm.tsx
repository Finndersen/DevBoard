import React, { useState, useEffect } from 'react'
import { CheckCircleIcon, XCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../lib/api'
import type { ConfigurationDetailResponse } from '../lib/api'
import { ConfigurationField } from './ConfigurationField'

interface ConfigurationFormProps {
  configKey: string
  title: string
  onSave?: (data: ConfigurationDetailResponse) => void
  onTestConnection?: () => void
}

export const ConfigurationForm: React.FC<ConfigurationFormProps> = ({ 
  configKey, 
  title,
  onSave,
  onTestConnection
}) => {
  const [config, setConfig] = useState<ConfigurationDetailResponse | null>(null)
  const [values, setValues] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message?: string } | null>(null)

  useEffect(() => {
    loadConfiguration()
  }, [configKey])

  const loadConfiguration = async () => {
    try {
      setLoading(true)
      setError(null)
      setTestResult(null)  // Clear test result when loading new configuration
      const result = await apiClient.getConfigurationDetail(configKey)
      setConfig(result)
      
      // Initialize form values with current values
      const initialValues: Record<string, any> = {}
      result.fields.forEach(field => {
        initialValues[field.name] = field.current_value
      })
      setValues(initialValues)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleFieldChange = (fieldName: string, value: any) => {
    setValues(prev => ({ ...prev, [fieldName]: value }))
  }

  const handleSave = async () => {
    if (!config) return

    try {
      setSaving(true)
      setError(null)
      
      // Send all fields that have changed (allow overriding environment variables)
      const updatableFields: Record<string, any> = {}
      config.fields.forEach(field => {
        const newValue = values[field.name]
        if (newValue !== field.current_value) {
          // Convert empty strings to null for proper validation
          const processedValue = (typeof newValue === 'string' && newValue.trim() === '') ? null : newValue
          updatableFields[field.name] = processedValue
        }
      })

      if (Object.keys(updatableFields).length === 0) {
        setError('No changes to save')
        return
      }

      const result = await apiClient.updateConfigurationFields(configKey, updatableFields)
      setConfig(result)
      
      // Update form values with the result
      const newValues: Record<string, any> = {}
      result.fields.forEach(field => {
        newValues[field.name] = field.current_value
      })
      setValues(newValues)
      
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
      const integrationType = configKey.split('.')[1]
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

  const getStatusIndicator = () => {
    if (!config) return null

    switch (config.validation_status) {
      case 'valid':
        return (
          <div className="flex items-center text-green-600 dark:text-green-400">
            <CheckCircleIcon className="h-5 w-5 mr-1" />
            <span className="text-sm">Valid</span>
          </div>
        )
      case 'invalid':
        return (
          <div className="flex items-center text-red-600 dark:text-red-400">
            <XCircleIcon className="h-5 w-5 mr-1" />
            <span className="text-sm">Invalid</span>
          </div>
        )
      case 'unconfigured':
        return (
          <div className="flex items-center text-gray-600 dark:text-gray-400">
            <ExclamationCircleIcon className="h-5 w-5 mr-1" />
            <span className="text-sm">Unconfigured</span>
          </div>
        )
      default:
        return null
    }
  }

  const hasChanges = () => {
    if (!config) return false
    return config.fields.some(field => {
      const newValue = values[field.name]
      const currentValue = field.current_value
      
      // Convert empty strings to null for comparison
      const processedNewValue = (typeof newValue === 'string' && newValue.trim() === '') ? null : newValue
      const processedCurrentValue = (typeof currentValue === 'string' && currentValue.trim() === '') ? null : currentValue
      
      return processedNewValue !== processedCurrentValue
    })
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-10 bg-gray-200 rounded"></div>
            <div className="h-10 bg-gray-200 rounded"></div>
            <div className="h-10 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="p-6">
        <div className="text-center py-8">
          <XCircleIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">Configuration not found</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            The requested configuration could not be loaded.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl">
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
            onClick={loadConfiguration}
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  )
}