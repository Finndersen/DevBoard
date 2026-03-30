import { ChevronRightIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useEffect, useState, useCallback, useMemo, Fragment, startTransition, useRef } from 'react'
import { useDiffReviewOptional } from '../../contexts/DiffReviewContext'
import DiffLineCommentButton from './DiffLineCommentButton'
import DiffLineCommentForm from './DiffLineCommentForm'
import { surfaces, borderColors, statusColors, textColors } from '../../styles/designSystem'

interface GitDiffViewerProps {
  diff: string
  fileName?: string
  stats?: {
    additions: number
    deletions: number
  }
  defaultExpanded?: boolean
  className?: string
  isNewFile?: boolean
  isDeleted?: boolean
}

interface DiffLine {
  type: 'header' | 'hunk' | 'added' | 'removed' | 'context'
  content: string
  oldLineNum?: number
  newLineNum?: number
}

// Map file extensions to Prism language identifiers
const getLanguageFromFilename = (filename?: string): string => {
  if (!filename) return 'text'

  const ext = filename.split('.').pop()?.toLowerCase()

  const languageMap: Record<string, string> = {
    // Common languages
    'js': 'javascript',
    'jsx': 'jsx',
    'ts': 'typescript',
    'tsx': 'tsx',
    'py': 'python',
    'rb': 'ruby',
    'java': 'java',
    'go': 'go',
    'rs': 'rust',
    'c': 'c',
    'cpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'h': 'c',
    'hpp': 'cpp',
    'cs': 'csharp',
    'php': 'php',
    'swift': 'swift',
    'kt': 'kotlin',
    'scala': 'scala',

    // Web
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'sass',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',

    // Shell/Config
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'fish': 'bash',
    'sql': 'sql',
    'md': 'markdown',
    'markdown': 'markdown',
    'dockerfile': 'docker',

    // Other
    'graphql': 'graphql',
    'gql': 'graphql',
  }

  return languageMap[ext || ''] || 'text'
}

// Parse diff into structured lines with line numbers
function parseDiff(rawDiff: string): DiffLine[] {
  const lines = rawDiff.split('\n')
  const result: DiffLine[] = []
  let oldLineNum = 0
  let newLineNum = 0

  for (const line of lines) {
    // Skip git metadata headers (diff --git, index, ---, +++)
    if (
      line.startsWith('diff --git') ||
      line.startsWith('index ') ||
      line.startsWith('--- ') ||
      line.startsWith('+++ ')
    ) {
      continue
    }

    // Hunk headers (@@ -x,y +a,b @@)
    if (line.startsWith('@@')) {
      const match = line.match(/@@ -(\d+),?\d* \+(\d+),?\d* @@/)
      if (match) {
        oldLineNum = parseInt(match[1], 10)
        newLineNum = parseInt(match[2], 10)
      }
      result.push({ type: 'hunk', content: line })
      continue
    }

    // Added lines
    if (line.startsWith('+')) {
      result.push({
        type: 'added',
        content: line.substring(1), // Remove the + prefix
        newLineNum: newLineNum++,
      })
      continue
    }

    // Removed lines
    if (line.startsWith('-')) {
      result.push({
        type: 'removed',
        content: line.substring(1), // Remove the - prefix
        oldLineNum: oldLineNum++,
      })
      continue
    }

    // Context lines (unchanged)
    result.push({
      type: 'context',
      content: line.startsWith(' ') ? line.substring(1) : line,
      oldLineNum: oldLineNum++,
      newLineNum: newLineNum++,
    })
  }

  return result
}

