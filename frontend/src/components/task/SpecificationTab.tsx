import { useEditableField } from '../../hooks/useEditableField'
import { MarkdownDocumentEditor } from '../MarkdownDocumentEditor'
import type { DocumentResponse } from '../../lib/api'

interface SpecificationTabProps {
  specificationDoc: DocumentResponse | null | undefined
  specificationField: ReturnType<typeof useEditableField<string>>
}

export function SpecificationTab({ specificationDoc, specificationField }: SpecificationTabProps) {
  return (
    <MarkdownDocumentEditor
      content={specificationDoc?.content}
      field={specificationField}
      placeholder="Enter task specification in Markdown format..."
      emptyText="No task specification provided."
    />
  )
}
