import { CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'

interface ConfigurationStatus {
  isValid: boolean
  errors?: string[]
}

interface ConfigurationListItemProps {
  configKey: string
  title: string
  isSelected: boolean
  status?: ConfigurationStatus
  onSelect: (configKey: string) => void
}

export function ConfigurationListItem({
  configKey,
  title,
  isSelected,
  status,
  onSelect
}: ConfigurationListItemProps) {
  return (
    <button
      onClick={() => onSelect(configKey)}
      className={`w-full px-6 py-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700 ${
        isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
          {title}
        </h4>
        {status && (
          status.isValid ? (
            <CheckCircleIcon className="w-4 h-4 text-green-500" title="Configuration is valid" />
          ) : (
            <ExclamationCircleIcon 
              className="w-4 h-4 text-red-500" 
              title={`Invalid: ${status.errors?.join(', ') || 'Configuration errors'}`} 
            />
          )
        )}
      </div>
    </button>
  )
}