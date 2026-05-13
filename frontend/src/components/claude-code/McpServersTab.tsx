import { useState, useEffect, useCallback } from 'react'
import { ArrowPathIcon } from '@heroicons/react/24/outline'
import { statusColors, textColors, borderColors } from '../../styles/designSystem'
import { apiClient } from '../../lib/api'
import type { McpServer } from '../../lib/api'

export default function McpServersTab() {
  const [servers, setServers] = useState<McpServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const fetchServers = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getClaudeCodeMcpServers()
      setServers(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load MCP servers')
    } finally {
      if (isRefresh) setIsRefreshing(false)
      else setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchServers()
  }, [fetchServers])

  const getStatusDisplay = (status: McpServer['status']) => {
    switch (status) {
      case 'connected':
        return { icon: '✓', text: 'Connected', color: 'text-green-600 dark:text-green-400' }
      case 'needs_auth':
        return { icon: '!', text: 'Needs authentication', color: 'text-amber-600 dark:text-amber-400' }
      case 'failed':
        return { icon: '✗', text: 'Failed to connect', color: 'text-red-600 dark:text-red-400' }
    }
  }

  const getTypeDisplay = (type: McpServer['type']) => {
    switch (type) {
      case 'remote':
        return { label: 'Remote', bg: 'bg-blue-100 dark:bg-blue-900/40', text: 'text-blue-700 dark:text-blue-300' }
      case 'local':
        return { label: 'Local', bg: 'bg-green-100 dark:bg-green-900/40', text: 'text-green-700 dark:text-green-300' }
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden p-6">
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h3 className={`text-base font-semibold ${textColors.primary}`}>MCP Servers</h3>
        <button
          onClick={() => fetchServers(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md transition-colors"
        >
          <ArrowPathIcon className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className={`mb-4 p-3 rounded-md ${statusColors.error.bg} ${statusColors.error.border} border`}>
          <p className={statusColors.error.text}>{error}</p>
        </div>
      )}

      {servers.length === 0 ? (
        <div className={`flex items-center justify-center flex-1 ${textColors.muted}`}>
          <p>No MCP servers configured</p>
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800/50">
              <tr className={`border-b ${borderColors.default}`}>
                <th className={`text-left px-4 py-2 font-medium ${textColors.muted}`}>Name</th>
                <th className={`text-left px-4 py-2 font-medium ${textColors.muted}`}>Type</th>
                <th className={`text-left px-4 py-2 font-medium ${textColors.muted}`}>URL / Command</th>
                <th className={`text-left px-4 py-2 font-medium ${textColors.muted}`}>Status</th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => {
                const statusDisplay = getStatusDisplay(server.status)
                const typeDisplay = getTypeDisplay(server.type)
                return (
                  <tr key={server.name} className={`border-b ${borderColors.default} hover:bg-gray-50 dark:hover:bg-white/[0.05]`}>
                    <td className={`px-4 py-3 ${textColors.primary}`}>{server.name}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-1 text-xs font-medium rounded-md ${typeDisplay.bg} ${typeDisplay.text}`}>
                        {typeDisplay.label}
                      </span>
                    </td>
                    <td className={`px-4 py-3 text-xs ${textColors.muted} font-mono`}>{server.url_or_command}</td>
                    <td className={`px-4 py-3 font-medium ${statusDisplay.color}`}>
                      {statusDisplay.icon} {statusDisplay.text}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
