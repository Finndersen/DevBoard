import { useState } from 'react'
import { PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Modal, Button, Input } from '../ui'
import { textColors } from '../../styles/designSystem'
import { useEditableField } from '../../hooks/useEditableField'
import { apiClient } from '../../lib/api'
import type { MCPTool } from '../../lib/api'

interface ToolTestModalProps {
  isOpen: boolean
  onClose: () => void
  tool: MCPTool
  serverId: number
  onToolUpdate?: (tool: MCPTool) => void
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

export function ToolTestModal({ isOpen, onClose, tool, serverId, onToolUpdate }: ToolTestModalProps) {
  const schema = tool.input_schema as JSONSchema | null
  const properties = schema?.properties || {}
  const requiredFields = new Set(schema?.required || [])

  const [formData, setFormData] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    for (const [key, prop] of Object.entries(properties)) {
      if (prop.default != null) {
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

  const {
    isEditing: isEditingDesc,
    editedValue: editedDesc,
    setEditedValue: setEditedDesc,
    saving: savingDesc,
    error: descError,
    startEditing: startEditingDesc,
    cancelEditing: cancelEditingDesc,
    save: saveDesc
  } = useEditableField(tool.description || '', async (value) => {
    const updated = await apiClient.updateMCPTool(serverId, tool.id, { description: value || null })
    onToolUpdate?.(updated)
  })

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

  // Sort properties: required fields first, then optional
  const propertyEntries = Object.entries(properties).sort(([keyA], [keyB]) => {
    const aRequired = requiredFields.has(keyA)
    const bRequired = requiredFields.has(keyB)
    if (aRequired && !bRequired) return -1
    if (!aRequired && bRequired) return 1
    return 0
  })

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={tool.name}
      maxWidth="7xl"
      scrollable={false}
    >
      <div className="flex flex-col flex-1 min-h-0">
        {/* Description — full-width at the top */}
        <div className="border border-gray-200 dark:border-white/[0.08] rounded-lg p-3 mb-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className={`text-xs font-medium uppercase tracking-wide ${textColors.secondary}`}>Description</h4>
            {!isEditingDesc && (
              <button
                onClick={startEditingDesc}
                className="p-1 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors"
                title="Edit description"
              >
                <PencilIcon className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          {isEditingDesc ? (
            <div>
              <textarea
                value={editedDesc}
                onChange={(e) => setEditedDesc(e.target.value)}
                className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                rows={Math.min(12, Math.max(2, editedDesc.split('\n').length + 1))}
                disabled={savingDesc}
              />
              {descError && <p className="text-xs text-red-500 mt-1">{descError}</p>}
              <div className="flex gap-1 mt-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={saveDesc}
                  loading={savingDesc}
                  icon={<CheckIcon className="w-3 h-3" />}
                >
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={cancelEditingDesc}
                  disabled={savingDesc}
                  icon={<XMarkIcon className="w-3 h-3" />}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <p className={`text-sm ${textColors.secondary} whitespace-pre-line`}>
              {tool.description || <span className="italic">No description</span>}
            </p>
          )}
        </div>

        {/* Test Tool section — parameters + results side-by-side */}
        <div className="border border-gray-200 dark:border-white/[0.08] rounded-lg p-4 flex-1 min-h-0 flex flex-col">
          <h4 className={`text-sm font-medium ${textColors.primary} mb-3 shrink-0`}>Test Tool</h4>
          <div className="flex gap-6 flex-1 min-h-0">
            <form onSubmit={handleSubmit} className="flex flex-col w-2/5 min-w-0 shrink-0 min-h-0">
              {/* Parameters */}
              <div className="flex-1 min-h-0 flex flex-col">
                <h4 className={`text-xs font-medium uppercase tracking-wide ${textColors.secondary} mb-2 shrink-0`}>Parameters</h4>
                {propertyEntries.length === 0 ? (
                  <p className={`text-sm ${textColors.secondary} italic`}>
                    This tool has no input parameters.
                  </p>
                ) : (
                  <div className="space-y-4 overflow-y-auto flex-1 min-h-0 pr-2">
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
              </div>

              <div className="flex justify-end pt-4 mt-4 shrink-0">
                <Button type="submit" loading={loading}>
                  Run
                </Button>
              </div>
            </form>

            {/* Result */}
            <div className="flex-1 min-w-0 border-l border-gray-200 dark:border-white/[0.08] pl-6">
              <h4 className={`text-xs font-medium uppercase tracking-wide ${textColors.secondary} mb-2`}>
                {error ? 'Error' : 'Result'}
              </h4>
              {error ? (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                  <pre className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap font-mono">
                    {error}
                  </pre>
                </div>
              ) : result !== null ? (
                <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] rounded-md max-h-[60vh] overflow-auto">
                  <pre className={`text-sm ${textColors.primary} whitespace-pre-wrap font-mono`}>
                    {result || '(empty response)'}
                  </pre>
                </div>
              ) : (
                <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] rounded-md">
                  <p className={`text-sm ${textColors.secondary} italic`}>
                    Run the tool to see results here
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}
