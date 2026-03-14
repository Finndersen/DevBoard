import { useState, useRef, useEffect } from 'react'
import { TagIcon } from '@heroicons/react/24/outline'
import type { CustomFieldDefinition } from '../../lib/api'
import { textColors } from '../../styles/designSystem'

interface CustomFieldsPopoverProps {
  customFields: Record<string, unknown> | null
  fieldDefinitions: CustomFieldDefinition[]
  onFieldChange: (fieldName: string, value: unknown) => Promise<void>
  saving?: boolean
}

export function CustomFieldsPopover({
  customFields,
  fieldDefinitions,
  onFieldChange,
  saving,
}: CustomFieldsPopoverProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState<string>('')
  const [savingField, setSavingField] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  const fieldCount = customFields ? Object.keys(customFields).length : 0
  const hasDefinitions = fieldDefinitions.length > 0

  // Hide button entirely when no fields and no definitions
  if (!hasDefinitions && fieldCount === 0) return null

  const allFieldNames = new Set([
    ...fieldDefinitions.map(d => d.name),
    ...Object.keys(customFields || {}),
  ])

  const getDefinition = (name: string) => fieldDefinitions.find(d => d.name === name)

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined || value === '') return '—'
    if (typeof value === 'boolean') return value ? 'Yes' : 'No'
    return String(value)
  }

  const handleTextEdit = (fieldName: string, currentValue: unknown) => {
    setEditingField(fieldName)
    setEditValue(String(currentValue ?? ''))
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleTextSave = async (fieldName: string) => {
    try {
      await onFieldChange(fieldName, editValue || null)
      setEditingField(null)
    } catch {
      // Keep editing state so user doesn't lose their input
    }
  }

  const handleBooleanChange = async (fieldName: string, value: boolean) => {
    if (savingField === fieldName) return
    setSavingField(fieldName)
    try {
      await onFieldChange(fieldName, value)
    } finally {
      setSavingField(null)
    }
  }

  const handleEnumChange = async (fieldName: string, value: string) => {
    if (savingField === fieldName) return
    setSavingField(fieldName)
    try {
      await onFieldChange(fieldName, value || null)
    } finally {
      setSavingField(null)
    }
  }

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setEditingField(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false)
        setEditingField(null)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  return (
    <div className="relative" ref={popoverRef}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(prev => !prev)}
        className={`flex items-center space-x-1.5 px-2 py-1 rounded text-sm border transition-colors ${
          isOpen
            ? 'border-blue-400 bg-blue-50 text-blue-600 dark:border-blue-500 dark:bg-blue-900/30 dark:text-blue-400'
            : `border-gray-300 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800 ${textColors.secondary}`
        }`}
        title={isOpen ? 'Hide custom fields' : 'Show custom fields'}
      >
        <TagIcon className="w-4 h-4" />
        {fieldCount > 0 && (
          <span className="text-xs">{fieldCount}</span>
        )}
      </button>

      {/* Popover Panel */}
      {isOpen && allFieldNames.size > 0 && (
        <div className="absolute right-0 top-full mt-1 z-20 w-72 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
          <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-700">
            <span className={`text-xs font-semibold uppercase tracking-wide ${textColors.secondary}`}>Custom Fields</span>
          </div>
          <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
            {Array.from(allFieldNames).map(fieldName => {
              const def = getDefinition(fieldName)
              const value = (customFields || {})[fieldName]
              const isOrphaned = !def

              return (
                <div key={fieldName} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <span className={`text-xs font-medium shrink-0 mr-3 ${textColors.secondary}`}>
                    {fieldName}
                  </span>

                  <div className="flex items-center min-w-0">
                    {isOrphaned ? (
                      <span className={`text-xs italic ${textColors.tertiary}`} title="Field definition deleted">
                        {formatValue(value)}
                      </span>
                    ) : def.type === 'boolean' ? (
                      <label className="relative inline-flex items-center cursor-pointer" title={savingField === fieldName ? 'Saving...' : undefined}>
                        <input
                          type="checkbox"
                          className="sr-only peer"
                          checked={(value as boolean) || false}
                          onChange={(e) => handleBooleanChange(fieldName, e.target.checked)}
                          disabled={saving || savingField === fieldName}
                        />
                        <div className="w-8 h-4 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-gray-500 peer-checked:bg-blue-600"></div>
                      </label>
                    ) : def.type === 'enum' ? (
                      <select
                        value={(value as string) || ''}
                        onChange={(e) => handleEnumChange(fieldName, e.target.value)}
                        disabled={saving || savingField === fieldName}
                        className="text-xs px-1 py-0.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white max-w-[140px] truncate"
                      >
                        <option value="">—</option>
                        {def.options?.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : editingField === fieldName ? (
                      <input
                        ref={inputRef}
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => handleTextSave(fieldName)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleTextSave(fieldName)
                          if (e.key === 'Escape') {
                            setEditingField(null)
                            e.stopPropagation()
                          }
                        }}
                        className="text-xs px-1 py-0.5 border border-blue-400 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white min-w-0 w-full max-w-[140px]"
                      />
                    ) : (
                      <button
                        onClick={() => handleTextEdit(fieldName, value)}
                        disabled={saving}
                        className={`text-xs truncate hover:underline cursor-text text-left ${
                          value ? textColors.primary : textColors.tertiary
                        } max-w-[140px]`}
                        title={value ? String(value) : 'Click to edit'}
                      >
                        {formatValue(value)}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
