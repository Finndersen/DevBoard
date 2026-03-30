import { useState, useEffect } from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import type { ConversationResponse, ModelInfo, UpdateConversationModelRequest, AgentConfigurationResponse } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { surfaces, borderColors, statusColors } from '../../styles/designSystem'

interface ConversationModelSelectorProps {
  conversationId: number
  onModelChange?: (engine: string, modelId: string | null, modelName: string) => void
}

export default function ConversationModelSelector({
  conversationId,
  onModelChange
}: ConversationModelSelectorProps) {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [engineConfig, setEngineConfig] = useState<AgentConfigurationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch conversation details
        const conversationData = await apiClient.getConversation(conversationId)
        setConversation(conversationData)

        // Fetch agent configuration to get engine info
        const configData = await apiClient.getAgentConfiguration(conversationData.agent_role)
        setEngineConfig(configData)

        // Fetch available models for this engine
        const modelsData = await apiClient.getAvailableModelsByEngine()
        const engineModels = modelsData.models_by_engine[conversationData.engine] || []
        setAvailableModels(engineModels)
      } catch (err) {
        console.error('Failed to fetch conversation or models:', err)
        setError(err instanceof Error ? err.message : 'Failed to load conversation data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [conversationId])

  const handleModelChange = async (newModelId: string | null) => {
    if (!conversation || newModelId === conversation.model_id) return

    try {
      setUpdating(true)
      setError(null)

      const request: UpdateConversationModelRequest = { model_id: newModelId }
      await apiClient.updateConversationModel(conversationId, request)

      // Find the new model name
      let newModelName: string
      if (newModelId === null) {
        newModelName = 'Default'
      } else {
        const newModel = availableModels.find(m => m.id === newModelId)
        newModelName = newModel?.name || newModelId.split(':')[1] || newModelId
      }

      // Update local state
      setConversation({
        ...conversation,
        model_id: newModelId
      })

      // Close dropdown
      setIsOpen(false)

      // Notify parent
      if (onModelChange) {
        onModelChange(conversation.engine, newModelId, newModelName)
      }
    } catch (err) {
      console.error('Failed to update conversation model:', err)
      setError(err instanceof Error ? err.message : 'Failed to update model')
    } finally {
      setUpdating(false)
    }
  }

  // Check if current engine requires model selection
  const engineRequiresModelSelection = (): boolean => {
    if (!engineConfig || !conversation) return true
    const engineInfo = engineConfig.available_engines.find(e => e.engine === conversation.engine)
    return engineInfo?.requires_model_selection ?? true
  }

  if (loading) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400">
        Loading...
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-sm text-red-600 dark:text-red-400">
        {error}
      </div>
    )
  }

  if (!conversation) {
    return null
  }

  // Format engine name for display
  const engineDisplayName = conversation.engine
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  // Extract model name from model_id (format: "provider:name")
  const modelDisplayName = conversation.model_id === null
    ? 'Default'
    : (conversation.model_id.split(':')[1] || conversation.model_id)

  return (
    <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
      {/* Engine display (non-interactive) */}
      <span className="font-medium">{engineDisplayName}</span>
      <span className="text-gray-400 dark:text-gray-500">/</span>

      {/* Model selector dropdown */}
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={updating || (availableModels.length === 0 && engineRequiresModelSelection())}
          className="flex items-center space-x-1 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span>{modelDisplayName}</span>
          {(availableModels.length > 1 || !engineRequiresModelSelection()) && (
            <ChevronDownIcon className="w-4 h-4" />
          )}
        </button>

        {/* Dropdown menu */}
        {isOpen && (availableModels.length > 0 || !engineRequiresModelSelection()) && (
          <>
            {/* Backdrop to close dropdown */}
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />

            {/* Dropdown options */}
            <div className={`absolute right-0 mt-2 w-64 ${surfaces.raised} rounded-md shadow-lg border ${borderColors.default} z-20 max-h-64 overflow-y-auto`}>
              {/* Show "Default" option for engines that don't require model selection */}
              {!engineRequiresModelSelection() && (
                <button
                  key="default"
                  onClick={() => handleModelChange(null)}
                  disabled={updating}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 ${
                    conversation.model_id === null
                      ? `${statusColors.info.bg} ${statusColors.info.text} font-medium`
                      : 'text-gray-900 dark:text-gray-100'
                  }`}
                >
                  <div className="flex flex-col">
                    <span>Default</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Use engine's default model
                    </span>
                  </div>
                </button>
              )}
              {availableModels.map((model) => (
                <button
                  key={model.id}
                  onClick={() => handleModelChange(model.id)}
                  disabled={updating}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 ${
                    model.id === conversation.model_id
                      ? `${statusColors.info.bg} ${statusColors.info.text} font-medium`
                      : 'text-gray-900 dark:text-gray-100'
                  }`}
                >
                  <div className="flex flex-col">
                    <span>{model.name}</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {model.provider} • {model.model_type}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
