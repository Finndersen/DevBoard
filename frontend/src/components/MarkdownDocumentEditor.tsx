import { CheckIcon, PencilIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { useEditableField } from '../hooks/useEditableField'
import { Button, Textarea, Markdown } from './ui'
import { textColors } from '../styles/designSystem'

interface MarkdownDocumentEditorProps {
  content: string | null | undefined
  field?: ReturnType<typeof useEditableField<string>>
  placeholder?: string
  emptyText?: string
  textareaClassName?: string
}

export function MarkdownDocumentEditor({
  content,
  field,
  placeholder = 'Enter content in Markdown format...',
  emptyText = 'No content provided.',
  textareaClassName,
}: MarkdownDocumentEditorProps) {
  return (
    <div className="h-full flex flex-col relative">
      {field?.isEditing ? (
        <>
          <Textarea
            value={field.editedValue}
            onChange={(e) => field.setEditedValue(e.target.value)}
            fillHeight={true}
            placeholder={placeholder}
            className={textareaClassName}
          />
          <div className="absolute bottom-3 right-3 flex items-center space-x-2">
            <Button
              onClick={field.save}
              variant="primary"
              size="sm"
              loading={field.saving}
              icon={<CheckIcon className="w-4 h-4" />}
            >
              Save
            </Button>
            <Button
              onClick={field.cancelEditing}
              variant="secondary"
              size="sm"
              icon={<XMarkIcon className="w-4 h-4" />}
            >
              Cancel
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="h-full overflow-y-auto">
            {content ? (
              <Markdown>{content}</Markdown>
            ) : (
              <p className={`${textColors.secondary} italic`}>{emptyText}</p>
            )}
          </div>
          {field && (
            <button
              onClick={field.startEditing}
              className="absolute bottom-3 right-3 flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors text-gray-600 dark:text-gray-400"
            >
              <PencilIcon className="w-3.5 h-3.5" />
              <span>Edit</span>
            </button>
          )}
        </>
      )}
    </div>
  )
}
