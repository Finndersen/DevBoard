import { useState, useCallback } from 'react'
import { CpuChipIcon } from '@heroicons/react/24/outline'
import { useBackgroundAgents, useUpdateBackgroundAgent } from '../hooks/useBackgroundAgents'
import type { BackgroundAgent } from '../lib/api'
import ViewHeader from '../components/layout/ViewHeader'
import { ErrorMessage } from '../components/ui'
import { loadingSpinner, textColors, borderColors, statusColors } from '../styles/designSystem'
import { useUIStore } from '../stores/uiStore'
import { useProjects } from '../hooks'
import { filterAgents } from './backgroundAgentFilters'
import type { FilterType } from './backgroundAgentFilters'

interface AgentRowProps {
  agent: BackgroundAgent
  onToggleEnabled: (agent: BackgroundAgent) => void
  onNavigate: (agent: BackgroundAgent) => void
}

function AgentRow({ agent, onToggleEnabled, onNavigate }: AgentRowProps) {
  const hasSchedule = agent.schedule_triggers.length > 0
  const hasEvents = agent.event_triggers.length > 0

  return (
    <tr
      className={`border-b ${borderColors.default} hover:bg-white/[0.02] transition-colors`}
      data-testid="agent-row"
      data-agent-id={agent.id}
    >
      {/* Agent name + description */}
      <td className="py-3 px-4">
        <button
          onClick={() => onNavigate(agent)}
          className={`font-medium ${textColors.primary} hover:text-blue-400 dark:hover:text-blue-400 transition-colors text-left`}
          data-testid={`agent-name-${agent.id}`}
        >
          {agent.name}
        </button>
        {agent.description && (
          <p className={`text-xs ${textColors.muted} mt-0.5`}>{agent.description}</p>
        )}
      </td>

      {/* Status: Running or Enabled toggle */}
      <td className="py-3 px-4">
        {agent.has_active_run ? (
          <div className="flex items-center gap-2" data-testid={`running-badge-${agent.id}`}>
            <div className={`w-2 h-2 rounded-full animate-pulse ${statusColors.success.bg}`} />
            <span className={`text-xs font-medium ${statusColors.success.text}`}>Running now</span>
          </div>
        ) : (
          <button
            role="switch"
            aria-checked={agent.enabled}
            aria-label={`Toggle ${agent.name}`}
            onClick={() => onToggleEnabled(agent)}
            data-testid={`toggle-${agent.id}`}
            className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ${
              agent.enabled ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                agent.enabled ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        )}
      </td>

      {/* Trigger icons */}
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5" data-testid={`triggers-${agent.id}`}>
          {hasSchedule && (
            <span
              title={`Schedule: ${agent.schedule_triggers.map(t => t.cron_expression).join(', ')}`}
              className="w-6 h-6 rounded flex items-center justify-center text-xs bg-blue-950 text-blue-400"
              data-testid="trigger-schedule"
            >
              ⏰
            </span>
          )}
          {hasEvents && (
            <span
              title={`Events: ${agent.event_triggers.map(t => t.event_type_pattern).join(', ')}`}
              className="w-6 h-6 rounded flex items-center justify-center text-xs bg-green-950 text-green-400"
              data-testid="trigger-event"
            >
              ⚡
            </span>
          )}
          {/* Manual trigger always shown */}
          <span
            title="Manual"
            className="w-6 h-6 rounded flex items-center justify-center text-xs bg-purple-950 text-purple-400"
            data-testid="trigger-manual"
          >
            ▶
          </span>
        </div>
      </td>

      {/* Last run */}
      <td className="py-3 px-4">
        <span className={`text-sm ${textColors.muted}`}>—</span>
      </td>

      {/* Run count — not available from list endpoint */}
      <td className="py-3 px-4">
        <span className={`text-sm ${textColors.muted}`}>—</span>
      </td>
    </tr>
  )
}

const FILTER_OPTIONS: { label: string; value: FilterType }[] = [
  { label: 'All', value: 'all' },
  { label: 'Enabled', value: 'enabled' },
  { label: 'Disabled', value: 'disabled' },
  { label: '⏰ Scheduled', value: 'scheduled' },
  { label: '⚡ Event-driven', value: 'event-driven' },
]

export default function BackgroundAgentsList() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all')
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>(undefined)
  const [localAgents, setLocalAgents] = useState<BackgroundAgent[] | null>(null)

  const { data: fetchedAgents, loading, error, refetch } = useBackgroundAgents()
  const { mutate: updateAgent } = useUpdateBackgroundAgent()
  const { data: projects } = useProjects()
  const navigateTo = useUIStore(state => state.navigateTo)

  // Use local state for optimistic updates, fall back to fetched data
  const agents = localAgents ?? fetchedAgents ?? []
  const filteredAgents = filterAgents(agents, activeFilter).filter(
    a => selectedProjectId === undefined || a.project_id === selectedProjectId
  )

  const handleToggleEnabled = useCallback(async (agent: BackgroundAgent) => {
    // Optimistic update
    const updatedAgents = (localAgents ?? fetchedAgents ?? []).map(a =>
      a.id === agent.id ? { ...a, enabled: !a.enabled } : a
    )
    setLocalAgents(updatedAgents)

    try {
      const updated = await updateAgent(agent.id, { enabled: !agent.enabled })
      setLocalAgents(prev => prev?.map(a => (a.id === updated.id ? updated : a)) ?? null)
    } catch {
      // Revert on failure
      setLocalAgents(prev => prev?.map(a => (a.id === agent.id ? agent : a)) ?? null)
    }
  }, [localAgents, fetchedAgents, updateAgent])

  const handleNavigate = useCallback((agent: BackgroundAgent) => {
    navigateTo({ type: 'background-agent-detail', entityId: String(agent.id), title: agent.name })
  }, [navigateTo])

  const handleCreateAgent = useCallback(() => {
    navigateTo({ type: 'background-agent-edit', entityId: 'new', title: 'Create Agent' })
  }, [navigateTo])

  // Sync localAgents back to null when refetch gives fresh data
  const handleRefetch = useCallback(() => {
    setLocalAgents(null)
    refetch()
  }, [refetch])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={CpuChipIcon}
        iconColor="text-purple-600 dark:text-purple-400"
        title="Agents"
        count={agents.length}
        actions={
          <button
            onClick={handleCreateAgent}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3 py-1.5 rounded-md transition-colors"
            data-testid="create-agent-button"
          >
            + Create Agent
          </button>
        }
      />

      {/* Filter bar */}
      <div
        className={`flex items-center gap-2 px-6 py-2.5 border-b ${borderColors.default} flex-shrink-0`}
        data-testid="filter-bar"
      >
        {FILTER_OPTIONS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => setActiveFilter(value)}
            data-testid={`filter-${value}`}
            aria-pressed={activeFilter === value}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              activeFilter === value
                ? 'bg-blue-950 border-blue-600 text-blue-300'
                : 'bg-gray-800/60 border-gray-700 text-gray-500 hover:text-gray-400'
            }`}
          >
            {label}
          </button>
        ))}
        {projects && projects.length > 0 && (
          <>
            <div className="w-px h-4 bg-gray-700" />
            <select
              value={selectedProjectId ?? ''}
              onChange={e => setSelectedProjectId(e.target.value ? Number(e.target.value) : undefined)}
              className="bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 px-2 py-1"
              data-testid="project-filter"
            >
              <option value="">All Projects</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="px-6 pt-4">
            <ErrorMessage error={error} retry={handleRefetch} />
          </div>
        )}

        {loading && !agents.length && (
          <div className="flex justify-center py-12">
            <div className={loadingSpinner} />
          </div>
        )}

        {!loading && !error && agents.length === 0 && (
          <p className={`text-sm italic text-center py-12 ${textColors.muted}`}>
            No background agents configured yet.
          </p>
        )}

        {agents.length > 0 && (
          <table className="w-full border-collapse" data-testid="agents-table">
            <thead>
              <tr className={`border-b ${borderColors.default}`}>
                <th className="py-2 px-4 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="py-2 px-4 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Enabled</th>
                <th className="py-2 px-4 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Triggers</th>
                <th className="py-2 px-4 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Last Run</th>
                <th className="py-2 px-4 text-left text-[11px] font-medium text-gray-500 uppercase tracking-wider">Runs</th>
              </tr>
            </thead>
            <tbody>
              {filteredAgents.map(agent => (
                <AgentRow
                  key={agent.id}
                  agent={agent}
                  onToggleEnabled={handleToggleEnabled}
                  onNavigate={handleNavigate}
                />
              ))}
            </tbody>
          </table>
        )}

        {agents.length > 0 && filteredAgents.length === 0 && (
          <p className={`text-sm italic text-center py-8 ${textColors.muted}`}>
            No agents match the current filter.
          </p>
        )}
      </div>
    </div>
  )
}
