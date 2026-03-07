import { useEditableField } from '../../hooks/useEditableField'
import { Textarea, Markdown } from '../ui'
import { textColors } from '../../styles/designSystem'
import type { DocumentResponse } from '../../lib/api'

interface SpecificationTabProps {
  specificationDoc: DocumentResponse | null | undefined
  specificationField: ReturnType<typeof useEditableField<string>>
}

export function SpecificationTab({ specificationDoc, specificationField }: SpecificationTabProps) {
  return (
    <div className="h-full flex flex-col">
      {specificationField.isEditing ? (
        <Textarea
          value={specificationField.editedValue}
          onChange={(e) => specificationField.setEditedValue(e.target.value)}
          fillHeight={true}
          placeholder="Enter task specification in Markdown format..."
        />
      ) : (
        <div className="h-full overflow-y-auto">
          {specificationDoc?.content ? (
            <Markdown>{specificationDoc.content}</Markdown>
          ) : (
            <p className={`${textColors.secondary} italic`}>No task specification provided. Click Edit to add specification.</p>
          )}
        </div>
      )}
    </div>
  )
}
