import { useState, useCallback, useRef, useLayoutEffect } from 'react'
import { CpuChipIcon } from '@heroicons/react/24/outline'
import type { PRFeedbackReview, PRFeedbackCommentThread } from '../../lib/api'

interface PRGeneralCommentsProps {
  reviews: PRFeedbackReview[]
  standaloneThreads: PRFeedbackCommentThread[]
  onSubmit: (message: string) => void
}

// GitHub mark icon (small inline version)
const GitHubIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
  </svg>
)

function formatTimestamp(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function getReviewStateBadge(state: string) {
  switch (state.toUpperCase()) {
    case 'APPROVED':
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Approved</span>
    case 'CHANGES_REQUESTED':
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Changes Requested</span>
    case 'COMMENTED':
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">Commented</span>
    default:
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400">{state}</span>
  }
}

function buildAgentMessage(author: string, body: string, userNotes: string): string {
  const parts = ['Address this PR review comment:\n']
  parts.push(`**Reviewer**: @${author}`)
  parts.push(`**Comment**: ${body}`)

  if (userNotes.trim()) {
    parts.push(`\n${userNotes.trim()}`)
  }

  return parts.join('\n')
}

function SendToAgentButton({ author, body, onSubmit }: { author: string; body: string; onSubmit: (message: string) => void }) {
  const [showNotes, setShowNotes] = useState(false)
  const [notes, setNotes] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useLayoutEffect(() => {
    if (showNotes) {
      textareaRef.current?.focus()
    }
  }, [showNotes])

  const handleSend = useCallback(() => {
    onSubmit(buildAgentMessage(author, body, notes))
    setShowNotes(false)
    setNotes('')
  }, [author, body, notes, onSubmit])

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

  if (!showNotes) {
    return (
      <button
        onClick={() => setShowNotes(true)}
        className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-900/50 rounded transition-colors"
      >
        <CpuChipIcon className="w-3.5 h-3.5" />
        Send to agent
      </button>
    )
  }

  return (
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
  )
}

export default function PRGeneralComments({ reviews, standaloneThreads, onSubmit }: PRGeneralCommentsProps) {
  // Filter to reviews with non-empty body and standalone threads without file paths
  const reviewsWithBody = reviews.filter(r => r.body.trim())
  const generalThreads = standaloneThreads.filter(t => !t.original.path)

  if (reviewsWithBody.length === 0 && generalThreads.length === 0) {
    return null
  }

  return (
    <div className="mt-6 border-t border-gray-200 dark:border-gray-700 pt-4">
      <h3 className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
        <GitHubIcon className="w-4 h-4" />
        PR Review Comments
      </h3>

      <div className="space-y-3">
        {/* Review-level comments */}
        {reviewsWithBody.map((review) => (
          <div key={review.id} className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 rounded-r">
            <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 mb-1.5">
              <span className="font-semibold">@{review.author}</span>
              {getReviewStateBadge(review.state)}
              {review.submitted_at && (
                <span className="opacity-60">{formatTimestamp(review.submitted_at)}</span>
              )}
            </div>
            <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap mb-2">
              {review.body}
            </div>
            <SendToAgentButton author={review.author} body={review.body} onSubmit={onSubmit} />
          </div>
        ))}

        {/* Standalone threads (general comments not tied to a file) */}
        {generalThreads.map((thread) => (
          <div key={thread.original.id} className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 rounded-r">
            <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 mb-1.5">
              <span className="font-semibold">@{thread.original.author}</span>
              {thread.original.created_at && (
                <span className="opacity-60">{formatTimestamp(thread.original.created_at)}</span>
              )}
            </div>
            <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap mb-2">
              {thread.original.body}
            </div>

            {/* Replies */}
            {thread.replies.length > 0 && (
              <div className="ml-4 space-y-2 border-l border-amber-300/50 dark:border-amber-600/30 pl-3 mb-2">
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

            <SendToAgentButton author={thread.original.author} body={thread.original.body} onSubmit={onSubmit} />
          </div>
        ))}
      </div>
    </div>
  )
}
