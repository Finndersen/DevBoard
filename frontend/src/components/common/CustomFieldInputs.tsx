import { Input } from '../ui'
import type { CustomFieldDefinition } from '../../lib/api'

interface CustomFieldInputsProps {
  definitions: CustomFieldDefinition[]
  values: Record<string, unknown>
  onChange: (fieldName: string, value: unknown) => void
  loading?: boolean
}

export function CustomFieldInputs({ definitions, values, onChange, loading }: CustomFieldInputsProps) {
  if (loading || definitions.length === 0) return null

  return (
    <div className="border-t border-gray-200 dark:border-white/[0.08] pt-4">
      <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Custom Fields</h4>
      <div className="space-y-4">
        {definitions.map(field => (
          <div key={field.id}>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {field.name}
              {field.mandatory && <span className="text-red-500 ml-1">*</span>}
            </label>
            {field.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">{field.description}</p>
            )}

            {field.type === 'text' && (
              <Input
                type="text"
                value={(values[field.name] as string) || ''}
                onChange={(e) => onChange(field.name, e.target.value)}
                placeholder={`Enter ${field.name}`}
              />
            )}

            {field.type === 'boolean' && (
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={(values[field.name] as boolean) || false}
                  onChange={(e) => onChange(field.name, e.target.checked)}
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-500 peer-checked:bg-blue-600"></div>
              </label>
            )}

            {field.type === 'enum' && field.options && (
              <select
                value={(values[field.name] as string) || ''}
                onChange={(e) => onChange(field.name, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white"
              >
                <option value="">Select {field.name}</option>
                {field.options.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
