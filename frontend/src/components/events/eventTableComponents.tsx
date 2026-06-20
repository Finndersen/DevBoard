import type { LogEntry } from '../../lib/api'
import { formatRelativeTime, sourceDotColor, typeBadgeClass } from './eventTableHelpers'

export function TableColGroup() {
  return (
    <colgroup>
      <col style={{ width: '5.5rem' }} />
      <col style={{ width: '5.5rem' }} />
      <col style={{ width: '7rem' }} />
      <col />
      <col style={{ width: '9rem' }} />
      <col style={{ width: '5rem' }} />
      <col style={{ width: '5rem' }} />
    </colgroup>
  )
}

export interface EntryRowProps {
  entry: LogEntry
  projectName?: string
  showProjectLink?: boolean
  onPin: (entry: LogEntry) => void
  onResolve: (entry: LogEntry) => void
  onNavigateProject?: (id: number) => void
  onNavigateTask: (id: number) => void
}

export function EntryRow({
  entry,
  projectName,
  showProjectLink = true,
  onPin,
  onResolve,
  onNavigateProject,
  onNavigateTask,
}: EntryRowProps) {
  const isInactive = entry.status === 'resolved' || entry.status === 'superseded'

  return (
    <tr
      className={`border-b border-gray-700/50 hover:bg-white/[0.03] ${isInactive ? 'opacity-50' : ''}`}
      data-testid="entry-row"
      data-source={entry.source}
      data-status={entry.status}
    >
      {/* Timestamp */}
      <td className="text-gray-500 text-xs whitespace-nowrap py-1.5 px-2">
        {formatRelativeTime(entry.timestamp)}
      </td>

      {/* Source */}
      <td className="py-1.5 px-2">
        <span className="flex items-center gap-1.5">
          <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${sourceDotColor(entry.source)}`} />
          <span className="text-xs text-gray-400">{entry.source}</span>
        </span>
      </td>

      {/* Type */}
      <td className="py-1.5 px-2">
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${typeBadgeClass(entry.type, entry.source)}`}>
          {entry.type}
        </span>
      </td>

      {/* Content */}
      <td className="py-1.5 px-2 max-w-0">
        <p className={`text-xs text-gray-200 truncate ${isInactive ? 'line-through' : ''}`} title={entry.content}>
          {entry.content}
        </p>
        {entry.metadata && (
          <details className="mt-1.5">
            <summary className="text-xs text-gray-500 cursor-pointer select-none">metadata</summary>
            <pre className="mt-1 bg-gray-950 p-2 rounded text-[11px] text-gray-400 overflow-x-auto">
              {JSON.stringify(entry.metadata, null, 2)}
            </pre>
          </details>
        )}
      </td>

      {/* Project / Task */}
      <td className="py-1.5 px-2 whitespace-nowrap">
        {showProjectLink && entry.project_id && (
          <button
            onClick={() => onNavigateProject(entry.project_id!)}
            className="text-xs text-blue-400 hover:underline"
          >
            {projectName ?? `Project #${entry.project_id}`}
          </button>
        )}
        {showProjectLink && entry.project_id && entry.task_id && (
          <span className="text-xs text-gray-600 mx-1">·</span>
        )}
        {entry.task_id && (
          <button
            onClick={() => onNavigateTask(entry.task_id!)}
            className="text-xs text-blue-400 hover:underline"
          >
            Task #{entry.task_id}
          </button>
        )}
      </td>

      {/* Status */}
      <td className="py-1.5 px-2 whitespace-nowrap">
        {entry.status !== 'active' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-950 text-green-400">
            {entry.status}
          </span>
        )}
        {entry.pinned && (
          <span className="text-[10px] text-amber-400">📌</span>
        )}
      </td>

      {/* Actions */}
      <td className="py-1.5 px-2 whitespace-nowrap text-right">
        {entry.status === 'active' && (
          <button
            onClick={() => onResolve(entry)}
            title="Resolve"
            className="border border-gray-600 rounded text-gray-400 text-[11px] px-1.5 py-0.5 hover:border-gray-400 hover:text-gray-200 transition-colors mr-1"
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
      </td>
    </tr>
  )
}
