import { MarkdownDocumentEditor } from '../MarkdownDocumentEditor'
import type { DocumentResponse } from '../../lib/api'

interface SummaryTabProps {
  changeSummaryDoc: DocumentResponse | null | undefined
}

export function SummaryTab({ changeSummaryDoc }: SummaryTabProps) {
  return (
    <MarkdownDocumentEditor
      content={changeSummaryDoc?.content}
      emptyText="No change summary available yet."
    />
  )
}
