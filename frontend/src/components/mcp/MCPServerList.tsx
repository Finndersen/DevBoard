import { PencilIcon, TrashIcon, PlayIcon, ServerStackIcon } from '@heroicons/react/24/outline'
import { Card, Button, ConfirmDialog } from '../ui'
import { textColors } from '../../styles/designSystem'
import type { MCPServerConfig } from '../../lib/api'
import { useState } from 'react'

interface MCPServerListProps {
  servers: MCPServerConfig[]
  onEdit: (server: MCPServerConfig) => void
  onDelete: (server: MCPServerConfig) => void
  onVerify: (server: MCPServerConfig) => void
  verifyingServerId: number | null
}

export function MCPServerList({
  servers,
  onEdit,
  onDelete,
  onVerify,
  verifyingServerId
}: MCPServerListProps) {
  const [serverToDelete, setServerToDelete] = useState<MCPServerConfig | null>(null)

  const handleDeleteConfirm = () => {
    if (serverToDelete) {
      onDelete(serverToDelete)
      setServerToDelete(null)
    }
  }

  if (servers.length === 0) {
    return (
      <Card className="text-center py-12">
        <ServerStackIcon className="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <h3 className={`text-lg font-medium ${textColors.primary} mb-2`}>
          No MCP Servers Configured
        </h3>
        <p className={`${textColors.secondary} mb-4`}>
          Add an MCP server to enable tool integrations for your agents.
        </p>
      </Card>
    )
  }

  return (
    <>
      <div className="space-y-4">
        {servers.map(server => (
          <Card key={server.id} className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                <ServerStackIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 className={`font-medium ${textColors.primary}`}>
                  {server.name}
                </h3>
                <p className={`text-sm ${textColors.secondary}`}>
                  Type: <span className="font-mono uppercase">{server.server_type}</span>
                  {server.server_type === 'stdio' && 'command' in server.config_json && (
                    <span className="ml-2">
                      Command: <span className="font-mono">{server.config_json.command}</span>
                    </span>
                  )}
                  {server.server_type === 'http' && 'url' in server.config_json && (
                    <span className="ml-2">
                      URL: <span className="font-mono">{server.config_json.url}</span>
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onVerify(server)}
                loading={verifyingServerId === server.id}
                icon={<PlayIcon className="w-4 h-4" />}
              >
                Verify
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onEdit(server)}
                icon={<PencilIcon className="w-4 h-4" />}
              >
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setServerToDelete(server)}
                className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                icon={<TrashIcon className="w-4 h-4" />}
              >
                Delete
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <ConfirmDialog
        isOpen={serverToDelete !== null}
        onClose={() => setServerToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete MCP Server"
        message={`Are you sure you want to delete "${serverToDelete?.name}"? This action cannot be undone.`}
        confirmText="Delete"
        variant="danger"
      />
    </>
  )
}
