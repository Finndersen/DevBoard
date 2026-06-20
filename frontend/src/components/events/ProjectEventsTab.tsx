import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDownIcon, ChevronUpIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { useLogEntries, usePinnedLogEntries } from '../../hooks/useLogEntries'
import { apiClient } from '../../lib/api'
import type { LogEntry, LogEntrySource, LogEntryFilters } from '../../lib/api'
import { ErrorMessage } from '../ui'
import { TableColGroup, EntryRow } from './eventTableComponents'
import { DEFAULT_LIMIT } from './eventTableHelpers'
import { loadingSpinner } from '../../styles/designSystem'

interface ProjectEventsTabProps {
  projectId: number
}

export default function ProjectEventsTab({ projectId }: ProjectEventsTabProps) {
  const navigate = useNavigate()

  const [selectedSource, setSelectedSource] = useState<LogEntrySource | null>(null)
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [offset, setOffset] = useState(0)
  const [allEntries, setAllEntries] = useState<LogEntry[]>([])
  const [pinnedExpanded, setPinnedExpanded] = useState(true)

  // Reset offset and accumulated entries when filters change
  const prevFiltersKey = useRef('')
  const filtersKey = JSON.stringify({ selectedSource, typeFilter })
  useEffect(() => {
    if (prevFiltersKey.current !== filtersKey) {
      prevFiltersKey.current = filtersKey
      setOffset(0)
      setAllEntries([])
    }
  }, [filtersKey])

  const feedFilters: LogEntryFilters = {
    project_id: projectId,
    source: selectedSource,
    type: typeFilter ? `${typeFilter}*` : null,
    pinned: null,
    since: null,
    until: null,
    limit: DEFAULT_LIMIT,
    offset,
    status: null,
  }

  const {
    data: pageEntries,
    loading: feedLoading,
    error: feedError,
    refetch: refetchFeed,
  } = useLogEntries(feedFilters)

  const pinnedFilters: LogEntryFilters = {
    project_id: projectId,
    source: selectedSource,
  }
  const {
    data: pinnedEntries,
    error: pinnedError,
    refetch: refetchPinned,
  } = usePinnedLogEntries(pinnedFilters)

  // Accumulate entries for "load more"
  useEffect(() => {
    if (!pageEntries) return
    if (offset === 0) {
      setAllEntries(pageEntries)
    } else {
      setAllEntries(prev => {
        const existingIds = new Set(prev.map(e => e.id))
        const newOnes = pageEntries.filter(e => !existingIds.has(e.id))
        return [...prev, ...newOnes]
      })
    }
  }, [pageEntries, offset])

  const handleLoadMore = useCallback(() => {
    setOffset(prev => prev + DEFAULT_LIMIT)
  }, [])

  const handleRefresh = useCallback(() => {
    setOffset(0)
    setAllEntries([])
    refetchFeed()
    refetchPinned()
  }, [refetchFeed, refetchPinned])

  const handleToggleSource = useCallback((src: LogEntrySource) => {
    setSelectedSource(prev => (prev === src ? null : src))
  }, [])

  const handlePin = useCallback(async (entry: LogEntry) => {
    await apiClient.updateLogEntry(entry.id, { pinned: !entry.pinned })
    refetchFeed()
    refetchPinned()
  }, [refetchFeed, refetchPinned])

  const handleResolve = useCallback(async (entry: LogEntry) => {
    await apiClient.updateLogEntry(entry.id, { status: 'resolved' })
    refetchFeed()
    refetchPinned()
  }, [refetchFeed, refetchPinned])

  const handleNavigateTask = useCallback((id: number) => {
    navigate(`/tasks/${id}`)
  }, [navigate])

  const hasMore = (pageEntries?.length ?? 0) === DEFAULT_LIMIT

  const sourceToggleButtons: { src: LogEntrySource; label: string }[] = [
    { src: 'developer', label: '👤 Developer' },
    { src: 'system', label: '⚙️ System' },
    { src: 'agent', label: '🤖 Agent' },
  ]

  const sharedRowProps = {
    showProjectLink: false,
    onPin: handlePin,
    onResolve: handleResolve,
    onNavigateTask: handleNavigateTask,
  }

  return (
    <div className="flex-1 flex flex-col overflow-y-auto px-6 py-4 gap-4 min-h-0">
      {/* Filter Bar */}
      <div
        className="flex gap-2 flex-wrap items-center p-2.5 bg-gray-800/50 dark:bg-gray-800/50 border border-gray-700 rounded-lg"
        data-testid="filter-bar"
      >
        {/* Source toggles */}
        <div className="flex gap-1">
          {sourceToggleButtons.map(({ src, label }) => {
            const active = selectedSource === null || selectedSource === src
            return (
              <button
                key={src}
                onClick={() => handleToggleSource(src)}
                className={`rounded-full px-2.5 py-1 text-xs border transition-colors ${
                  active
                    ? 'bg-blue-950 border-blue-600 text-blue-300'
                    : 'bg-gray-700 border-gray-600 text-gray-500'
                }`}
                data-testid={`source-toggle-${src}`}
                aria-pressed={active}
              >
                {label}
              </button>
            )
          })}
        </div>

        {/* Type filter */}
        <input
          type="text"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          placeholder="Filter by type…"
          className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-2 py-1 w-32"
          data-testid="type-filter"
        />

        <div className="ml-auto">
          <button
            onClick={handleRefresh}
            title="Refresh"
            disabled={feedLoading}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs border border-gray-600 text-gray-400 hover:border-gray-400 hover:text-gray-200 disabled:opacity-40 transition-colors"
            data-testid="refresh-button"
          >
            <ArrowPathIcon className={`w-3.5 h-3.5 ${feedLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Pinned error */}
      {pinnedError && <ErrorMessage error={pinnedError} retry={refetchPinned} />}

      {/* Pinned Section */}
      {pinnedEntries && pinnedEntries.length > 0 && (
        <div
          className="border border-amber-900 bg-amber-950/20 rounded-lg overflow-hidden"
          data-testid="pinned-section"
        >
          <button
            className="w-full flex items-center gap-2 px-3 py-2 bg-amber-950/30 text-left"
            onClick={() => setPinnedExpanded(prev => !prev)}
            aria-expanded={pinnedExpanded}
          >
            <span>📌</span>
            <span className="text-sm font-semibold text-amber-400">Pinned ({pinnedEntries.length})</span>
            <span className="ml-auto text-gray-500">
              {pinnedExpanded
                ? <ChevronUpIcon className="w-3 h-3" />
                : <ChevronDownIcon className="w-3 h-3" />}
            </span>
          </button>

          {pinnedExpanded && (
            <table className="w-full border-collapse">
              <TableColGroup />
              <tbody>
                {pinnedEntries.map(entry => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    {...sharedRowProps}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Feed error */}
      {feedError && <ErrorMessage error={feedError} retry={refetchFeed} />}

      {/* Main Feed */}
      <div data-testid="main-feed">
        <table className="w-full border-collapse">
          <TableColGroup />
          <thead>
            <tr className="border-b border-gray-700/50 sticky top-0 bg-gray-900">
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Time</th>
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Source</th>
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Type</th>
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider">Content</th>
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Task</th>
              <th className="py-1.5 px-2 text-left text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Status</th>
              <th className="py-1.5 px-2 text-right text-[10px] font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {allEntries.map(entry => (
              <EntryRow
                key={entry.id}
                entry={entry}
                {...sharedRowProps}
              />
            ))}
          </tbody>
        </table>

        {feedLoading && (
          <div className="flex justify-center py-6">
            <div className={loadingSpinner} />
          </div>
        )}

        {!feedLoading && allEntries.length === 0 && !feedError && (
          <p className="text-sm text-gray-500 italic text-center py-8">No events</p>
        )}
      </div>

      {/* Load more */}
      {hasMore && !feedLoading && (
        <div className="text-center pb-4">
          <button
            onClick={handleLoadMore}
            className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm px-4 py-1.5 rounded transition-colors"
            data-testid="load-more"
          >
            Load more…
          </button>
        </div>
      )}
    </div>
  )
}
