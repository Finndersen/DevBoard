import type { DocumentResponse } from '../../lib/api'
import { Markdown } from '../ui'
import { textColors } from '../../styles/designSystem'

interface SummaryTabProps {
  changeSummaryDoc: DocumentResponse | null | undefined
}

export function SummaryTab({ changeSummaryDoc }: SummaryTabProps) {
  return (
    <div className="h-full flex flex-col">
      <div className="h-full overflow-y-auto">
        {changeSummaryDoc?.content ? (
          <Markdown>{changeSummaryDoc.content}</Markdown>
        ) : (
          <p className={`${textColors.secondary} italic`}>No change summary available yet.</p>
        )}
      </div>
    </div>
  )
}
