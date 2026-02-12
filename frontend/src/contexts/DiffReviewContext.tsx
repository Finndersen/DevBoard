import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'

export interface PendingComment {
  filePath: string
  lineNumber: number
  lineContent: string
  commentText: string
  surroundingLines: { above: string[]; below: string[] }
}

export type CommentSubmitHandler = (message: string) => Promise<void>

interface DiffReviewContextValue {
  pendingComments: Map<string, PendingComment>
  addComment: (comment: Omit<PendingComment, 'commentText'> & { commentText: string }) => void
  updateComment: (filePath: string, lineNumber: number, commentText: string) => void
  removeComment: (filePath: string, lineNumber: number) => void
  submitSingleComment: (comment: PendingComment) => Promise<void>
  submitAllComments: () => Promise<void>
  clearAllComments: () => void
  isSubmitting: boolean
  hasComment: (filePath: string, lineNumber: number) => boolean
}

const DiffReviewContext = createContext<DiffReviewContextValue | undefined>(undefined)

function getLanguageFromFilePath(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase()
  const languageMap: Record<string, string> = {
    'js': 'javascript', 'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
    'py': 'python', 'rb': 'ruby', 'java': 'java', 'go': 'go', 'rs': 'rust',
    'c': 'c', 'cpp': 'cpp', 'h': 'c', 'hpp': 'cpp', 'cs': 'csharp',
    'php': 'php', 'swift': 'swift', 'kt': 'kotlin', 'scala': 'scala',
    'html': 'html', 'css': 'css', 'scss': 'scss', 'json': 'json',
    'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml', 'md': 'markdown',
    'sh': 'bash', 'bash': 'bash', 'sql': 'sql'
  }
  return languageMap[ext || ''] || ''
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatCommentMessage(comment: PendingComment): string {
  const { filePath, lineNumber, lineContent, commentText, surroundingLines } = comment
  const language = getLanguageFromFilePath(filePath)

  // Build numbered code block with context
  const startLine = lineNumber - surroundingLines.above.length
  const lines: string[] = []

  surroundingLines.above.forEach((content, i) => {
    const num = startLine + i
    lines.push(`   ${num.toString().padStart(4)} │ ${content}`)
  })

  // Commented line with >> indicator
  lines.push(`>> ${lineNumber.toString().padStart(4)} │ ${lineContent}`)

  surroundingLines.below.forEach((content, i) => {
    const num = lineNumber + 1 + i
    lines.push(`   ${num.toString().padStart(4)} │ ${content}`)
  })

  const codeBlock = lines.join('\n')

  return `**Review comment** on \`${filePath}\` at line ${lineNumber}:

\`\`\`${language}
${codeBlock}
\`\`\`

${commentText}`
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatBatchMessage(comments: PendingComment[]): string {
  return `## Code Review Comments\n\n${comments.map(formatCommentMessage).join('\n\n---\n\n')}`
}

interface DiffReviewProviderProps {
  children: ReactNode
  onSubmitComments: CommentSubmitHandler
}

export function DiffReviewProvider({ children, onSubmitComments }: DiffReviewProviderProps) {
  const [pendingComments, setPendingComments] = useState<Map<string, PendingComment>>(new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)

  const getCommentKey = useCallback((filePath: string, lineNumber: number) => {
    return `${filePath}:${lineNumber}`
  }, [])

  const addComment = useCallback((comment: Omit<PendingComment, 'commentText'> & { commentText: string }) => {
    const key = getCommentKey(comment.filePath, comment.lineNumber)
    setPendingComments(prev => {
      const next = new Map(prev)
      next.set(key, comment as PendingComment)
      return next
    })
  }, [getCommentKey])

  const updateComment = useCallback((filePath: string, lineNumber: number, commentText: string) => {
    const key = getCommentKey(filePath, lineNumber)
    setPendingComments(prev => {
      const existing = prev.get(key)
      if (!existing) return prev
      const next = new Map(prev)
      next.set(key, { ...existing, commentText })
      return next
    })
  }, [getCommentKey])

  const removeComment = useCallback((filePath: string, lineNumber: number) => {
    const key = getCommentKey(filePath, lineNumber)
    setPendingComments(prev => {
      const next = new Map(prev)
      next.delete(key)
      return next
    })
  }, [getCommentKey])

  const hasComment = useCallback((filePath: string, lineNumber: number) => {
    const key = getCommentKey(filePath, lineNumber)
    return pendingComments.has(key)
  }, [getCommentKey, pendingComments])

  const clearAllComments = useCallback(() => {
    setPendingComments(new Map())
  }, [])

  const submitSingleComment = useCallback(async (comment: PendingComment) => {
    if (!comment.commentText.trim()) return

    const message = formatCommentMessage(comment)
    // Remove comment from pending immediately so form closes
    removeComment(comment.filePath, comment.lineNumber)
    // Submit message (runs in background, doesn't block)
    await onSubmitComments(message)
  }, [onSubmitComments, removeComment])

  const submitAllComments = useCallback(async () => {
    if (pendingComments.size === 0) return

    setIsSubmitting(true)
    try {
      const comments = Array.from(pendingComments.values()).filter(c => c.commentText.trim())
      if (comments.length === 0) return

      const message = comments.length === 1
        ? formatCommentMessage(comments[0])
        : formatBatchMessage(comments)

      await onSubmitComments(message)
      clearAllComments()
    } finally {
      setIsSubmitting(false)
    }
  }, [pendingComments, onSubmitComments, clearAllComments])

  const contextValue: DiffReviewContextValue = useMemo(() => ({
    pendingComments,
    addComment,
    updateComment,
    removeComment,
    submitSingleComment,
    submitAllComments,
    clearAllComments,
    isSubmitting,
    hasComment
  }), [
    pendingComments,
    addComment,
    updateComment,
    removeComment,
    submitSingleComment,
    submitAllComments,
    clearAllComments,
    isSubmitting,
    hasComment
  ])

  return (
    <DiffReviewContext.Provider value={contextValue}>
      {children}
    </DiffReviewContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDiffReview() {
  const context = useContext(DiffReviewContext)
  if (context === undefined) {
    throw new Error('useDiffReview must be used within a DiffReviewProvider')
  }
  return context
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDiffReviewOptional() {
  return useContext(DiffReviewContext)
}
