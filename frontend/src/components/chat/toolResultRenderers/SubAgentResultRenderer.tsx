/**
 * Rich renderer for investigate_codebase and review_code_changes tool results.
 * Renders the result field as formatted markdown and displays session_id as metadata.
 */

import Markdown from '../../ui/Markdown'
import type { RichResultRendererProps } from './index'

interface SubAgentResultData {
  result: string
  session_id: number | null
}

function isSubAgentResultData(data: unknown): data is SubAgentResultData {
  if (typeof data !== 'object' || data === null) {
    return false
  }

  const obj = data as Record<string, unknown>
  return (
    typeof obj.result === 'string' &&
    (obj.session_id === null || typeof obj.session_id === 'number')
  )
}

export default function SubAgentResultRenderer({ data }: RichResultRendererProps) {
  if (!isSubAgentResultData(data)) {
    return (
      <div className="font-mono text-xs whitespace-pre-wrap">
        {JSON.stringify(data, null, 2)}
      </div>
    )
  }

  return (
    <div>
      <div className="max-h-96 overflow-y-auto">
        <Markdown>{data.result}</Markdown>
      </div>
      {data.session_id !== null && (
        <div className="mt-2 text-[11px] text-gray-400 dark:text-gray-500 font-mono select-text">
          Conversation: {data.session_id}
        </div>
      )}
    </div>
  )
}
