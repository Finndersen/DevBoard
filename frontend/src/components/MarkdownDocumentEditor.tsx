import { useRef, useMemo } from 'react'
import { CheckIcon, PencilIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { useEditableField } from '../hooks/useEditableField'
import { Button, Textarea, Markdown } from './ui'
import TableOfContentsPopover from './ui/TableOfContentsPopover'
import { textColors } from '../styles/designSystem'
import { extractHeadings } from '../utils/markdown'

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
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const headings = useMemo(() => extractHeadings(content ?? ''), [content])

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
          <div className="h-full overflow-y-auto" ref={scrollContainerRef}>
            {content ? (
              <Markdown>{content}</Markdown>
            ) : (
              <p className={`${textColors.secondary} italic`}>{emptyText}</p>
            )}
          </div>
          {(headings.length >= 2 || field) && (
            <div className="absolute top-2 right-5 flex items-center gap-2 z-10">
              {headings.length >= 2 && (
                <TableOfContentsPopover
                  headings={headings}
                  scrollContainerRef={scrollContainerRef}
                />
              )}
              {field && (
                <button
                  onClick={field.startEditing}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] shadow-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors text-gray-600 dark:text-gray-400"
                >
                  <PencilIcon className="w-3.5 h-3.5" />
                  <span>Edit</span>
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
