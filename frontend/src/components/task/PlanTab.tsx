import { useEditableField } from '../../hooks/useEditableField'
import { Textarea, Markdown } from '../ui'
import { textColors } from '../../styles/designSystem'
import type { DocumentResponse } from '../../lib/api'

interface PlanTabProps {
  implementationPlanDoc: DocumentResponse | null | undefined
  planField: ReturnType<typeof useEditableField<string>>
}

export function PlanTab({ implementationPlanDoc, planField }: PlanTabProps) {
  return (
    <div className="h-full flex flex-col">
      {planField.isEditing ? (
        <Textarea
          value={planField.editedValue}
          onChange={(e) => planField.setEditedValue(e.target.value)}
          fillHeight={true}
          placeholder="Enter implementation plan in Markdown format..."
        />
      ) : (
        <div className="h-full overflow-y-auto">
          {implementationPlanDoc?.content ? (
            <Markdown>{implementationPlanDoc.content}</Markdown>
          ) : (
            <p className={`${textColors.secondary} italic`}>No implementation plan provided. Click Edit to add plan.</p>
          )}
        </div>
      )}
    </div>
  )
}
