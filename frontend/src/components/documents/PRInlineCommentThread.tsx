import { useState, useCallback, useRef, useLayoutEffect } from 'react'
import { CpuChipIcon } from '@heroicons/react/24/outline'
import type { PRFeedbackCommentThread } from '../../lib/api'

interface PRInlineCommentThreadProps {
  thread: PRFeedbackCommentThread
  onSubmit: (message: string) => void
}

function formatTimestamp(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function buildAgentMessage(thread: PRFeedbackCommentThread, userNotes: string): string {
  const comment = thread.original
  const parts = ['Address this PR review comment:\n']

  if (comment.path) {
    parts.push(`**File**: \`${comment.path}\`${comment.line ? ` (line ${comment.line})` : ''}`)
  }
  parts.push(`**Reviewer**: @${comment.author}`)
  parts.push(`**Comment**: ${comment.body}`)

  if (comment.diff_hunk) {
    parts.push(`\n**Diff context**:\n\`\`\`\n${comment.diff_hunk}\n\`\`\``)
  }

  if (userNotes.trim()) {
    parts.push(`\n${userNotes.trim()}`)
  }

  return parts.join('\n')
}

export default function PRInlineCommentThread({ thread, onSubmit }: PRInlineCommentThreadProps) {
  const [showNotes, setShowNotes] = useState(false)
  const [notes, setNotes] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useLayoutEffect(() => {
    if (showNotes) {
      textareaRef.current?.focus()
    }
  }, [showNotes])

  const handleSend = useCallback(() => {
    onSubmit(buildAgentMessage(thread, notes))
    setShowNotes(false)
    setNotes('')
  }, [thread, notes, onSubmit])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setShowNotes(false)
      setNotes('')
    }
  }, [handleSend])

  return (
    <div className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 my-1">
      {/* Header */}
      <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 mb-1.5">
        <span className="font-semibold">GitHub Review</span>
        <span>@{thread.original.author}</span>
        {thread.original.created_at && (
          <span className="text-amber-600/60 dark:text-amber-500/60">{formatTimestamp(thread.original.created_at)}</span>
        )}
      </div>

      {/* Original comment body */}
      <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap mb-2">
        {thread.original.body}
      </div>

      {/* Replies */}
      {thread.replies.length > 0 && (
        <div className="ml-4 space-y-2 border-l border-amber-300/50 dark:border-amber-600/30 pl-3">
          {thread.replies.map((reply) => (
            <div key={reply.id}>
              <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-500 mb-0.5">
                <span>@{reply.author}</span>
                {reply.created_at && (
                  <span className="opacity-60">{formatTimestamp(reply.created_at)}</span>
                )}
              </div>
              <div className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {reply.body}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Send to agent button */}
      {!showNotes ? (
        <button
          onClick={() => setShowNotes(true)}
          className="mt-2 flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-900/50 rounded transition-colors"
        >
          <CpuChipIcon className="w-3.5 h-3.5" />
          Send to agent
        </button>
      ) : (
        <div className="mt-2 space-y-2">
          <textarea
            ref={textareaRef}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add optional notes for the agent..."
            className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-900 border border-amber-300 dark:border-amber-600/50 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
            rows={2}
          />
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => { setShowNotes(false); setNotes('') }}
              className="px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSend}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 rounded transition-colors"
            >
              <CpuChipIcon className="w-3 h-3" />
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
