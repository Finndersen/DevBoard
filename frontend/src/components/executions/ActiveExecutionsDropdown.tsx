import { useState, useRef, useEffect, useCallback } from 'react'
import { ArrowPathIcon, StopIcon, DocumentTextIcon } from '@heroicons/react/24/outline'
import { useActiveExecutions } from '../../hooks/useActiveExecutions'
import { useUIStore } from '../../stores/uiStore'
import { apiClient } from '../../lib/api'
import type { ActiveExecutionItem } from '../../lib/api'

function formatElapsed(startedAt: string): string {
  const diffMs = Date.now() - new Date(startedAt).getTime()
  const secs = Math.floor(diffMs / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function formatAgentRole(role: string): string {
  return role
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function AgentIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21M6.75 8.25h10.5a2.25 2.25 0 0 1 2.25 2.25v5.25a2.25 2.25 0 0 1-2.25 2.25H6.75a2.25 2.25 0 0 1-2.25-2.25v-5.25a2.25 2.25 0 0 1 2.25-2.25Z" />
    </svg>
  )
}

export default function ActiveExecutionsDropdown() {
  const [isOpen, setIsOpen] = useState(false)
  const { data, loading, refetch } = useActiveExecutions(isOpen)
  const openTab = useUIStore(s => s.openTab)
  const [interruptingIds, setInterruptingIds] = useState<Set<number>>(new Set())
  const panelRef = useRef<HTMLDivElement>(null)

  const executions = data?.executions ?? []
  const count = executions.length

  const handleRefresh = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    refetch()
  }, [refetch])

  const handleOpenTask = (e: React.MouseEvent, item: ActiveExecutionItem) => {
    e.stopPropagation()
    if (item.task_id) {
      openTab({ type: 'task', entityId: String(item.task_id), title: item.task_title || `Task #${item.task_id}` })
      setIsOpen(false)
    }
  }

  const handleInterrupt = async (e: React.MouseEvent, item: ActiveExecutionItem) => {
    e.stopPropagation()
    setInterruptingIds(prev => new Set(prev).add(item.conversation_id))
    try {
      await apiClient.interruptConversation(item.conversation_id)
      await refetch()
    } finally {
      setInterruptingIds(prev => {
        const next = new Set(prev)
        next.delete(item.conversation_id)
        return next
      })
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-md text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        aria-label="Active agent executions"
      >
        <AgentIcon className={`w-5 h-5 ${count > 0 ? 'text-green-500 dark:text-green-400' : ''}`} />
        {count > 0 && (
          <>
            {/* Animated pulse ring to indicate active work */}
            <span className="absolute inset-0 rounded-md animate-ping opacity-30 bg-green-400" />
            <span className="absolute top-0 right-0 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-green-500 rounded-full z-10">
              {count}
            </span>
          </>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
          {/* Header */}
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
              Active Agents ({count})
            </h3>
            <button
              onClick={handleRefresh}
              className="p-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title="Refresh"
            >
              <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto">
            {count === 0 && !loading && (
              <div className="p-6 text-center">
                <AgentIcon className="mx-auto h-10 w-10 text-gray-300 dark:text-gray-600" />
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">No active agent executions</p>
              </div>
            )}

            {count > 0 && (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {executions.map(item => (
                  <div
                    key={item.conversation_id}
                    className="p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      {/* Pulsing status dot */}
                      <div className="flex-shrink-0 mt-1.5">
                        <span className="relative flex h-2.5 w-2.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
                        </span>
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                          {item.task_title ?? `Conversation #${item.conversation_id}`}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {formatAgentRole(item.agent_role)} · {formatElapsed(item.started_at)}
                        </p>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {item.task_id !== null && (
                          <button
                            onClick={(e) => handleOpenTask(e, item)}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                            title="Open task"
                          >
                            <DocumentTextIcon className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                          </button>
                        )}
                        <button
                          onClick={(e) => handleInterrupt(e, item)}
                          disabled={interruptingIds.has(item.conversation_id)}
                          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50"
                          title="Interrupt agent"
                        >
                          <StopIcon className="w-3.5 h-3.5 text-red-500 dark:text-red-400" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
