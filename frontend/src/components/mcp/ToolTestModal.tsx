import { useState } from 'react'
import { Modal, Button, Input } from '../ui'
import { textColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { MCPTool } from '../../lib/api'

interface ToolTestModalProps {
  isOpen: boolean
  onClose: () => void
  tool: MCPTool
  serverId: number
}

interface JSONSchemaProperty {
  type?: string
  description?: string
  default?: unknown
}

interface JSONSchema {
  type?: string
  properties?: Record<string, JSONSchemaProperty>
  required?: string[]
}

function getInputType(schemaType: string | undefined): string {
  switch (schemaType) {
    case 'number':
    case 'integer':
      return 'number'
    case 'boolean':
      return 'checkbox'
    default:
      return 'text'
  }
}

function parseValue(value: string, schemaType: string | undefined): unknown {
  if (value === '') return undefined
  switch (schemaType) {
    case 'number':
      return parseFloat(value)
    case 'integer':
      return parseInt(value, 10)
    case 'boolean':
      return value === 'true'
    default:
      return value
  }
}

export function ToolTestModal({ isOpen, onClose, tool, serverId }: ToolTestModalProps) {
  const schema = tool.input_schema as JSONSchema | null
  const properties = schema?.properties || {}
  const requiredFields = new Set(schema?.required || [])

  const [formData, setFormData] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    for (const [key, prop] of Object.entries(properties)) {
      if (prop.default !== undefined) {
        initial[key] = String(prop.default)
      } else {
        initial[key] = ''
      }
    }
    return initial
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    setError(null)
    setResult(null)
  }

  const handleCheckboxChange = (field: string, checked: boolean) => {
    setFormData(prev => ({ ...prev, [field]: String(checked) }))
    setError(null)
    setResult(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)

    // Build arguments object, only including fields with values
    const args: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(formData)) {
      const prop = properties[key]
      const parsed = parseValue(value, prop?.type)
      if (parsed !== undefined) {
        args[key] = parsed
      }
    }

    try {
      const response = await apiClient.runMCPTool(serverId, tool.id, {
        arguments: Object.keys(args).length > 0 ? args : undefined
      })

      if (response.success) {
        setResult(response.result ?? '')
      } else {
        setError(response.error ?? 'Unknown error')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run tool')
    } finally {
      setLoading(false)
    }
  }

  const propertyEntries = Object.entries(properties)

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Test: ${tool.name}`}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {tool.description && (
          <p className={`text-sm ${textColors.secondary}`}>{tool.description}</p>
        )}

        {propertyEntries.length === 0 ? (
          <p className={`text-sm ${textColors.secondary} italic`}>
            This tool has no input parameters.
          </p>
        ) : (
          <div className="space-y-4">
            {propertyEntries.map(([key, prop]) => {
              const inputType = getInputType(prop.type)
              const isRequired = requiredFields.has(key)

              if (inputType === 'checkbox') {
                return (
                  <div key={key} className="flex items-center gap-3">
                    <input
                      id={`field-${key}`}
                      type="checkbox"
                      checked={formData[key] === 'true'}
                      onChange={(e) => handleCheckboxChange(key, e.target.checked)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      disabled={loading}
                    />
                    <label
                      htmlFor={`field-${key}`}
                      className={`text-sm font-medium ${textColors.primary}`}
                    >
                      {key}
                      {isRequired && <span className="text-red-500 ml-1">*</span>}
                    </label>
                    {prop.description && (
                      <span className={`text-sm ${textColors.secondary}`}>
                        — {prop.description}
                      </span>
                    )}
                  </div>
                )
              }

              return (
                <Input
                  key={key}
                  label={isRequired ? `${key} *` : key}
                  type={inputType}
                  value={formData[key] || ''}
                  onChange={(e) => handleChange(key, e.target.value)}
                  helpText={prop.description}
                  disabled={loading}
                  required={isRequired}
                />
              )
            })}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <Button type="submit" loading={loading}>
            Run
          </Button>
        </div>

        {(result !== null || error) && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
            <h4 className={`text-sm font-medium ${textColors.primary} mb-2`}>
              {error ? 'Error' : 'Result'}
            </h4>
            {error ? (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                <pre className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap font-mono">
                  {error}
                </pre>
              </div>
            ) : (
              <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md max-h-64 overflow-auto">
                <pre className={`text-sm ${textColors.primary} whitespace-pre-wrap font-mono`}>
                  {result || '(empty response)'}
                </pre>
              </div>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
