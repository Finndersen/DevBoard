import { useState, useEffect } from 'react'
import { ChevronUpIcon, ChevronDownIcon, EyeIcon, EyeSlashIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline'
import type { PendingApproval } from '../lib/api'
import { 
  generateUnifiedDiff, 
  createInlineHighlight, 
  createDocumentComparison,
  calculateDiffStats,
  formatDiffStats,
  highlightUnifiedDiff
} from '../utils/diffUtils'
import InlineChangeHighlighter, { ChangeComparison } from './InlineChangeHighlighter'

interface DiffViewerProps {
  approval: PendingApproval
  className?: string
}

type ViewMode = 'cards' | 'unified'

export default function DiffViewer({ approval, className = '' }: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [expandedEdits, setExpandedEdits] = useState<Set<number>>(new Set())
  const [showWhitespace, setShowWhitespace] = useState(false)

  // Keyboard navigation for view mode switching
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Only handle keys if we're not in an input field
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return
      }

      switch (event.key) {
        case '1':
          if (event.altKey) {
            event.preventDefault()
            setViewMode('cards')
          }
          break
        case '2':
          if (event.altKey) {
            event.preventDefault()
            setViewMode('unified')
          }
          break
        case 'e':
          if (event.altKey) {
            event.preventDefault()
            expandAllEdits()
          }
          break
        case 'c':
          if (event.altKey) {
            event.preventDefault()
            collapseAllEdits()
          }
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const toggleEditExpansion = (index: number) => {
    const newExpanded = new Set(expandedEdits)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedEdits(newExpanded)
  }

  const expandAllEdits = () => {
    if (approval.edits) {
      setExpandedEdits(new Set(approval.edits.map((_, index) => index)))
    }
  }

  const collapseAllEdits = () => {
    setExpandedEdits(new Set())
  }

  const renderUnifiedDiff = () => {
    if (!approval.edits || approval.edits.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No edits available to generate unified diff
        </div>
      )
    }

    const unifiedDiffText = generateUnifiedDiff(approval.edits)
    const highlightedLines = highlightUnifiedDiff(unifiedDiffText)
    const stats = calculateDiffStats(approval.edits)

    const copyToClipboard = async () => {
      try {
        await navigator.clipboard.writeText(unifiedDiffText)
      } catch (err) {
        console.warn('Failed to copy to clipboard:', err)
      }
    }

    return (
      <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <div className="bg-gray-100 dark:bg-gray-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
              Unified Diff
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-500">
              {formatDiffStats(stats)}
            </span>
          </div>
          <button
            onClick={copyToClipboard}
            className="text-xs px-2 py-1 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 rounded transition-colors"
            title="Copy to clipboard"
          >
            <DocumentDuplicateIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4 max-h-96 overflow-y-auto font-mono text-xs">
          {highlightedLines.map((line, index) => (
            <div key={index} className={`leading-relaxed ${getUnifiedDiffLineStyle(line.type)}`}>
              {line.line || '\u00A0'} {/* Non-breaking space for empty lines */}
            </div>
          ))}
        </div>
      </div>
    )
  }

  const getUnifiedDiffLineStyle = (type: 'header' | 'added' | 'removed' | 'context') => {
    switch (type) {
      case 'header':
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 font-medium px-2 py-1 my-1 rounded'
      case 'added':
        return 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200'
      case 'removed':
        return 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200'
      case 'context':
      default:
        return 'text-gray-700 dark:text-gray-300'
    }
  }


  const renderCards = () => {
    if (!approval.edits || approval.edits.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No individual edits available
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {approval.edits.map((edit, index) => {
          const highlight = createInlineHighlight(edit.find, edit.replace)
          const editStats = calculateDiffStats([edit])
          
          return (
            <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <div className="bg-gray-50 dark:bg-gray-800 px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  Change {index + 1} of {approval.edits.length}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-500">
                  {formatDiffStats(editStats)}
                </span>
              </div>
              
              {/* Enhanced comparison with highlighting */}
              <ChangeComparison
                oldText={edit.find}
                newText={edit.replace}
                changes={highlight.changes}
                className="border-0 rounded-none"
              />
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* View Mode Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
          <button
            onClick={() => setViewMode('cards')}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              viewMode === 'cards'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Cards View - Review each change individually (Alt+1)"
          >
            Cards View
          </button>
          <button
            onClick={() => setViewMode('unified')}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              viewMode === 'unified'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Unified Diff - Git-style diff format (Alt+2)"
          >
            Unified Diff
          </button>
        </div>
        
        {/* Keyboard shortcuts help */}
        <div className="text-xs text-gray-500 dark:text-gray-400 space-x-2">
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+1,2</kbd> Switch views</span>
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+E</kbd> Expand</span>
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+C</kbd> Collapse</span>
        </div>
      </div>

      {/* Content based on view mode */}
      <div>
        {viewMode === 'unified' && renderUnifiedDiff()}
        {viewMode === 'cards' && renderCards()}
      </div>
    </div>
  )
}