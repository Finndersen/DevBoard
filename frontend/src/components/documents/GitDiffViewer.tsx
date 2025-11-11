import { ChevronRightIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useEffect, useState } from 'react'

interface GitDiffViewerProps {
  diff: string
  fileName?: string
  stats?: {
    additions: number
    deletions: number
  }
  defaultExpanded?: boolean
  className?: string
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

export default function GitDiffViewer({ diff, fileName, stats, defaultExpanded = false, className = '' }: GitDiffViewerProps) {
  // Collapse/expand state
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  // Detect dark mode
  const [isDarkMode, setIsDarkMode] = useState(false)

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

  // Parse diff into structured lines with line numbers (only when expanded)
  const parseDiff = (rawDiff: string): DiffLine[] => {
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

  // Only parse diff when expanded to improve performance
  const diffLines = isExpanded ? parseDiff(diff) : []

  const getLineStyle = (type: DiffLine['type']) => {
    switch (type) {
      case 'hunk':
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 font-medium'
      case 'added':
        return 'bg-green-50 dark:bg-green-900/20 text-green-900 dark:text-green-200'
      case 'removed':
        return 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-200'
      case 'context':
        return 'text-gray-700 dark:text-gray-300'
      default:
        return 'text-gray-700 dark:text-gray-300'
    }
  }

  const formatLineNumber = (num?: number) => {
    return num !== undefined ? num.toString().padStart(4, ' ') : '    '
  }

  return (
    <div className={`bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden ${className}`}>
      {/* File Header - Clickable to expand/collapse */}
      <div
        className="bg-gray-50 dark:bg-gray-800 px-4 py-2 border-b border-gray-200 dark:border-gray-600 flex items-center space-x-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
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
        <div className="max-h-[32rem] overflow-auto">
          <div className="font-mono text-xs min-w-max">
            {diffLines.map((line, index) => (
              <div
                key={index}
                className={`flex ${getLineStyle(line.type)}`}
              >
                {/* Line numbers */}
                {line.type !== 'hunk' && (
                  <div className="flex shrink-0 select-none border-r border-gray-300 dark:border-gray-600 sticky left-0 bg-inherit">
                    <span className="inline-block w-12 text-right px-2 text-gray-500 dark:text-gray-400 bg-inherit">
                      {formatLineNumber(line.oldLineNum)}
                    </span>
                    <span className="inline-block w-12 text-right px-2 text-gray-500 dark:text-gray-400 bg-inherit">
                      {formatLineNumber(line.newLineNum)}
                    </span>
                  </div>
                )}
                {/* Content with syntax highlighting */}
                <div className={`flex-1 ${line.type === 'hunk' ? 'text-center' : ''}`}>
                  {line.type === 'hunk' ? (
                    <pre className="px-4 py-1 m-0 whitespace-pre">{line.content || ' '}</pre>
                  ) : (
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
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
