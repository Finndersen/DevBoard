import { useState, useCallback } from 'react'
import { CpuChipIcon } from '@heroicons/react/24/outline'
import type { PRFeedbackResponse, PRFeedbackReview, PRFeedbackCommentThread } from '../../lib/api'
import { textColors, surfaces, borderColors, statusColors } from '../../styles/designSystem'

interface CommentsTabProps {
  prFeedback: PRFeedbackResponse
  onSubmitComments: (message: string) => void
}

function formatTimestamp(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function getReviewStateBadge(state: string) {
  switch (state.toUpperCase()) {
    case 'APPROVED':
      return <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${statusColors.success.icon} ${statusColors.success.text}`}>Approved</span>
    case 'CHANGES_REQUESTED':
      return <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${statusColors.error.icon} ${statusColors.error.text}`}>Changes Requested</span>
    case 'COMMENTED':
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-700 dark:bg-white/[0.05] dark:text-gray-300">Commented</span>
    default:
      return <span className="px-1.5 py-0.5 text-xs font-medium rounded bg-gray-100 text-gray-600 dark:bg-white/[0.05] dark:text-gray-400">{state}</span>
  }
}

function buildReviewAgentMessage(author: string, body: string, userNotes: string): string {
  const parts = ['Address this PR review comment:\n']
  parts.push(`**Reviewer**: @${author}`)
  parts.push(`**Comment**: ${body}`)
  if (userNotes.trim()) {
    parts.push(`\n${userNotes.trim()}`)
  }
  return parts.join('\n')
}

function buildThreadAgentMessage(thread: PRFeedbackCommentThread, userNotes: string): string {
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

function SendToAgentInline({ onSend }: { onSend: (notes: string) => void }) {
  const [notes, setNotes] = useState('')

  const handleSend = useCallback(() => {
    onSend(notes)
    setNotes('')
  }, [notes, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  return (
    <div className="mt-2 space-y-2">
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Add optional notes for the agent..."
        className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-900 border border-amber-300 dark:border-amber-600/50 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
        rows={2}
      />
      <div className="flex items-center justify-end">
        <button
          onClick={handleSend}
          className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-amber-600 hover:bg-amber-700 rounded transition-colors"
        >
          <CpuChipIcon className="w-3 h-3" />
          Send to agent
        </button>
      </div>
    </div>
  )
}

function ThreadReplies({ replies }: { replies: PRFeedbackCommentThread['replies'] }) {
  if (replies.length === 0) return null

  return (
    <div className="ml-4 space-y-2 border-l border-amber-300/50 dark:border-amber-600/30 pl-3 mb-2">
      {replies.map((reply) => (
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
  )
}

function ReviewSection({ review, onSubmit }: { review: PRFeedbackReview; onSubmit: (message: string) => void }) {
  return (
    <div className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 rounded-r">
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
      <SendToAgentInline onSend={(notes) => onSubmit(buildReviewAgentMessage(review.author, review.body, notes))} />
    </div>
  )
}

function GeneralThreadSection({ thread, onSubmit }: { thread: PRFeedbackCommentThread; onSubmit: (message: string) => void }) {
  return (
    <div className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 rounded-r">
      <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 mb-1.5">
        <span className="font-semibold">@{thread.original.author}</span>
        {thread.original.created_at && (
          <span className="opacity-60">{formatTimestamp(thread.original.created_at)}</span>
        )}
      </div>
      <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap mb-2">
        {thread.original.body}
      </div>
      <ThreadReplies replies={thread.replies} />
      <SendToAgentInline onSend={(notes) => onSubmit(buildThreadAgentMessage(thread, notes))} />
    </div>
  )
}

function FileThreadSection({ thread, onSubmit }: { thread: PRFeedbackCommentThread; onSubmit: (message: string) => void }) {
  return (
    <div className="border-l-2 border-amber-400 bg-amber-50/50 dark:bg-amber-900/10 p-3 rounded-r">
      <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400 mb-1.5">
        <code className="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
          {thread.original.path}{thread.original.line ? `:${thread.original.line}` : ''}
        </code>
        <span>@{thread.original.author}</span>
        {thread.original.created_at && (
          <span className="opacity-60">{formatTimestamp(thread.original.created_at)}</span>
        )}
      </div>
      {thread.original.diff_hunk && (
        <pre className={`text-xs font-mono ${surfaces.sunken} border ${borderColors.default} rounded p-2 mb-2 overflow-x-auto whitespace-pre`}>
          {thread.original.diff_hunk}
        </pre>
      )}
      <div className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap mb-2">
        {thread.original.body}
      </div>
      <ThreadReplies replies={thread.replies} />
      <SendToAgentInline onSend={(notes) => onSubmit(buildThreadAgentMessage(thread, notes))} />
    </div>
  )
}

export function CommentsTab({ prFeedback, onSubmitComments }: CommentsTabProps) {
  const reviewsWithBody = prFeedback.reviews.filter(r => r.body.trim())
  const generalThreads = prFeedback.standalone_threads.filter(t => !t.original.path)

  // Collect all file-specific threads from reviews and standalone
  const fileThreads: PRFeedbackCommentThread[] = []
  for (const review of prFeedback.reviews) {
    for (const thread of review.comment_threads) {
      if (thread.original.path) {
        fileThreads.push(thread)
      }
    }
  }
  for (const thread of prFeedback.standalone_threads) {
    if (thread.original.path) {
      fileThreads.push(thread)
    }
  }

  const sectionCount = (reviewsWithBody.length > 0 ? 1 : 0) + (generalThreads.length > 0 ? 1 : 0) + (fileThreads.length > 0 ? 1 : 0)
  const showHeadings = sectionCount > 1

  return (
    <div className="h-full overflow-y-auto space-y-4">
      {reviewsWithBody.length > 0 && (
        <div>
          {showHeadings && (
            <h3 className={`text-sm font-medium ${textColors.primary} mb-3`}>Reviews</h3>
          )}
          <div className="space-y-3">
            {reviewsWithBody.map((review) => (
              <ReviewSection key={review.id} review={review} onSubmit={onSubmitComments} />
            ))}
          </div>
        </div>
      )}

      {generalThreads.length > 0 && (
        <div>
          {showHeadings && (
            <h3 className={`text-sm font-medium ${textColors.primary} mb-3`}>General Comments</h3>
          )}
          <div className="space-y-3">
            {generalThreads.map((thread) => (
              <GeneralThreadSection key={thread.original.id} thread={thread} onSubmit={onSubmitComments} />
            ))}
          </div>
        </div>
      )}

      {fileThreads.length > 0 && (
        <div>
          {showHeadings && (
            <h3 className={`text-sm font-medium ${textColors.primary} mb-3`}>File Comments</h3>
          )}
          <div className="space-y-3">
            {fileThreads.map((thread) => (
              <FileThreadSection key={thread.original.id} thread={thread} onSubmit={onSubmitComments} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
