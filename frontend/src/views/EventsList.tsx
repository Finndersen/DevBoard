import { useState, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { NewspaperIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline'
import { useLogEntries, usePinnedLogEntries } from '../hooks/useLogEntries'
import { useProjects } from '../hooks'
import { apiClient } from '../lib/api'
import type { LogEntry, LogEntrySource, LogEntryFilters } from '../lib/api'
import ViewHeader from '../components/layout/ViewHeader'
import { ErrorMessage } from '../components/ui'
import { loadingSpinner } from '../styles/designSystem'

const DEFAULT_LIMIT = 20

function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function sourceBorderColor(source: LogEntrySource): string {
  switch (source) {
    case 'developer': return 'bg-blue-500'
    case 'system': return 'bg-gray-500'
    case 'agent': return 'bg-purple-500'
  }
}

function sourceLabel(source: LogEntrySource): string {
  switch (source) {
    case 'developer': return '👤 developer'
    case 'system': return '⚙️ system'
    case 'agent': return '🤖 agent'
  }
}

function typeBadgeClass(type: string, source: LogEntrySource): string {
  if (source === 'system') return 'bg-gray-700 text-gray-400'
  if (source === 'agent') return 'bg-purple-950 text-purple-300'
  switch (type) {
    case 'blocker': return 'bg-red-950 text-red-300'
    case 'decision': return 'bg-amber-950 text-amber-300'
    case 'thought': return 'bg-blue-950 text-blue-300'
    default: return 'bg-gray-700 text-gray-400'
  }
}

interface EntryCardProps {
  entry: LogEntry
  projectName?: string
  onPin: (entry: LogEntry) => void
  onResolve: (entry: LogEntry) => void
  onNavigateProject: (id: number) => void
  onNavigateTask: (id: number) => void
}

function EntryCard({
  entry,
  projectName,
  onPin,
  onResolve,
  onNavigateProject,
  onNavigateTask,
}: EntryCardProps) {
  const isInactive = entry.status === 'resolved' || entry.status === 'superseded'
  const bg = entry.source === 'system' || entry.source === 'agent'
    ? 'bg-gray-900/60 dark:bg-gray-900/60'
    : 'bg-gray-800/80 dark:bg-gray-800/80'

  return (
    <div
      className={`rounded-md flex gap-2 items-stretch p-2.5 ${bg} ${isInactive ? 'opacity-50' : ''}`}
      data-testid="entry-card"
      data-source={entry.source}
      data-status={entry.status}
    >
      {/* Left border */}
      <div className={`w-0.5 rounded-full flex-shrink-0 self-stretch ${sourceBorderColor(entry.source)}`} />

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap mb-1">
          <span className="text-xs text-gray-500">{formatRelativeTime(entry.timestamp)}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${typeBadgeClass(entry.type, entry.source)}`}>
            {entry.type}
          </span>
          <span className="text-[10px] text-gray-500">{sourceLabel(entry.source)}</span>
          {entry.status !== 'active' && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-950 text-green-400">
              ✓ {entry.status}
            </span>
          )}
          {entry.pinned && (
            <span className="text-[10px] text-amber-400">📌</span>
          )}
        </div>

        <p className={`text-sm text-gray-200 m-0 ${isInactive ? 'line-through' : ''}`}>
          {entry.content}
        </p>

        {(entry.project_id || entry.task_id) && (
          <div className="mt-1 flex gap-2 flex-wrap">
            {entry.project_id && (
              <button
                onClick={() => onNavigateProject(entry.project_id!)}
                className="text-xs text-blue-400 hover:underline"
              >
                {projectName ?? `Project #${entry.project_id}`}
              </button>
            )}
            {entry.task_id && (
              <>
                {entry.project_id && <span className="text-xs text-gray-600">·</span>}
                <button
                  onClick={() => onNavigateTask(entry.task_id!)}
                  className="text-xs text-blue-400 hover:underline"
                >
                  Task #{entry.task_id}
                </button>
              </>
            )}
          </div>
        )}

        {entry.metadata && (
          <details className="mt-1.5">
            <summary className="text-xs text-gray-500 cursor-pointer select-none">metadata</summary>
            <pre className="mt-1 bg-gray-950 p-2 rounded text-[11px] text-gray-400 overflow-x-auto">
              {JSON.stringify(entry.metadata, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-1 flex-shrink-0">
        {entry.status === 'active' && (
          <button
            onClick={() => onResolve(entry)}
            title="Resolve"
            className="border border-gray-600 rounded text-gray-400 text-[11px] px-1.5 py-0.5 hover:border-gray-400 hover:text-gray-200 transition-colors"
          >
            ✓
          </button>
        )}
        <button
          onClick={() => onPin(entry)}
          title={entry.pinned ? 'Unpin' : 'Pin'}
          className={`border rounded text-[11px] px-1.5 py-0.5 transition-colors ${
            entry.pinned
              ? 'border-amber-600 text-amber-400 hover:border-amber-400'
              : 'border-gray-600 text-gray-500 hover:border-gray-400 hover:text-gray-300'
          }`}
        >
          📌
        </button>
      </div>
    </div>
  )
}

export default function EventsList() {
  const location = useLocation()
  const navigate = useNavigate()

  const params = new URLSearchParams(location.search)

  const [selectedSource, setSelectedSource] = useState<LogEntrySource | null>(() => {
    const raw = params.get('source')
    return (raw as LogEntrySource | null) ?? null
  })
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>(() => {
    const raw = params.get('project_id')
    if (!raw) return undefined
    const n = Number(raw)
    return Number.isNaN(n) ? undefined : n
  })
  const [typeFilter, setTypeFilter] = useState<string>(() => params.get('type') ?? '')
  const [pinnedOnly, setPinnedOnly] = useState<boolean>(() => params.get('pinned') === 'true')
  const [since, setSince] = useState<string>(() => params.get('since') ?? '')
  const [until, setUntil] = useState<string>(() => params.get('until') ?? '')
  const [offset, setOffset] = useState(0)
  const [allEntries, setAllEntries] = useState<LogEntry[]>([])
  const [pinnedExpanded, setPinnedExpanded] = useState(true)

  const { data: projects } = useProjects()

  // Sync filters to URL
  useEffect(() => {
    const p = new URLSearchParams()
    if (selectedSource) p.set('source', selectedSource)
    if (selectedProjectId) p.set('project_id', String(selectedProjectId))
    if (typeFilter) p.set('type', typeFilter)
    if (pinnedOnly) p.set('pinned', 'true')
    if (since) p.set('since', since)
    if (until) p.set('until', until)
    const qs = p.toString()
    navigate(`/events${qs ? `?${qs}` : ''}`, { replace: true })
  }, [selectedSource, selectedProjectId, typeFilter, pinnedOnly, since, until, navigate])

  // Reset offset and accumulated entries when filters change
  const prevFiltersKey = useRef('')
  const filtersKey = JSON.stringify({ selectedSource, selectedProjectId, typeFilter, pinnedOnly, since, until })
  useEffect(() => {
    if (prevFiltersKey.current !== filtersKey) {
      prevFiltersKey.current = filtersKey
      setOffset(0)
      setAllEntries([])
    }
  }, [filtersKey])

  const feedFilters: LogEntryFilters = {
    project_id: selectedProjectId ?? null,
    source: selectedSource,
    type: typeFilter || null,
    pinned: pinnedOnly ? true : null,
    since: since ? `${since}T00:00:00` : null,
    until: until ? `${until}T23:59:59` : null,
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
    project_id: selectedProjectId ?? null,
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

  const handleToggleSource = useCallback((src: LogEntrySource) => {
    // Clicking the active source deselects it (all sources); clicking an inactive source selects only it
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

  const handleNavigateProject = useCallback((id: number) => {
    navigate(`/projects/${id}`)
  }, [navigate])

  const handleNavigateTask = useCallback((id: number) => {
    navigate(`/tasks/${id}`)
  }, [navigate])

  const projectMap = new Map(projects?.map(p => [p.id, p.name]) ?? [])

  const hasMore = (pageEntries?.length ?? 0) === DEFAULT_LIMIT

  const sourceToggleButtons: { src: LogEntrySource; label: string }[] = [
    { src: 'developer', label: '👤 Developer' },
    { src: 'system', label: '⚙️ System' },
    { src: 'agent', label: '🤖 Agent' },
  ]

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={NewspaperIcon}
        iconColor="text-blue-600 dark:text-blue-400"
        title="Events"
        count={allEntries.length}
      />

      <div className="flex-1 flex flex-col overflow-y-auto px-6 py-4 gap-4 min-h-0">
        {/* Filter Bar */}
        <div
          className="flex gap-2 flex-wrap items-center p-2.5 bg-gray-800/50 dark:bg-gray-800/50 border border-gray-700 rounded-lg"
          data-testid="filter-bar"
        >
          {/* Source toggles — single-select; no selection means all sources */}
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

          <div className="w-px h-5 bg-gray-700" />

          {/* Project filter */}
          <select
            value={selectedProjectId ?? ''}
            onChange={e => setSelectedProjectId(e.target.value ? Number(e.target.value) : undefined)}
            className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-2 py-1"
            data-testid="project-filter"
          >
            <option value="">All Projects</option>
            {projects?.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          {/* Type filter */}
          <input
            type="text"
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            placeholder="Filter by type…"
            className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-2 py-1 w-32"
            data-testid="type-filter"
          />

          {/* Pinned toggle */}
          <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={pinnedOnly}
              onChange={e => setPinnedOnly(e.target.checked)}
              className="accent-blue-600"
              data-testid="pinned-toggle"
            />
            📌 Pinned only
          </label>

          <div className="w-px h-5 bg-gray-700" />

          {/* Date range */}
          <label className="flex items-center gap-1 text-xs text-gray-500">
            Since
            <input
              type="date"
              value={since}
              onChange={e => setSince(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-1.5 py-1"
              data-testid="since-filter"
            />
          </label>
          <label className="flex items-center gap-1 text-xs text-gray-500">
            Until
            <input
              type="date"
              value={until}
              onChange={e => setUntil(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-1.5 py-1"
              data-testid="until-filter"
            />
          </label>
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
              <div className="divide-y divide-gray-800">
                {pinnedEntries.map(entry => (
                  <div key={entry.id} className="p-2">
                    <EntryCard
                      entry={entry}
                      projectName={entry.project_id ? projectMap.get(entry.project_id) : undefined}
                      onPin={handlePin}
                      onResolve={handleResolve}
                      onNavigateProject={handleNavigateProject}
                      onNavigateTask={handleNavigateTask}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Feed error */}
        {feedError && <ErrorMessage error={feedError} retry={refetchFeed} />}

        {/* Main Feed */}
        <div className="flex flex-col gap-1.5" data-testid="main-feed">
          {allEntries.map(entry => (
            <EntryCard
              key={entry.id}
              entry={entry}
              projectName={entry.project_id ? projectMap.get(entry.project_id) : undefined}
              onPin={handlePin}
              onResolve={handleResolve}
              onNavigateProject={handleNavigateProject}
              onNavigateTask={handleNavigateTask}
            />
          ))}

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

    </div>
  )
}
