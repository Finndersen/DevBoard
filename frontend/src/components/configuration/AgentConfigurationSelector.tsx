import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDownIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import type {
  AgentConfigurationResponse,
  AgentEngineInfo,
  ModelInfo,
  AvailableModelsByEngineResponse,
  UpdateAgentConfigurationRequest
} from '../../lib/api'
import { apiClient } from '../../lib/api'

interface AgentConfigurationSelectorProps {
  agentRole: string
  agentName: string
  onConfigChange?: (agentRole: string, engine: string, modelId: string | null) => void
}

export function AgentConfigurationSelector({ agentRole, agentName, onConfigChange }: AgentConfigurationSelectorProps) {
  const [configuration, setConfiguration] = useState<AgentConfigurationResponse | null>(null)
  const [availableModels, setAvailableModels] = useState<AvailableModelsByEngineResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [isEngineOpen, setIsEngineOpen] = useState(false)
  const [isModelOpen, setIsModelOpen] = useState(false)
  const [selectedEngine, setSelectedEngine] = useState<string | null>(null)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

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

    // Find the engine info to check if it requires model selection
    const engineInfo = configuration.available_engines.find(e => e.engine === engine)
    if (!engineInfo) {
      setError(`Engine ${engine} not found`)
      return
    }

    // If engine doesn't require model selection, use null (default)
    if (!engineInfo.requires_model_selection) {
      await handleConfigChange(engine, null)
      return
    }

    // Otherwise, get the first model for the selected engine as default
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

      // Update local state
      setSelectedEngine(response.config.engine)
      setSelectedModel(response.config.model_id)
      setConfiguration(response)

      if (onConfigChange) {
        onConfigChange(agentRole, response.config.engine, response.config.model_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update agent configuration')
    } finally {
      setSaving(false)
      setIsEngineOpen(false)
      setIsModelOpen(false)
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
      <div className="flex items-center space-x-2">
        <ArrowPathIcon className="w-4 h-4 animate-spin text-gray-400" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Loading...</span>
      </div>
    )
  }

  if (error || !configuration || !availableModels) {
    return (
      <div className="text-sm text-red-600 dark:text-red-400">
        {error || 'Failed to load agent configuration'}
      </div>
    )
  }

  const selectedEngineInfo = getSelectedEngineInfo()
  const selectedModelInfo = getSelectedModelInfo()
  const availableModelsForEngine = getAvailableModelsForSelectedEngine()

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">
            {agentName}
          </h4>
        </div>

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
              className={`relative w-44 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-white ${
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
                {configuration.available_engines.map((engine) => (
                  <button
                    key={engine.engine}
                    type="button"
                    onClick={() => handleEngineChange(engine.engine)}
                    className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 ${
                      selectedEngine === engine.engine
                        ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                        : 'text-gray-900 dark:text-gray-100'
                    }`}
                  >
                    <div>
                      <div className="font-medium">{getEngineDisplayName(engine)}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {engine.description}
                      </div>
                    </div>
                  </button>
                ))}
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
              className={`relative w-60 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-white ${
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
                {/* Show "Default" option for engines that don't require model selection */}
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
    </div>
  )
}
