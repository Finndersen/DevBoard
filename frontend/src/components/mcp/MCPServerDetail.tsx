import { useState, useRef, useEffect } from 'react'
import {
  PencilIcon,
  TrashIcon,
  PlayIcon,
  CheckIcon,
  XMarkIcon,
  WrenchScrewdriverIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline'
import { Button, ConfirmDialog } from '../ui'
import { textColors } from '../../styles/designSystem'
import { useEditableField } from '../../hooks/useEditableField'
import { apiClient } from '../../lib/api'
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

interface JsonSchemaProperty {
  type?: string
  description?: string
  enum?: unknown[]
  items?: { type?: string }
}

interface JsonSchema {
  type?: string
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
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

function formatParameterType(prop: JsonSchemaProperty): string {
  if (prop.enum) return 'enum'
  if (prop.type === 'array' && prop.items?.type) return `${prop.items.type}[]`
  return prop.type || 'any'
}

function ToolParameterList({ inputSchema }: { inputSchema: Record<string, unknown> | null }) {
  if (!inputSchema) {
    return <p className={`text-xs ${textColors.secondary} italic`}>No schema available</p>
  }

  const schema = inputSchema as JsonSchema
  const properties = schema.properties || {}
  const required = new Set(schema.required || [])
  const entries = Object.entries(properties)

  if (entries.length === 0) {
    return <p className={`text-xs ${textColors.secondary} italic`}>No parameters</p>
  }

  return (
    <div className="space-y-2">
      {entries.map(([name, prop]) => (
        <div key={name} className="text-xs">
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-medium text-gray-900 dark:text-gray-100">{name}</span>
            <span className="text-gray-500 dark:text-gray-400">{formatParameterType(prop)}</span>
            {required.has(name) ? (
              <span className="text-red-500 dark:text-red-400 text-[10px]">required</span>
            ) : (
              <span className="text-gray-400 dark:text-gray-500 text-[10px]">optional</span>
            )}
          </div>
          {prop.description && (
            <p className="text-gray-500 dark:text-gray-400 mt-0.5 pl-2">{prop.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function ToolParameterPopover({
  tool,
  isOpen,
  onToggle
}: {
  tool: MCPTool
  isOpen: boolean
  onToggle: () => void
}) {
  const buttonRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return

    function handleClickOutside(event: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        onToggle()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, onToggle])

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={onToggle}
        className={`text-xs flex items-center gap-0.5 hover:text-gray-700 dark:hover:text-gray-200 transition-colors ${textColors.secondary}`}
      >
        {tool.parameter_count} param{tool.parameter_count !== 1 ? 's' : ''}
        <ChevronDownIcon className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div
          ref={popoverRef}
          className="absolute right-0 top-full mt-1 z-10 w-72 max-h-64 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3"
        >
          <ToolParameterList inputSchema={tool.input_schema} />
        </div>
      )}
    </div>
  )
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
    <div className="relative">
      {showTopGradient && (
        <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-b from-white dark:from-gray-900 to-transparent pointer-events-none z-10" />
      )}
      <div
        ref={containerRef}
        className="space-y-2 max-h-[32rem] overflow-y-auto"
      >
        {children}
      </div>
      {showBottomGradient && (
        <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white dark:from-gray-900 to-transparent pointer-events-none z-10" />
      )}
    </div>
  )
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

function ToolCard({
  tool,
  serverId,
  onToolUpdate,
  onSelect
}: {
  tool: MCPTool
  serverId: number
  onToolUpdate: (tool: MCPTool) => void
  onSelect: () => void
}) {
  const [showParams, setShowParams] = useState(false)

  return (
    <div
      className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 cursor-pointer hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
      onClick={onSelect}
    >
      <div className="flex items-center justify-between">
        <h4 className={`font-mono font-medium ${textColors.primary}`}>
          {tool.name}
        </h4>
        <ToolParameterPopover
          tool={tool}
          isOpen={showParams}
          onToggle={() => setShowParams(!showParams)}
        />
      </div>
      <ToolDescriptionEditor
        tool={tool}
        serverId={serverId}
        onUpdate={onToolUpdate}
      />
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

  return (
    <div className="p-6 space-y-6">
      {/* Header with server info, status, and actions */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className={`text-xl font-semibold ${textColors.primary}`}>
              {server.name}
            </h2>
            <VerificationStatusIndicator server={server} />
          </div>
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

      {/* Error message (only shown on failure) */}
      {server.last_verified_error && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-600 dark:text-red-400 font-mono">
            {server.last_verified_error}
          </p>
        </div>
      )}

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
          <ScrollableToolList>
            {server.tools.map(tool => (
              <ToolCard
                key={tool.id}
                tool={tool}
                serverId={server.id}
                onToolUpdate={onToolUpdate}
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
        />
      )}
    </div>
  )
}
