import Modal from '../ui/Modal'
import Button from '../ui/Button'
import type { CustomFieldDefinition } from '../../lib/api'
import { textColors } from '../../styles/designSystem'

interface TaskCustomFieldsModalProps {
  isOpen: boolean
  onClose: () => void
  customFields: Record<string, unknown>
  fieldDefinitions: CustomFieldDefinition[]
}

export default function TaskCustomFieldsModal({
  isOpen,
  onClose,
  customFields,
  fieldDefinitions
}: TaskCustomFieldsModalProps) {
  if (!customFields || Object.keys(customFields).length === 0) return null

  const formatValue = (value: unknown): string => {
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No'
    }
    return String(value)
  }

  const getFieldDefinition = (fieldName: string): CustomFieldDefinition | undefined => {
    return fieldDefinitions.find(f => f.name === fieldName)
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Task Custom Fields"
      maxWidth="lg"
    >
      <div className="space-y-4">
        {/* Field List */}
        <div className="space-y-3">
          {Object.entries(customFields).map(([fieldName, value]) => {
            const fieldDef = getFieldDefinition(fieldName)
            const displayValue = formatValue(value)

            return (
              <div
                key={fieldName}
                className="flex items-start justify-between p-3 border border-gray-200 dark:border-gray-600 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className={`font-medium ${textColors.primary}`}>{fieldName}</span>
                    {fieldDef && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${getTypeBadgeColor(fieldDef.type)}`}>
                        {getTypeLabel(fieldDef.type)}
                      </span>
                    )}
                    {!fieldDef && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 italic">
                        Field deleted
                      </span>
                    )}
                  </div>
                  {fieldDef?.description && (
                    <p className={`mt-1 text-xs ${textColors.tertiary}`}>{fieldDef.description}</p>
                  )}
                </div>
                <div className="ml-4 flex-shrink-0">
                  <span className={fieldDef ? textColors.primary : `${textColors.tertiary} italic`}>
                    {displayValue}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Close button */}
        <div className="flex justify-end pt-2">
          <Button
            variant="ghost"
            onClick={onClose}
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function getTypeLabel(type: string): string {
  switch (type) {
    case 'text': return 'Text'
    case 'boolean': return 'Boolean'
    case 'enum': return 'Dropdown'
    default: return type
  }
}

function getTypeBadgeColor(type: string): string {
  switch (type) {
    case 'text': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
    case 'boolean': return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300'
    case 'enum': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
    default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
  }
}
