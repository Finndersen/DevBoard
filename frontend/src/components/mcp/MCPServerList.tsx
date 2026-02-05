import { ServerStackIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import type { MCPServerConfig } from '../../lib/api'

interface MCPServerListProps {
  servers: MCPServerConfig[]
  selectedId: number | null
  onSelect: (server: MCPServerConfig) => void
}

function getStatusIndicator(server: MCPServerConfig & { last_verified_success?: boolean | null }) {
  const verifiedSuccess = 'last_verified_success' in server ? server.last_verified_success : null

  if (verifiedSuccess === true) {
    return <span className="w-2 h-2 rounded-full bg-green-500" title="Verified" />
  } else if (verifiedSuccess === false) {
    return <span className="w-2 h-2 rounded-full bg-red-500" title="Verification failed" />
  }
  return <span className="w-2 h-2 rounded-full bg-gray-400" title="Not verified" />
}

export function MCPServerList({
  servers,
  selectedId,
  onSelect
}: MCPServerListProps) {
  if (servers.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <ServerStackIcon className="w-10 h-10 mx-auto text-gray-400 mb-3" />
        <p className={`text-sm ${textColors.secondary}`}>
          No MCP servers configured
        </p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-200 dark:divide-gray-700">
      {servers.map(server => (
        <button
          key={server.id}
          onClick={() => onSelect(server)}
          className={`w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
            selectedId === server.id
              ? 'bg-blue-50 dark:bg-blue-900/30 border-l-2 border-l-blue-500'
              : ''
          }`}
        >
          <div className="flex items-center gap-3">
            {getStatusIndicator(server)}
            <div className="min-w-0 flex-1">
              <h3 className={`font-medium ${textColors.primary} truncate`}>
                {server.name}
              </h3>
              <p className={`text-xs ${textColors.secondary} uppercase`}>
                {server.server_type}
              </p>
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
