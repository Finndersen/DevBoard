import { useState, useEffect, useCallback } from 'react'
import Modal from '../ui/Modal'
import type { AgentConfigResponse, ToolInfo } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { formatAgentRoleDisplayName } from '../../utils/agentRoles'

interface AgentInspectorModalProps {
  isOpen: boolean
  onClose: () => void
  conversationId: number
}

type FilterType = 'all' | 'role' | 'mcp' | 'builtin'

const FILTER_LABELS: Record<FilterType, string> = {
  all: 'All',
  role: 'Role',
  mcp: 'MCP',
  builtin: 'Builtin',
}

function getSourceBadgeClasses(source: string): string {
  if (source === 'role') return 'text-purple-300 bg-purple-900/50'
  if (source === 'mcp') return 'text-green-300 bg-green-900/50'
  return 'text-amber-300 bg-amber-900/50'
}

function getSourceBadgeText(tool: ToolInfo): string {
  if (tool.source === 'mcp') return `MCP: ${tool.server_name}`
  return tool.source === 'role' ? 'Role' : 'Builtin'
}

export default function AgentInspectorModal({ isOpen, onClose, conversationId }: AgentInspectorModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AgentConfigResponse | null>(null)
  const [activeFilter, setActiveFilter] = useState<FilterType>('all')
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set())

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiClient.getConversationAgentConfig(conversationId)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent configuration')
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  useEffect(() => {
    if (!isOpen) {
      setData(null)
      setActiveFilter('all')
      setExpandedSchemas(new Set())
      return
    }
    fetchConfig()
  }, [isOpen, fetchConfig])

  const toggleSchema = (toolKey: string) => {
    setExpandedSchemas(prev => {
      const next = new Set(prev)
      if (next.has(toolKey)) {
        next.delete(toolKey)
      } else {
        next.add(toolKey)
      }
      return next
    })
  }

  const allTools = data
    ? [...data.role_tools, ...data.mcp_tools, ...data.builtin_tools]
    : []

  const filteredTools =
    activeFilter === 'all' ? allTools : allTools.filter(t => t.source === activeFilter)

  const getToolCount = (filter: FilterType) =>
    filter === 'all' ? allTools.length : allTools.filter(t => t.source === filter).length

  const title = data ? (
    <span className="flex items-center gap-2">
      Agent Inspector
      <span className="bg-blue-900 text-blue-300 text-xs px-2 py-0.5 rounded-full font-medium">
        {formatAgentRoleDisplayName(data.agent_role)}
      </span>
    </span>
  ) : (
    'Agent Inspector'
  )

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="screen" scrollable={false}>
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <span className="ml-3 text-gray-400">Loading agent configuration...</span>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <p className="text-red-400 text-sm">{error}</p>
          <button
            onClick={fetchConfig}
            className="text-sm text-blue-400 hover:text-blue-300 underline"
          >
            Retry
          </button>
        </div>
      )}

      {data && !loading && (
        <div className="overflow-y-auto flex-1">
          <div className="grid grid-cols-2 gap-4 p-1">
            {/* Behaviour Guidelines — left column */}
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="flex justify-between items-center px-4 py-2 bg-gray-800/50 border-b border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300">Behaviour Guidelines</h3>
                <span className="text-xs text-gray-500 italic">System prompt</span>
              </div>
              <div className="px-4 py-3 max-h-[260px] overflow-y-auto">
                <pre className="font-mono text-xs text-gray-300 whitespace-pre-wrap break-words">
                  {data.behaviour_guidelines}
                </pre>
              </div>
            </div>

            {/* Context Content — right column */}
            <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="flex justify-between items-center px-4 py-2 bg-gray-800/50 border-b border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300">Context Content</h3>
                <span className="text-xs text-gray-500 italic">Provided as initial context to agent</span>
              </div>
              <div className="px-4 py-3 max-h-[260px] overflow-y-auto">
                <pre className="font-mono text-xs text-gray-300 whitespace-pre-wrap break-words">
                  {data.context_content}
                </pre>
              </div>
            </div>

            {/* Custom Instructions — full width, only if present */}
            {data.custom_instructions && (
              <div className="col-span-2 bg-stone-900 border border-amber-800 rounded-lg overflow-hidden">
                <div className="flex justify-between items-center px-4 py-2 bg-amber-900/20 border-b border-amber-800">
                  <h3 className="text-sm font-semibold text-amber-300">Custom Instructions</h3>
                  <span className="text-xs text-gray-500 italic">Appended to system prompt</span>
                </div>
                <div className="px-4 py-3 max-h-[200px] overflow-y-auto">
                  <pre className="font-mono text-xs text-gray-300 whitespace-pre-wrap break-words">
                    {data.custom_instructions}
                  </pre>
                </div>
              </div>
            )}

            {/* Tools — full width */}
            <div className="col-span-2 bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
              <div className="flex justify-between items-center px-4 py-2 bg-gray-800/50 border-b border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300">Tools</h3>
                <span className="text-xs text-gray-500 italic">{allTools.length} tools</span>
              </div>
              <div className="flex gap-2 px-4 py-2 bg-gray-900/80 border-b border-gray-700">
                {(['all', 'role', 'mcp', 'builtin'] as FilterType[]).map(filter => (
                  <button
                    key={filter}
                    onClick={() => setActiveFilter(filter)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      activeFilter === filter
                        ? 'border-blue-500 text-blue-300 bg-blue-900/30'
                        : 'border-gray-700 text-gray-500 hover:text-gray-400'
                    }`}
                  >
                    {FILTER_LABELS[filter]} ({getToolCount(filter)})
                  </button>
                ))}
              </div>
              <div className="max-h-[300px] overflow-y-auto px-4 py-2">
                <ul className="divide-y divide-gray-800">
                  {filteredTools.map(tool => (
                    <li key={`${tool.source}-${tool.name}`} className="py-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-blue-300">{tool.name}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${getSourceBadgeClasses(tool.source)}`}>
                          {getSourceBadgeText(tool)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {tool.source === 'builtin' ? 'Built-in engine tool' : tool.description}
                      </p>
                      {tool.input_schema && (
                        <>
                          <button
                            onClick={() => toggleSchema(`${tool.source}-${tool.name}`)}
                            className="text-xs text-gray-600 hover:text-gray-500 mt-1"
                          >
                            {expandedSchemas.has(`${tool.source}-${tool.name}`) ? '▼' : '▶'} Input schema
                          </button>
                          {expandedSchemas.has(`${tool.source}-${tool.name}`) && (
                            <pre className="font-mono text-xs text-gray-400 bg-gray-950 p-2 rounded mt-1 overflow-x-auto">
                              {JSON.stringify(tool.input_schema, null, 2)}
                            </pre>
                          )}
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}
