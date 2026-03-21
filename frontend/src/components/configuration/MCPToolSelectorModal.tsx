import { useState, useEffect, useMemo } from 'react'
import { XMarkIcon, MagnifyingGlassIcon, ArrowPathIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline'
import type { MCPToolSummary } from '../../lib/api'
import { apiClient } from '../../lib/api'

interface MCPToolSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (toolIds: number[]) => Promise<void>
  excludeToolIds: number[]
}

export function MCPToolSelectorModal({ isOpen, onClose, onAdd, excludeToolIds }: MCPToolSelectorModalProps) {
  const [availableTools, setAvailableTools] = useState<MCPToolSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedToolIds, setSelectedToolIds] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedServer, setSelectedServer] = useState<string>('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadAvailableTools()
      setSelectedToolIds(new Set())
      setSearchQuery('')
      setSelectedServer('')
    }
  }, [isOpen])

  const loadAvailableTools = async () => {
    try {
      setLoading(true)
      setError(null)
      const tools = await apiClient.getAvailableMCPTools()
      setAvailableTools(tools)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load available tools')
    } finally {
      setLoading(false)
    }
  }

  // Get unique server names for the filter dropdown
  const serverNames = useMemo(() => {
    const names = new Set(availableTools.map(t => t.server_name))
    return Array.from(names).sort()
  }, [availableTools])

  // Filter tools based on search query, server filter, and excluded IDs
  const filteredTools = useMemo(() => {
    return availableTools.filter(tool => {
      // Exclude already assigned tools
      if (excludeToolIds.includes(tool.tool_id)) return false

      // Filter by server
      if (selectedServer && tool.server_name !== selectedServer) return false

      // Filter by search query
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesName = tool.tool_name.toLowerCase().includes(query)
        const matchesDescription = tool.description?.toLowerCase().includes(query) || false
        if (!matchesName && !matchesDescription) return false
      }

      return true
    })
  }, [availableTools, excludeToolIds, selectedServer, searchQuery])

  const handleToggleTool = (toolId: number) => {
    setSelectedToolIds(prev => {
      const next = new Set(prev)
      if (next.has(toolId)) {
        next.delete(toolId)
      } else {
        next.add(toolId)
      }
      return next
    })
  }

  const handleAddSelected = async () => {
    if (selectedToolIds.size === 0) return

    try {
      setAdding(true)
      await onAdd(Array.from(selectedToolIds))
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add tools')
    } finally {
      setAdding(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" onClick={onClose} />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-white/[0.08]">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              Add MCP Tools
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Filters */}
          <div className="p-4 border-b border-gray-200 dark:border-white/[0.08] space-y-3">
            {/* Search */}
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search tools..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Server filter */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600 dark:text-gray-400">Server:</label>
              <select
                value={selectedServer}
                onChange={(e) => setSelectedServer(e.target.value)}
                className="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Servers</option>
                {serverNames.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Tool List */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <ArrowPathIcon className="w-6 h-6 animate-spin text-gray-400" />
                <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">Loading tools...</span>
              </div>
            ) : error ? (
              <div className="text-center py-8">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                <button
                  onClick={loadAvailableTools}
                  className="mt-2 text-sm text-blue-600 hover:text-blue-500"
                >
                  Retry
                </button>
              </div>
            ) : filteredTools.length === 0 ? (
              <div className="text-center py-8">
                <WrenchScrewdriverIcon className="w-10 h-10 mx-auto text-gray-400" />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  {availableTools.length === 0
                    ? 'No MCP tools available. Configure and verify MCP servers first.'
                    : 'No tools match your filters'}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredTools.map((tool) => (
                  <label
                    key={tool.tool_id}
                    className={`flex items-start p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedToolIds.has(tool.tool_id)
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-200 dark:border-white/[0.08] hover:border-gray-300 dark:hover:border-gray-600'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedToolIds.has(tool.tool_id)}
                      onChange={() => handleToggleTool(tool.tool_id)}
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="ml-3 flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {tool.tool_name}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 px-2 py-0.5 bg-gray-100 dark:bg-white/[0.05] rounded">
                          {tool.server_name}
                        </span>
                      </div>
                      {tool.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {tool.description}
                        </p>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-4 border-t border-gray-200 dark:border-white/[0.08]">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {selectedToolIds.size} tool{selectedToolIds.size !== 1 ? 's' : ''} selected
            </span>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSelected}
                disabled={selectedToolIds.size === 0 || adding}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {adding && <ArrowPathIcon className="w-4 h-4 animate-spin" />}
                Add Selected
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
