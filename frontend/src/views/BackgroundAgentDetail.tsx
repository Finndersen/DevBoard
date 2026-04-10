import { useState, useCallback } from 'react'
import { CpuChipIcon, PlayIcon, PencilIcon } from '@heroicons/react/24/outline'
import {
  useBackgroundAgent,
  useBackgroundAgentRuns,
  useBackgroundAgentRunStats,
  useTriggerBackgroundAgent,
} from '../hooks/useBackgroundAgents'
import { useUIStore } from '../stores/uiStore'
import { ErrorMessage } from '../components/ui'
import { loadingSpinner, textColors, borderColors, surfaces } from '../styles/designSystem'
import type { BackgroundAgentRun, BackgroundAgentRunStatus, MCPToolSummary } from '../lib/api'
import { useApi } from '../hooks'
import { apiClient } from '../lib/api'
import {
  computeSuccessRate,
  formatTriggeredBy,
  formatDuration,
  formatRelativeTime,
  statusBadgeClass,
} from './backgroundAgentUtils'

interface Props {
  id: string
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: BackgroundAgentRunStatus }) {
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${statusBadgeClass(status)}`}>
      {status}
    </span>
  )
}

// ── Summary card ──────────────────────────────────────────────────────────────

function SummaryCard({ label, value, sub, valueClass = '' }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className={`${surfaces.raised} border ${borderColors.default} rounded-lg p-4`}>
      <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">{label}</div>
      <div className={`text-xl font-semibold ${valueClass || textColors.primary}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  )
}

// ── Run row ───────────────────────────────────────────────────────────────────