export default function GitDiffViewer({ diff, fileName, stats, defaultExpanded = false, className = '', isNewFile, isDeleted }: GitDiffViewerProps) {
  // Collapse/expand state
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  // Track which diff line index has the comment form open (not line number, since those can duplicate)
  const [activeCommentIndex, setActiveCommentIndex] = useState<number | null>(null)

  // Detect dark mode
  const [isDarkMode, setIsDarkMode] = useState(false)

  // Ref to the scroll container to get its width for comment form
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState<number | null>(null)

  // Get optional review context (may be undefined if not within provider)
  const reviewContext = useDiffReviewOptional()

  // Track container width for comment form sizing
  useEffect(() => {
    if (!scrollContainerRef.current) return

    const updateWidth = () => {
      if (scrollContainerRef.current) {
        setContainerWidth(scrollContainerRef.current.clientWidth)
      }
    }

    updateWidth()

    const resizeObserver = new ResizeObserver(updateWidth)
    resizeObserver.observe(scrollContainerRef.current)

    return () => resizeObserver.disconnect()
  }, [isExpanded])

  useEffect(() => {
    const checkDarkMode = () => {
      setIsDarkMode(document.documentElement.classList.contains('dark'))
    }

    checkDarkMode()

    // Watch for dark mode changes
    const observer = new MutationObserver(checkDarkMode)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    })

    return () => observer.disconnect()
  }, [])

  const language = getLanguageFromFilename(fileName)

  // Only parse diff when expanded to improve performance
  const diffLines = useMemo(() => isExpanded ? parseDiff(diff) : [], [isExpanded, diff])

  const getLineStyle = (type: DiffLine['type']) => {
    switch (type) {
      case 'hunk':
        return `${statusColors.info.bg} ${statusColors.info.text} font-medium`
      case 'added':
        return `${statusColors.success.bg} ${statusColors.success.text}`
      case 'removed':
        return `${statusColors.error.bg} ${statusColors.error.text}`
      case 'context':
        return textColors.secondary
      default:
        return textColors.secondary
    }
  }

  const formatLineNumber = (num?: number) => {
    return num !== undefined ? num.toString().padStart(4, ' ') : '    '
  }

  // Get the line number to use for comments (new line for added/context, old for removed)
  const getCommentLineNumber = (line: DiffLine): number => {
    if (line.type === 'removed') {
      return line.oldLineNum ?? 0
    }
    return line.newLineNum ?? line.oldLineNum ?? 0
  }

  // Get surrounding lines for context
  const getSurroundingLines = useCallback((index: number, count: number = 2) => {
    const above: string[] = []
    const below: string[] = []

    // Get lines above
    for (let i = index - 1; i >= 0 && above.length < count; i--) {
      const line = diffLines[i]
      if (line.type !== 'hunk') {
        above.unshift(line.content)
      }
    }

    // Get lines below
    for (let i = index + 1; i < diffLines.length && below.length < count; i++) {
      const line = diffLines[i]
      if (line.type !== 'hunk') {
        below.push(line.content)
      }
    }

    return { above, below }
  }, [diffLines])

  const handleCommentButtonClick = useCallback((index: number) => {
    startTransition(() => {
      setActiveCommentIndex(prev => prev === index ? null : index)
    })
  }, [])

  const handleCloseCommentForm = useCallback(() => {
    startTransition(() => {
      setActiveCommentIndex(null)
    })
  }, [])

  // Check if comments are enabled (context exists and fileName is provided)
  const commentsEnabled = !!reviewContext && !!fileName

  return (
    <div className={`${surfaces.raised} border ${borderColors.default} rounded-lg overflow-hidden ${className}`}>
      {/* File Header - Clickable to expand/collapse */}
      <div
        className={`${surfaces.sunken} px-4 py-2 border-b ${borderColors.default} flex items-center space-x-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Chevron icon */}
        {isExpanded ? (
          <ChevronDownIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
        )}
        {fileName && (
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {fileName}
          </span>
        )}
        {isNewFile && (
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${statusColors.success.icon} ${statusColors.success.text} shrink-0`}>
            New
          </span>
        )}
        {isDeleted && (
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${statusColors.error.icon} ${statusColors.error.text} shrink-0`}>
            Deleted
          </span>
        )}
        {stats && (
          <span className="text-xs text-gray-600 dark:text-gray-400 shrink-0">
            <span className="text-green-600 dark:text-green-400">+{stats.additions}</span>
            {' '}
            <span className="text-red-600 dark:text-red-400">-{stats.deletions}</span>
          </span>
        )}
      </div>

      {/* Diff Content - Only render when expanded */}
      {isExpanded && (
        <div ref={scrollContainerRef} className="max-h-[32rem] overflow-auto">
          <div className="font-mono text-xs min-w-max">
            {diffLines.map((line, index) => {
              const lineNumber = getCommentLineNumber(line)
              const isCommentFormOpen = activeCommentIndex === index && line.type !== 'hunk'

              return (
                <Fragment key={index}>
                  <div
                    className={`group flex ${getLineStyle(line.type)}`}
                  >
                    {/* Line numbers with comment button */}
                    {line.type !== 'hunk' && (
                      <div className="flex items-stretch shrink-0 select-none border-r border-gray-300 dark:border-gray-600 sticky left-0 bg-inherit">
                        <span className="w-10 text-right pr-1 text-gray-500 dark:text-gray-400 bg-inherit flex items-center justify-end">
                          {formatLineNumber(line.oldLineNum)}
                        </span>
                        <span className="w-10 text-right pr-1 text-gray-500 dark:text-gray-400 bg-inherit flex items-center justify-end">
                          {formatLineNumber(line.newLineNum)}
                        </span>
                        {/* Comment button - positioned after line numbers like GitHub */}
                        {commentsEnabled && fileName ? (
                          <div className="w-6 flex items-center justify-center bg-inherit">
                            <DiffLineCommentButton
                              onClick={() => handleCommentButtonClick(index)}
                              filePath={fileName}
                              lineNumber={lineNumber}
                            />
                          </div>
                        ) : (
                          <div className="w-1 bg-inherit" />
                        )}
                      </div>
                    )}
                    {/* Hunk header - left aligned with padding to clear line number column */}
                    {line.type === 'hunk' && (
                      <div className="flex-1">
                        <pre className={`py-1 m-0 whitespace-pre ${commentsEnabled ? 'pl-[6.5rem]' : 'pl-[5.25rem]'}`}>
                          {line.content || ' '}
                        </pre>
                      </div>
                    )}
                    {/* Content with syntax highlighting */}
                    {line.type !== 'hunk' && (
                      <div className="flex-1">
                        <SyntaxHighlighter
                          language={language}
                          style={isDarkMode ? oneDark : oneLight}
                          customStyle={{
                            background: 'transparent',
                            margin: 0,
                            padding: '0.25rem 1rem',
                            fontSize: 'inherit',
                            lineHeight: 'inherit',
                          }}
                          codeTagProps={{
                            style: {
                              fontFamily: 'inherit',
                              fontSize: 'inherit',
                            }
                          }}
                          PreTag="div"
                        >
                          {line.content || ' '}
                        </SyntaxHighlighter>
                      </div>
                    )}
                  </div>
                  {/* Comment form - rendered below the line when active, sticky to stay in viewport */}
                  {isCommentFormOpen && fileName && (
                    <div
                      className="sticky left-0"
                      style={{ width: containerWidth ? `${containerWidth}px` : '100%' }}
                    >
                      <DiffLineCommentForm
                        filePath={fileName}
                        lineNumber={lineNumber}
                        lineContent={line.content}
                        surroundingLines={getSurroundingLines(index)}
                        onClose={handleCloseCommentForm}
                      />
                    </div>
                  )}
                </Fragment>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
