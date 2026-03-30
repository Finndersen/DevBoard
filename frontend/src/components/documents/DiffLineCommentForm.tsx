import { useState, useRef, useCallback, useLayoutEffect, useEffect } from 'react'
import { useDiffReview } from '../../contexts/DiffReviewContext'
import { surfaces, borderColors } from '../../styles/designSystem'

interface DiffLineCommentFormProps {
  filePath: string
  lineNumber: number
  lineContent: string
  surroundingLines: { above: string[]; below: string[] }
  onClose: () => void
}

export default function DiffLineCommentForm({
  filePath,
  lineNumber,
  lineContent,
  surroundingLines,
  onClose
}: DiffLineCommentFormProps) {
  const { pendingComments, addComment, removeComment, submitSingleComment, isSubmitting } = useDiffReview()

  // Get initial text from context only once using lazy initializer
  const [commentText, setCommentText] = useState(
    () => pendingComments.get(`${filePath}:${lineNumber}`)?.commentText ?? ''
  )
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Use useLayoutEffect to focus immediately before paint
  useLayoutEffect(() => {
    textareaRef.current?.focus()
  }, [])

  // Sync comment to context (debounced)
  const syncToContext = useCallback((text: string) => {
    if (text.trim()) {
      addComment({
        filePath,
        lineNumber,
        lineContent,
        commentText: text.trim(),
        surroundingLines
      })
    } else {
      removeComment(filePath, lineNumber)
    }
  }, [filePath, lineNumber, lineContent, surroundingLines, addComment, removeComment])

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  // Update local state immediately, debounce context sync
  const handleTextChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value
    setCommentText(newText)

    // Debounce the context update
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      syncToContext(newText)
    }, 300)
  }, [syncToContext])

  // Send this comment immediately
  const handleSend = useCallback(async () => {
    if (!commentText.trim()) return

    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    // Submit the comment directly
    await submitSingleComment({
      filePath,
      lineNumber,
      lineContent,
      commentText: commentText.trim(),
      surroundingLines
    })
    onClose()
  }, [commentText, filePath, lineNumber, lineContent, surroundingLines, submitSingleComment, onClose])

  // Cancel removes the comment entirely
  const handleCancel = useCallback(() => {
    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    removeComment(filePath, lineNumber)
    onClose()
  }, [filePath, lineNumber, removeComment, onClose])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      handleSend()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      handleCancel()
    }
  }, [handleSend, handleCancel])

  return (
    <div className={`${surfaces.sunken} border-t border-b ${borderColors.default} p-3`}>
      <div className="space-y-2">
        <textarea
          ref={textareaRef}
          value={commentText}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          placeholder="Add a review comment..."
          className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
          rows={3}
          disabled={isSubmitting}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+Enter to send
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCancel}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSend}
              disabled={!commentText.trim() || isSubmitting}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
