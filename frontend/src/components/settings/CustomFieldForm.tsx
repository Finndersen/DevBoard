import { useState, useEffect } from 'react'
import { PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Button, Input } from '../ui'
import type { CustomFieldDefinition, CustomFieldCreate, CustomFieldUpdate, CustomFieldType, CustomFieldEntityType } from '../../lib/api'
import { statusColors, borderColors } from '../../styles/designSystem'

interface CustomFieldFormProps {
  field: CustomFieldDefinition | null
  entityType: CustomFieldEntityType
  onSubmit: (data: CustomFieldCreate | CustomFieldUpdate) => Promise<void>
  onCancel: () => void
  isSaving: boolean
}

export function CustomFieldForm({ field, entityType, onSubmit, onCancel, isSaving }: CustomFieldFormProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState<CustomFieldType>('text')
  const [options, setOptions] = useState<string[]>([])
  const [newOption, setNewOption] = useState('')
  const [mandatory, setMandatory] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Initialize form when editing
  useEffect(() => {
    if (field) {
      setName(field.name)
      setDescription(field.description || '')
      setType(field.type)
      setOptions(field.options || [])
      setMandatory(field.mandatory)
    } else {
      setName('')
      setDescription('')
      setType('text')
      setOptions([])
      setMandatory(false)
    }
    setError(null)
  }, [field])

  const handleAddOption = () => {
    const trimmed = newOption.trim()
    if (trimmed && !options.includes(trimmed)) {
      setOptions(prev => [...prev, trimmed])
      setNewOption('')
    }
  }

  const handleRemoveOption = (optionToRemove: string) => {
    setOptions(prev => prev.filter(opt => opt !== optionToRemove))
  }

  const handleOptionKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddOption()
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validate
    if (!name.trim()) {
      setError('Name is required')
      return
    }

    if (type === 'enum' && options.length === 0) {
      setError('At least one option is required for dropdown fields')
      return
    }

    const data: CustomFieldCreate | CustomFieldUpdate = {
      name: name.trim(),
      description: description.trim() || null,
      type,
      options: type === 'enum' ? options : null,
      mandatory,
    }

    try {
      await onSubmit(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save field')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className={`p-3 ${statusColors.error.bg} ${statusColors.error.text} rounded-md text-sm`}>
          {error}
        </div>
      )}

      <Input
        label="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g., priority, jira_issue_id"
        required
        helpText="A unique identifier for this field"
      />

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 dark:bg-white/[0.06] dark:text-white resize-none"
          placeholder="Help text describing what this field is for"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Optional description shown to users when filling out this field
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Field Type
        </label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value as CustomFieldType)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 dark:bg-white/[0.06] dark:text-white"
        >
          <option value="text">Text - Free-form text input</option>
          <option value="boolean">Boolean - Toggle switch (yes/no)</option>
          <option value="enum">Dropdown - Select from predefined options</option>
        </select>
      </div>

      {type === 'enum' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Options
          </label>
          <div className="flex space-x-2 mb-2">
            <input
              type="text"
              value={newOption}
              onChange={(e) => setNewOption(e.target.value)}
              onKeyDown={handleOptionKeyDown}
              placeholder="Add an option..."
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white text-gray-900 dark:bg-white/[0.06] dark:text-white"
            />
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={handleAddOption}
              disabled={!newOption.trim()}
            >
              <PlusIcon className="w-4 h-4" />
            </Button>
          </div>

          {options.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {options.map((option) => (
                <span
                  key={option}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 dark:bg-white/[0.05] text-gray-800 dark:text-gray-200"
                >
                  {option}
                  <button
                    type="button"
                    onClick={() => handleRemoveOption(option)}
                    className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
                    <XMarkIcon className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {options.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No options added yet. Add at least one option for the dropdown.
            </p>
          )}
        </div>
      )}

      <div className="flex items-center justify-between py-2">
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">Required Field</h4>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Make this field mandatory when creating new {entityType === 'task' ? 'tasks' : entityType === 'project' ? 'projects' : `${entityType}s`}
          </p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            className="sr-only peer"
            checked={mandatory}
            onChange={(e) => setMandatory(e.target.checked)}
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-500 peer-checked:bg-blue-600"></div>
        </label>
      </div>

      <div className={`flex justify-end space-x-3 pt-4 border-t ${borderColors.default}`}>
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={isSaving}>
          {field ? 'Save Changes' : 'Create Field'}
        </Button>
      </div>
    </form>
  )
}
