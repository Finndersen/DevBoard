import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronDownIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import type { AvailableModelsForAgentResponse, ModelInfo, UpdateAgentModelRequest } from '../../lib/api'
import { apiClient } from '../../lib/api'

interface AgentModelSelectorProps {
  agentType: string
  agentName: string
  onModelChange?: (agentType: string, modelId: string | null) => void
}

export function AgentModelSelector({ agentType, agentName, onModelChange }: AgentModelSelectorProps) {
  const [data, setData] = useState<AvailableModelsForAgentResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)

  const dropdownRef = useRef<HTMLDivElement>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await apiClient.getAvailableModelsForAgent(agentType)
      setData(response)
      setSelectedModel(response.preferred_model)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agent models')
    } finally {
      setLoading(false)
    }
  }, [agentType])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [isOpen])

  const handleModelChange = async (modelId: string | null) => {
    if (saving) return

    try {
      setSaving(true)
      const request: UpdateAgentModelRequest = { model_id: modelId }
      const response = await apiClient.updateAgentModel(agentType, request)
      
      // Update local state directly - no need to refetch data
      setSelectedModel(response.model_id)
      if (data) {
        setData({
          ...data,
          preferred_model: response.model_id
        })
      }
      
      if (onModelChange) {
        onModelChange(agentType, response.model_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update agent model')
    } finally {
      setSaving(false)
      setIsOpen(false)
    }
  }

  const getModelDisplayName = (model: ModelInfo): string => {
    return `${model.provider}/${model.name}`
  }

  const getSelectedModelInfo = (): ModelInfo | null => {
    if (!data || !selectedModel) return null
    return data.available_models.find(m => m.id === selectedModel) || null
  }

  if (loading) {
    return (
      <div className="flex items-center space-x-2">
        <ArrowPathIcon className="w-4 h-4 animate-spin text-gray-400" />
        <span className="text-sm text-gray-500 dark:text-gray-400">Loading...</span>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-sm text-red-600 dark:text-red-400">
        {error || 'Failed to load agent models'}
      </div>
    )
  }

  const selectedModelInfo = getSelectedModelInfo()
  
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">
            {agentName}
          </h4>
        </div>
        
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            disabled={saving}
            className={`relative w-60 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm text-gray-900 dark:text-white ${
              saving ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <span className="block truncate">
              {selectedModelInfo ? getModelDisplayName(selectedModelInfo) : 'Auto (Default)'}
            </span>
            <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
              {saving ? (
                <ArrowPathIcon className="w-4 h-4 animate-spin text-gray-400" />
              ) : (
                <ChevronDownIcon className="w-4 h-4 text-gray-400" />
              )}
            </span>
          </button>

          {isOpen && (
            <div className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-700 shadow-lg max-h-60 rounded-md py-1 text-sm ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none">
              {/* Auto/Default option */}
              <button
                type="button"
                onClick={() => handleModelChange(null)}
                className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 ${
                  !selectedModelInfo 
                    ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' 
                    : 'text-gray-900 dark:text-gray-100'
                }`}
              >
                <div>
                  <div className="font-medium">Auto (Default)</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {data.preferred_model ? `Uses ${data.preferred_model}` : 'Uses system fallback'}
                  </div>
                </div>
              </button>

              <div className="border-t border-gray-200 dark:border-gray-600 my-1"></div>

              {/* Available models */}
              {data.available_models.map((model) => (
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
                      {model.provider} provider
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

    </div>
  )
}