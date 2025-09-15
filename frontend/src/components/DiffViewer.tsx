import { useState, useEffect } from 'react'
import { ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import type { PendingApproval } from '../lib/api'

interface DiffViewerProps {
  approval: PendingApproval
  className?: string
}

type ViewMode = 'unified' | 'split' | 'edits'

export default function DiffViewer({ approval, className = '' }: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('edits')
  const [expandedEdits, setExpandedEdits] = useState<Set<number>>(new Set())

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
            setViewMode('edits')
          }
          break
        case '2':
          if (event.altKey) {
            event.preventDefault()
            setViewMode('split')
          }
          break
        case '3':
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
    if (!approval.diff_preview) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No unified diff preview available
        </div>
      )
    }

    return (
      <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <div className="bg-gray-100 dark:bg-gray-700 px-4 py-2 border-b border-gray-200 dark:border-gray-600">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
            Unified Diff View
          </span>
        </div>
        <pre className="text-xs p-4 overflow-x-auto whitespace-pre-wrap font-mono text-gray-800 dark:text-gray-200 max-h-96 overflow-y-auto">
          {approval.diff_preview}
        </pre>
      </div>
    )
  }

  const renderSplitDiff = () => {
    if (!approval.edits || approval.edits.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No individual edits available
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {/* Controls */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            {approval.edits.length} change{approval.edits.length !== 1 ? 's' : ''}
          </span>
          <div className="flex space-x-2">
            <button
              onClick={expandAllEdits}
              className="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
            >
              Expand All
            </button>
            <button
              onClick={collapseAllEdits}
              className="text-xs px-2 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
            >
              Collapse All
            </button>
          </div>
        </div>

        {/* Split View */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Before Column */}
          <div>
            <div className="bg-red-50 dark:bg-red-900/20 px-3 py-2 border border-red-200 dark:border-red-800 rounded-t-lg">
              <span className="text-sm font-medium text-red-700 dark:text-red-400">
                Before (Remove)
              </span>
            </div>
            <div className="border-l border-r border-b border-red-200 dark:border-red-800 rounded-b-lg bg-red-50/50 dark:bg-red-900/10 max-h-96 overflow-y-auto">
              {approval.edits.map((edit, index) => (
                <div key={index} className="border-b border-red-200 dark:border-red-800 last:border-b-0">
                  <div className="px-3 py-2 bg-red-100 dark:bg-red-900/30 text-xs text-red-600 dark:text-red-400 flex items-center justify-between">
                    <span>Change {index + 1}</span>
                    <button
                      onClick={() => toggleEditExpansion(index)}
                      className="hover:bg-red-200 dark:hover:bg-red-800 p-1 rounded"
                    >
                      {expandedEdits.has(index) ? (
                        <ChevronUpIcon className="w-3 h-3" />
                      ) : (
                        <ChevronDownIcon className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                  {expandedEdits.has(index) && (
                    <pre className="text-xs p-3 text-red-800 dark:text-red-200 whitespace-pre-wrap font-mono">
                      {edit.find}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* After Column */}
          <div>
            <div className="bg-green-50 dark:bg-green-900/20 px-3 py-2 border border-green-200 dark:border-green-800 rounded-t-lg">
              <span className="text-sm font-medium text-green-700 dark:text-green-400">
                After (Replace with)
              </span>
            </div>
            <div className="border-l border-r border-b border-green-200 dark:border-green-800 rounded-b-lg bg-green-50/50 dark:bg-green-900/10 max-h-96 overflow-y-auto">
              {approval.edits.map((edit, index) => (
                <div key={index} className="border-b border-green-200 dark:border-green-800 last:border-b-0">
                  <div className="px-3 py-2 bg-green-100 dark:bg-green-900/30 text-xs text-green-600 dark:text-green-400 flex items-center justify-between">
                    <span>Change {index + 1}</span>
                    <button
                      onClick={() => toggleEditExpansion(index)}
                      className="hover:bg-green-200 dark:hover:bg-green-800 p-1 rounded"
                    >
                      {expandedEdits.has(index) ? (
                        <ChevronUpIcon className="w-3 h-3" />
                      ) : (
                        <ChevronDownIcon className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                  {expandedEdits.has(index) && (
                    <pre className="text-xs p-3 text-green-800 dark:text-green-200 whitespace-pre-wrap font-mono">
                      {edit.replace}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderEditsList = () => {
    if (!approval.edits || approval.edits.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          No individual edits available
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {approval.edits.map((edit, index) => (
          <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div className="bg-gray-50 dark:bg-gray-800 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Change {index + 1} of {approval.edits.length}
              </span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2">
              {/* Remove Section */}
              <div className="border-r border-gray-200 dark:border-gray-700">
                <div className="bg-red-50 dark:bg-red-900/20 px-4 py-2 border-b border-red-200 dark:border-red-800">
                  <span className="text-xs font-medium text-red-700 dark:text-red-400">
                    Remove:
                  </span>
                </div>
                <pre className="text-xs p-4 text-red-800 dark:text-red-200 bg-red-50 dark:bg-red-900/10 whitespace-pre-wrap font-mono min-h-[6rem] max-h-48 overflow-auto">
                  {edit.find}
                </pre>
              </div>
              {/* Replace Section */}
              <div>
                <div className="bg-green-50 dark:bg-green-900/20 px-4 py-2 border-b border-green-200 dark:border-green-800">
                  <span className="text-xs font-medium text-green-700 dark:text-green-400">
                    Replace with:
                  </span>
                </div>
                <pre className="text-xs p-4 text-green-800 dark:text-green-200 bg-green-50 dark:bg-green-900/10 whitespace-pre-wrap font-mono min-h-[6rem] max-h-48 overflow-auto">
                  {edit.replace}
                </pre>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* View Mode Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
          <button
            onClick={() => setViewMode('edits')}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              viewMode === 'edits'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Individual Changes (Alt+1)"
          >
            Individual Changes
          </button>
          <button
            onClick={() => setViewMode('split')}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              viewMode === 'split'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Split View (Alt+2)"
          >
            Split View
          </button>
          <button
            onClick={() => setViewMode('unified')}
            className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              viewMode === 'unified'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
            title="Unified Diff (Alt+3)"
          >
            Unified Diff
          </button>
        </div>
        
        {/* Keyboard shortcuts help */}
        <div className="text-xs text-gray-500 dark:text-gray-400 space-x-2">
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+1,2,3</kbd> Switch views</span>
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+E</kbd> Expand</span>
          <span><kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Alt+C</kbd> Collapse</span>
        </div>
      </div>

      {/* Content based on view mode */}
      <div>
        {viewMode === 'unified' && renderUnifiedDiff()}
        {viewMode === 'split' && renderSplitDiff()}
        {viewMode === 'edits' && renderEditsList()}
      </div>
    </div>
  )
}