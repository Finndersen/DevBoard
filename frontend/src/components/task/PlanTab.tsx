import { useEditableField } from '../../hooks/useEditableField'
import { MarkdownDocumentEditor } from '../MarkdownDocumentEditor'
import type { DocumentResponse } from '../../lib/api'

interface PlanTabProps {
  implementationPlanDoc: DocumentResponse | null | undefined
  planField: ReturnType<typeof useEditableField<string>>
}

export function PlanTab({ implementationPlanDoc, planField }: PlanTabProps) {
  return (
    <MarkdownDocumentEditor
      content={implementationPlanDoc?.content}
      field={planField}
      placeholder="Enter implementation plan in Markdown format..."
      emptyText="No implementation plan provided."
    />
  )
}
