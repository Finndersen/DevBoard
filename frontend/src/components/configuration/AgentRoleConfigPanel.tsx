import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDownIcon, ArrowPathIcon, PlusIcon, XMarkIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline'
import type {
  AgentConfigurationResponse,
  AgentEngineInfo,
  ModelInfo,
  AvailableModelsByEngineResponse,
  UpdateAgentConfigurationRequest,
  MCPToolSummary
} from '../../lib/api'
import { apiClient } from '../../lib/api'
import { MCPToolSelectorModal } from './MCPToolSelectorModal'

interface AgentRoleConfigPanelProps {
  agentRole: string
  agentName: string
  agentDescription: string
}

export function AgentRoleConfigPanel({ agentRole, agentName, agentDescription }: AgentRoleConfigPanelProps) {
  const [configuration, setConfiguration] = useState<AgentConfigurationResponse | null>(null)
  const [availableModels, setAvailableModels] = useState<AvailableModelsByEngineResponse | null>(null)
  const [assignedTools, setAssignedTools] = useState<MCPToolSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [isEngineOpen, setIsEngineOpen] = useState(false)
  const [isModelOpen, setIsModelOpen] = useState(false)
  const [selectedEngine, setSelectedEngine] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [customInstructions, setCustomInstructions] = useState<string>('')
  const [customInstructionsDirty, setCustomInstructionsDirty] = useState(false)
  const [savingInstructions, setSavingInstructions] = useState(false)
  const [isToolSelectorOpen, setIsToolSelectorOpen] = useState(false)
  const [removingToolId, setRemovingToolId] = useState<number | null>(null)

  const engineDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [configResponse, modelsResponse] = await Promise.all([
        apiClient.getAgentConfiguration(agentRole),
        apiClient.getAvailableModelsByEngine()
      ])

      setConfiguration(configResponse)
      setAvailableModels(modelsResponse)
      setSelectedEngine(configResponse.config.engine)
      setSelectedModel(configResponse.config.model_id)
      setCustomInstructions(configResponse.custom_instructions || '')
      setCustomInstructionsDirty(false)
      setAssignedTools(configResponse.enabled_mcp_tools)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent configuration')
    } finally {
      setLoading(false)
    }
  }, [agentRole])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (engineDropdownRef.current && !engineDropdownRef.current.contains(event.target as Node)) {
        setIsEngineOpen(false)
      }
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target as Node)) {
        setIsModelOpen(false)
      }
    }

    if (isEngineOpen || isModelOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [isEngineOpen, isModelOpen])

  const handleEngineChange = async (engine: string) => {
    if (saving || !availableModels || !configuration) return

    const engineInfo = configuration.available_engines.find(e => e.engine === engine)
    if (!engineInfo) {
      setError(`Engine ${engine} not found`)
      return
    }

    if (!engineInfo.is_available) {
      return
    }

    if (!engineInfo.requires_model_selection) {
      await handleConfigChange(engine, null)
      return
    }

    const modelsForEngine = availableModels.models_by_engine[engine]
    if (!modelsForEngine || modelsForEngine.length === 0) {
      setError(`No models available for engine ${engine}`)
      return
    }

    const defaultModel = modelsForEngine[0].id
    await handleConfigChange(engine, defaultModel)
  }

  const handleModelChange = async (modelId: string | null) => {
    if (saving || !selectedEngine) return
    await handleConfigChange(selectedEngine, modelId)
  }

  const handleConfigChange = async (engine: string, modelId: string | null) => {
    try {
      setSaving(true)
      const request: UpdateAgentConfigurationRequest = { engine, model_id: modelId }
      const response = await apiClient.updateAgentConfiguration(agentRole, request)

      setSelectedEngine(response.config.engine)
      setSelectedModel(response.config.model_id)
      setConfiguration(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update agent configuration')
    } finally {
      setSaving(false)
      setIsEngineOpen(false)
      setIsModelOpen(false)
    }
  }

  const handleSaveCustomInstructions = async () => {
    if (!configuration) return

    try {
      setSavingInstructions(true)
      const request: UpdateAgentConfigurationRequest = {
        engine: configuration.config.engine,
        model_id: configuration.config.model_id,
        custom_instructions: customInstructions || null
      }
      const response = await apiClient.updateAgentConfiguration(agentRole, request)
      setConfiguration(response)
      setCustomInstructionsDirty(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save custom instructions')
    } finally {
      setSavingInstructions(false)
    }
  }

  const handleAddTools = async (toolIds: number[]) => {
    try {
      for (const toolId of toolIds) {
        await apiClient.addAgentRoleTool(agentRole, toolId)
      }
      // Refresh configuration to get updated tools list
      const configResponse = await apiClient.getAgentConfiguration(agentRole)
      setConfiguration(configResponse)
      setAssignedTools(configResponse.enabled_mcp_tools)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add tools')
    }
  }

  const handleRemoveTool = async (toolId: number) => {
    try {
      setRemovingToolId(toolId)
      await apiClient.removeAgentRoleTool(agentRole, toolId)
      setAssignedTools(prev => prev.filter(t => t.tool_id !== toolId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove tool')
    } finally {
      setRemovingToolId(null)
    }
  }

  const getEngineDisplayName = (engine: AgentEngineInfo): string => {
    return engine.display_name
  }

  const getModelDisplayName = (model: ModelInfo): string => {
    return model.name
  }

  const getSelectedEngineInfo = (): AgentEngineInfo | null => {
    if (!configuration || !selectedEngine) return null
    return configuration.available_engines.find(e => e.engine === selectedEngine) || null
  }

  const getSelectedModelInfo = (): ModelInfo | null => {
    if (!availableModels || !selectedEngine || !selectedModel) return null
    const modelsForEngine = availableModels.models_by_engine[selectedEngine]
    if (!modelsForEngine) return null
    return modelsForEngine.find(m => m.id === selectedModel) || null
  }

  const getAvailableModelsForSelectedEngine = (): ModelInfo[] => {
    if (!availableModels || !selectedEngine) return []
    return availableModels.models_by_engine[selectedEngine] || []
  }

  const selectedEngineRequiresModelSelection = (): boolean => {
    const engineInfo = getSelectedEngineInfo()
    return engineInfo?.requires_model_selection ?? true
  }

  const getModelDisplayText = (): string => {
    if (selectedModel === null) return 'Default'
    const modelInfo = getSelectedModelInfo()
    return modelInfo ? getModelDisplayName(modelInfo) : selectedModel
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <ArrowPathIcon className="w-6 h-6 animate-spin text-gray-400" />
        <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">Loading configuration...</span>
      </div>
    )
  }

  if (error || !configuration || !availableModels) {
    return (
      <div className="p-6 text-center">
        <div className="text-sm text-red-600 dark:text-red-400">
          {error || 'Failed to load agent configuration'}
        </div>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-500"
        >
          Retry
        </button>
      </div>
    )
  }

  const selectedEngineInfo = getSelectedEngineInfo()
  const availableModelsForEngine = getAvailableModelsForSelectedEngine()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">{agentName}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{agentDescription}</p>
      </div>

      {/* Engine & Model Selection */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white">Engine & Model</h4>

        <div className="flex gap-4">
          {/* Engine Selector */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
              Engine
            </label>
            <div className="relative" ref={engineDropdownRef}>
              <button
                type="button"
                onClick={() => setIsEngineOpen(!isEngineOpen)}
                disabled={saving}
                className={`relative w-48 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-white ${
                  saving ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                <span className="block truncate">
                  {selectedEngineInfo ? getEngineDisplayName(selectedEngineInfo) : selectedEngine}
                </span>
                <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                  {saving ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin text-gray-400" />
                  ) : (
                    <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                  )}
                </span>
              </button>

              {isEngineOpen && (
                <div className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-700 shadow-lg max-h-60 rounded-md py-1 text-sm ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none">
                  {configuration.available_engines.map((engine) => {
                    const isUnavailable = !engine.is_available
                    return (
                      <button
                        key={engine.engine}
                        type="button"
                        onClick={() => handleEngineChange(engine.engine)}
                        disabled={isUnavailable}
                        className={`w-full text-left px-3 py-2 ${
                          isUnavailable
                            ? 'opacity-50 cursor-not-allowed'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-600 cursor-pointer'
                        } ${
                          selectedEngine === engine.engine && !isUnavailable
                            ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                            : 'text-gray-900 dark:text-gray-100'
                        }`}
                      >
                        <div>
                          <div className="font-medium">
                            {getEngineDisplayName(engine)}
                            {isUnavailable && <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">(Unavailable)</span>}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {isUnavailable && engine.unavailable_reason
                              ? engine.unavailable_reason
                              : engine.description}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Model Selector */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
              Model
            </label>
            <div className="relative" ref={modelDropdownRef}>
              <button
                type="button"
                onClick={() => setIsModelOpen(!isModelOpen)}
                disabled={saving}
                className={`relative w-64 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-white ${
                  saving ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                <span className="block truncate">
                  {getModelDisplayText()}
                </span>
                <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                  {saving ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin text-gray-400" />
                  ) : (
                    <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                  )}
                </span>
              </button>

              {isModelOpen && (
                <div className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-700 shadow-lg max-h-60 rounded-md py-1 text-sm ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none">
                  {!selectedEngineRequiresModelSelection() && (
                    <button
                      type="button"
                      onClick={() => handleModelChange(null)}
                      className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 ${
                        selectedModel === null
                          ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                          : 'text-gray-900 dark:text-gray-100'
                      }`}
                    >
                      <div>
                        <div className="font-medium">Default</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          Use engine's default model
                        </div>
                      </div>
                    </button>
                  )}
                  {availableModelsForEngine.map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => handleModelChange(model.id)}
                      className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 ${
                        selectedModel === model.id
                          ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                          : 'text-gray-900 dark:text-gray-100'
                      }`}
                    >
                      <div>
                        <div className="font-medium">{getModelDisplayName(model)}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                          {model.model_type}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Custom Instructions */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white">Custom Instructions</h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Additional instructions appended to the agent's system prompt
            </p>
          </div>
          {customInstructionsDirty && (
            <button
              onClick={handleSaveCustomInstructions}
              disabled={savingInstructions}
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {savingInstructions && <ArrowPathIcon className="w-4 h-4 animate-spin" />}
              Save
            </button>
          )}
        </div>
        <textarea
          value={customInstructions}
          onChange={(e) => {
            setCustomInstructions(e.target.value)
            setCustomInstructionsDirty(true)
          }}
          placeholder="Enter custom instructions for this agent..."
          rows={4}
          className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* Assigned MCP Tools */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium text-gray-900 dark:text-white">Assigned MCP Tools</h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              External tools available to this agent (Internal engine only)
            </p>
          </div>
          <button
            onClick={() => setIsToolSelectorOpen(true)}
            className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 border border-blue-600 dark:border-blue-400 rounded-md flex items-center gap-1.5"
          >
            <PlusIcon className="w-4 h-4" />
            Add Tools
          </button>
        </div>

        {assignedTools.length === 0 ? (
          <div className="border border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
            <WrenchScrewdriverIcon className="w-8 h-8 mx-auto text-gray-400 dark:text-gray-500" />
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              No MCP tools configured
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              Add tools from verified MCP servers to extend agent capabilities
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {assignedTools.map((tool) => (
              <div
                key={tool.tool_id}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {tool.tool_name}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                      {tool.server_name}
                    </span>
                  </div>
                  {tool.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                      {tool.description}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleRemoveTool(tool.tool_id)}
                  disabled={removingToolId === tool.tool_id}
                  className="ml-3 p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400 disabled:opacity-50"
                >
                  {removingToolId === tool.tool_id ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  ) : (
                    <XMarkIcon className="w-4 h-4" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* MCP Tool Selector Modal */}
      <MCPToolSelectorModal
        isOpen={isToolSelectorOpen}
        onClose={() => setIsToolSelectorOpen(false)}
        onAdd={handleAddTools}
        excludeToolIds={assignedTools.map(t => t.tool_id)}
      />
    </div>
  )
}