function RunRow({ run, onClickRun }: { run: BackgroundAgentRun; onClickRun: (run: BackgroundAgentRun) => void }) {
  const { icon, label } = formatTriggeredBy(run.triggered_by)
  const duration = formatDuration(run.started_at, run.completed_at)
  const started = formatRelativeTime(run.started_at)

  return (
    <>
      <tr
        className="border-b border-gray-700/40 hover:bg-white/[0.03] cursor-pointer"
        onClick={() => onClickRun(run)}
        data-testid="run-row"
      >
        <td className="py-2.5 px-3 text-xs text-gray-300">
          <span className="flex items-center gap-1.5">
            <span className="text-gray-500">{icon}</span>
            {label}
          </span>
        </td>
        <td className="py-2.5 px-3 text-xs text-gray-400 whitespace-nowrap">{started}</td>
        <td className="py-2.5 px-3 text-xs text-gray-400 whitespace-nowrap">{duration}</td>
        <td className="py-2.5 px-3">
          <StatusBadge status={run.status} />
        </td>
        <td className="py-2.5 px-3 text-xs text-gray-500 whitespace-nowrap">
          {run.input_tokens != null || run.output_tokens != null
            ? `${run.input_tokens ?? 0} in · ${run.output_tokens ?? 0} out`
            : '—'}
        </td>
      </tr>
      {run.status === 'failed' && run.error && (
        <tr className="border-b border-gray-700/40 bg-red-950/20">
          <td colSpan={5} className="py-1.5 px-3 text-xs text-red-400">
            ✕ {run.error}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'history' | 'configuration' | 'state'

// ── Main view ─────────────────────────────────────────────────────────────────

export default function BackgroundAgentDetail({ id }: Props) {
  const navigateTo = useUIStore(state => state.navigateTo)

  const { data: agent, loading: agentLoading, error: agentError } = useBackgroundAgent(id)
  const { data: runs, loading: runsLoading, error: runsError, refetch: refetchRuns } = useBackgroundAgentRuns(id)
  const { data: stats } = useBackgroundAgentRunStats(id)
  const { mutate: triggerAgent, loading: triggering } = useTriggerBackgroundAgent()
  const { data: availableTools } = useApi<MCPToolSummary[]>(() => apiClient.getAvailableMCPTools())

  const [activeTab, setActiveTab] = useState<Tab>('history')

  const handleBack = useCallback(() => {
    navigateTo({ type: 'background-agents-list', entityId: '', title: 'Agents' })
  }, [navigateTo])

  const handleEdit = useCallback(() => {
    if (!agent) return
    navigateTo({ type: 'background-agent-edit', entityId: String(agent.id), title: `Edit ${agent.name}` })
  }, [navigateTo, agent])

  const handleTrigger = useCallback(async () => {
    await triggerAgent(id)
    refetchRuns()
  }, [triggerAgent, id, refetchRuns])

  const handleClickRun = useCallback((run: BackgroundAgentRun) => {
    navigateTo({ type: 'background-agent-run', entityId: String(run.id), title: `Run #${run.id}` })
  }, [navigateTo])

  if (agentLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className={loadingSpinner} />
      </div>
    )
  }

  if (agentError || !agent) {
    return (
      <div className="p-6">
        <ErrorMessage error={agentError ? String(agentError) : 'Agent not found'} />
      </div>
    )
  }

  // Summary stats
  const successRate = stats ? computeSuccessRate(stats.completed, stats.total_runs) : null
  const lastRun = runs?.[0] ?? null
  const avgTokens = stats?.avg_input_tokens != null ? Math.round(stats.avg_input_tokens) : null

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className={`flex items-center justify-between px-6 py-4 border-b ${borderColors.default} flex-shrink-0`}>
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm"
            aria-label="Back to agents list"
          >
            ← Agents
          </button>
          <CpuChipIcon className="w-5 h-5 text-purple-400" />
          <h1 className={`text-lg font-semibold ${textColors.primary}`}>{agent.name}</h1>
          <span
            className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
              agent.enabled
                ? 'bg-green-900/50 text-green-400 border border-green-700/50'
                : 'bg-gray-700 text-gray-400'
            }`}
          >
            {agent.enabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-green-900/50 text-green-400 border border-green-700/50 hover:bg-green-900/70 disabled:opacity-50 transition-colors"
          >
            <PlayIcon className="w-3.5 h-3.5" />
            {triggering ? 'Triggering…' : 'Trigger Run'}
          </button>
          <button
            onClick={handleEdit}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border border-gray-600 text-gray-400 hover:border-gray-400 hover:text-gray-200 transition-colors"
          >
            <PencilIcon className="w-3.5 h-3.5" />
            Edit
          </button>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {/* Summary cards */}
        <div className="grid grid-cols-4 gap-3">
          <SummaryCard
            label="Total Runs"
            value={stats ? String(stats.total_runs) : '—'}
          />
          <SummaryCard
            label="Success Rate"
            value={successRate != null ? `${successRate.toFixed(1)}%` : '—'}
            sub={stats ? `${stats.failed} failure${stats.failed !== 1 ? 's' : ''}` : undefined}
            valueClass={successRate != null && successRate >= 80 ? 'text-green-400' : successRate != null ? 'text-red-400' : ''}
          />
          <SummaryCard
            label="Avg Input Tokens"
            value={avgTokens != null ? avgTokens.toLocaleString() : '—'}
          />
          <SummaryCard
            label="Last Run"
            value={lastRun ? formatRelativeTime(lastRun.started_at) : 'Never'}
            sub={lastRun && lastRun.completed_at ? `Completed in ${formatDuration(lastRun.started_at, lastRun.completed_at)}` : undefined}
          />
        </div>

        {/* Tabs */}
        <div className={`flex border-b ${borderColors.default}`}>
          {(['history', 'configuration', 'state'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm capitalize border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'history' ? 'Run History' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'history' && (
          <div>
            {runsError && <ErrorMessage error={runsError} retry={refetchRuns} />}
            {runsLoading && (
              <div className="flex justify-center py-8">
                <div className={loadingSpinner} />
              </div>
            )}
            {!runsLoading && !runsError && (
              <table className="w-full border-collapse">
                <thead>
                  <tr className={`border-b ${borderColors.default}`}>
                    <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Triggered By</th>
                    <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Started</th>
                    <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Duration</th>
                    <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Status</th>
                    <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-gray-500">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {runs && runs.length > 0
                    ? runs.map((run) => (
                        <RunRow key={run.id} run={run} onClickRun={handleClickRun} />
                      ))
                    : (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-sm text-gray-500 italic">
                          No runs yet
                        </td>
                      </tr>
                    )}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'configuration' && (
          <div className="space-y-4">
            <div>
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Prompt</div>
              <pre className={`text-xs font-mono whitespace-pre-wrap ${surfaces.sunken} rounded-lg p-4 text-gray-300 border ${borderColors.default}`}>
                {agent.prompt}
              </pre>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Engine</div>
                <div className="text-sm text-gray-300">{agent.engine}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Model</div>
                <div className="text-sm text-gray-300">{agent.model_id ?? '(default)'}</div>
              </div>
            </div>
            {agent.schedule_triggers.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Schedule Triggers</div>
                <ul className="space-y-1">
                  {agent.schedule_triggers.map((t) => (
                    <li key={t.id} className="text-sm text-gray-300 font-mono">{t.cron_expression}</li>
                  ))}
                </ul>
              </div>
            )}
            {agent.event_triggers.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Event Triggers</div>
                <ul className="space-y-1">
                  {agent.event_triggers.map((t) => (
                    <li key={t.id} className="text-sm text-gray-300 font-mono">{t.event_type_pattern}</li>
                  ))}
                </ul>
              </div>
            )}
            {agent.mcp_tool_ids.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  MCP Tools ({agent.mcp_tool_ids.length})
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {agent.mcp_tool_ids.map((toolId) => {
                    const tool = availableTools?.find(t => t.tool_id === toolId)
                    return (
                      <span
                        key={toolId}
                        className={`text-xs px-2 py-0.5 rounded ${surfaces.sunken} border ${borderColors.default} text-gray-300 flex items-center gap-1.5`}
                      >
                        {tool ? tool.tool_name : `Tool #${toolId}`}
                        {tool && (
                          <span className="text-gray-500 bg-white/5 px-1 rounded">{tool.server_name}</span>
                        )}
                      </span>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'state' && (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Current State</div>
            <pre className={`text-xs font-mono whitespace-pre-wrap ${surfaces.sunken} rounded-lg p-4 text-green-400 border ${borderColors.default}`}>
              {JSON.stringify(agent.state, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
