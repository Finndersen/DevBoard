import { useState } from 'react'
import {
  PencilIcon,
  TrashIcon,
  PlayIcon,
  CheckIcon,
  XMarkIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { Button, ConfirmDialog } from '../ui'
import { textColors } from '../../styles/designSystem'
import { useEditableField } from '../../hooks/useEditableField'
import { apiClient } from '../../lib/api'
import type { MCPServerDetail as MCPServerDetailType, MCPTool } from '../../lib/api'

interface MCPServerDetailProps {
  server: MCPServerDetailType
  onEdit: () => void
  onDelete: () => void
  onVerify: () => void
  onToolUpdate: (tool: MCPTool) => void
  verifying: boolean
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return 'Never'
  const date = new Date(isoString)
  return date.toLocaleString()
}

function ToolDescriptionEditor({
  tool,
  serverId,
  onUpdate
}: {
  tool: MCPTool
  serverId: number
  onUpdate: (tool: MCPTool) => void
}) {
  const {
    isEditing,
    editedValue,
    setEditedValue,
    saving,
    error,
    startEditing,
    cancelEditing,
    save
  } = useEditableField(tool.description || '', async (value) => {
    const updated = await apiClient.updateMCPTool(serverId, tool.id, { description: value || null })
    onUpdate(updated)
  })

  if (isEditing) {
    return (
      <div className="mt-1">
        <textarea
          value={editedValue}
          onChange={(e) => setEditedValue(e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          rows={2}
          disabled={saving}
        />
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        <div className="flex gap-1 mt-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={save}
            loading={saving}
            icon={<CheckIcon className="w-3 h-3" />}
          >
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={cancelEditing}
            disabled={saving}
            icon={<XMarkIcon className="w-3 h-3" />}
          >
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-1 mt-1">
      <p className={`text-sm ${textColors.secondary} flex-1`}>
        {tool.description || <span className="italic">No description</span>}
      </p>
      <button
        onClick={startEditing}
        className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        title="Edit description"
      >
        <PencilIcon className="w-3 h-3" />
      </button>
    </div>
  )
}

export function MCPServerDetail({
  server,
  onEdit,
  onDelete,
  onVerify,
  onToolUpdate,
  verifying
}: MCPServerDetailProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  return (
    <div className="p-6 space-y-6">
      {/* Header with server info and actions */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className={`text-xl font-semibold ${textColors.primary}`}>
            {server.name}
          </h2>
          <p className={`text-sm ${textColors.secondary} mt-1`}>
            Type: <span className="font-mono uppercase">{server.server_type}</span>
          </p>
          {server.server_type === 'stdio' && 'command' in server.config_json && (
            <p className={`text-sm ${textColors.secondary}`}>
              Command: <span className="font-mono">{server.config_json.command}</span>
            </p>
          )}
          {server.server_type === 'http' && 'url' in server.config_json && (
            <p className={`text-sm ${textColors.secondary}`}>
              URL: <span className="font-mono">{server.config_json.url}</span>
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onVerify}
            loading={verifying}
            icon={<PlayIcon className="w-4 h-4" />}
          >
            Verify
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onEdit}
            icon={<PencilIcon className="w-4 h-4" />}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            icon={<TrashIcon className="w-4 h-4" />}
          >
            Delete
          </Button>
        </div>
      </div>

      {/* Verification status */}
      <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
        <h3 className={`text-sm font-medium ${textColors.primary} mb-2`}>
          Verification Status
        </h3>
        {server.last_verified_at ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              {server.last_verified_success ? (
                <>
                  <CheckCircleIcon className="w-5 h-5 text-green-500" />
                  <span className="text-green-600 dark:text-green-400 font-medium">Connected</span>
                </>
              ) : (
                <>
                  <XCircleIcon className="w-5 h-5 text-red-500" />
                  <span className="text-red-600 dark:text-red-400 font-medium">Failed</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <ClockIcon className="w-4 h-4" />
              <span>Last verified: {formatDateTime(server.last_verified_at)}</span>
            </div>
            {server.last_verified_error && (
              <p className="text-sm text-red-600 dark:text-red-400 font-mono bg-red-50 dark:bg-red-900/20 p-2 rounded">
                {server.last_verified_error}
              </p>
            )}
          </div>
        ) : (
          <p className={`text-sm ${textColors.secondary}`}>
            Not yet verified. Click Verify to fetch tools.
          </p>
        )}
      </div>

      {/* Tools list */}
      <div>
        <h3 className={`text-sm font-medium ${textColors.primary} mb-3 flex items-center gap-2`}>
          <WrenchScrewdriverIcon className="w-5 h-5" />
          Cached Tools ({server.tools.length})
        </h3>
        {server.tools.length === 0 ? (
          <div className="text-center py-8 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
            <WrenchScrewdriverIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
            <p className={`${textColors.secondary}`}>
              No tools cached
            </p>
            <p className={`text-sm ${textColors.secondary} mt-1`}>
              Click Verify to fetch tools from the server
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {server.tools.map(tool => (
              <div
                key={tool.id}
                className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center justify-between">
                  <h4 className={`font-mono font-medium ${textColors.primary}`}>
                    {tool.name}
                  </h4>
                  <span className={`text-xs ${textColors.secondary}`}>
                    {tool.parameter_count} parameter{tool.parameter_count !== 1 ? 's' : ''}
                  </span>
                </div>
                <ToolDescriptionEditor
                  tool={tool}
                  serverId={server.id}
                  onUpdate={onToolUpdate}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={onDelete}
        title="Delete MCP Server"
        message={`Are you sure you want to delete "${server.name}"? This will also delete all cached tools. This action cannot be undone.`}
        confirmText="Delete"
        variant="danger"
      />
    </div>
  )
}
