import { useState, useRef, useEffect } from 'react'
import {
  TrashIcon,
  PlayIcon,
  PencilIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'
import { Button, ConfirmDialog } from '../ui'
import { textColors } from '../../styles/designSystem'
import type { MCPServerDetail as MCPServerDetailType, MCPTool } from '../../lib/api'
import { ToolTestModal } from './ToolTestModal'

interface MCPServerDetailProps {
  server: MCPServerDetailType
  onEdit: () => void
  onDelete: () => void
  onVerify: () => void
  onToolUpdate: (tool: MCPTool) => void
  verifying: boolean
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function ScrollableToolList({ children }: { children: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [showTopGradient, setShowTopGradient] = useState(false)
  const [showBottomGradient, setShowBottomGradient] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    function updateGradients() {
      if (!container) return
      const { scrollTop, scrollHeight, clientHeight } = container
      setShowTopGradient(scrollTop > 0)
      setShowBottomGradient(scrollTop + clientHeight < scrollHeight - 1)
    }

    updateGradients()
    container.addEventListener('scroll', updateGradients)
    const resizeObserver = new ResizeObserver(updateGradients)
    resizeObserver.observe(container)

    return () => {
      container.removeEventListener('scroll', updateGradients)
      resizeObserver.disconnect()
    }
  }, [children])

  return (
    <div className="relative flex-1 min-h-0 flex flex-col">
      {showTopGradient && (
        <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white dark:from-gray-900 to-transparent pointer-events-none z-10" />
      )}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 overflow-y-auto"
      >
        {children}
      </div>
      {showBottomGradient && (
        <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white dark:from-gray-900 to-transparent pointer-events-none z-10" />
      )}
    </div>
  )
}

function ToolRow({ tool, nameWidth, onSelect }: { tool: MCPTool; nameWidth: number; onSelect: () => void }) {
  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      onClick={onSelect}
    >
      <span
        className={`font-mono font-medium text-sm ${textColors.primary} shrink-0`}
        style={{ width: `${nameWidth}ch` }}
      >
        {tool.name}
      </span>
      <span className={`text-sm ${textColors.secondary} truncate flex-1 min-w-0`}>
        {tool.description || <span className="italic">No description</span>}
      </span>
      <span className={`text-xs ${textColors.secondary} shrink-0 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full`}>
        {tool.parameter_count} param{tool.parameter_count !== 1 ? 's' : ''}
      </span>
    </div>
  )
}

function VerificationStatusIndicator({ server }: { server: MCPServerDetailType }) {
  if (!server.last_verified_at) {
    return (
      <span className={`text-xs ${textColors.secondary}`}>
        Not verified
      </span>
    )
  }

  return (
    <div className="flex items-center gap-2">
      {server.last_verified_success ? (
        <>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-xs text-green-600 dark:text-green-400 font-medium">Connected</span>
          </span>
        </>
      ) : (
        <>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-xs text-red-600 dark:text-red-400 font-medium">Failed</span>
          </span>
        </>
      )}
      <span className={`text-xs ${textColors.secondary}`}>
        {formatRelativeTime(server.last_verified_at)}
      </span>
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
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null)

  const maxToolNameLength = server.tools.reduce((max, t) => Math.max(max, t.name.length), 0)

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Server header bar */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className={`text-xl font-semibold ${textColors.primary}`}>
                {server.name}
              </h2>
              <VerificationStatusIndicator server={server} />
            </div>
            <div className={`flex items-center gap-3 text-sm ${textColors.secondary} mt-1`}>
              <span>
                Type: <span className="font-mono uppercase">{server.server_type}</span>
              </span>
              {server.server_type === 'stdio' && 'command' in server.config_json && (
                <span>
                  Command: <span className="font-mono">{server.config_json.command}</span>
                </span>
              )}
              {server.server_type === 'http' && 'url' in server.config_json && (
                <span>
                  URL: <span className="font-mono">{server.config_json.url}</span>
                </span>
              )}
            </div>
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

        {server.last_verified_error && (
          <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400 font-mono">
              {server.last_verified_error}
            </p>
          </div>
        )}
      </div>

      {/* Tools section */}
      <div className="flex flex-col flex-1 min-h-0 px-6 pt-4">
        <div className="flex items-center justify-between mb-3 shrink-0">
          <h3 className={`text-sm font-medium ${textColors.primary} flex items-center gap-2`}>
            <WrenchScrewdriverIcon className="w-5 h-5" />
            Tools ({server.tools.length})
          </h3>
          {server.tools.length > 0 && (
            <span className={`text-xs ${textColors.secondary}`}>
              Select a tool to edit its description or test it
            </span>
          )}
        </div>

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
          <ScrollableToolList>
            {server.tools.map(tool => (
              <ToolRow
                key={tool.id}
                tool={tool}
                nameWidth={maxToolNameLength}
                onSelect={() => setSelectedTool(tool)}
              />
            ))}
          </ScrollableToolList>
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

      {selectedTool && (
        <ToolTestModal
          isOpen={true}
          onClose={() => setSelectedTool(null)}
          tool={selectedTool}
          serverId={server.id}
          onToolUpdate={onToolUpdate}
        />
      )}
    </div>
  )
}
