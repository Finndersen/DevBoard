import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import type { ConversationResponse, ModelInfo, UpdateConversationModelRequest, AgentConfigurationResponse } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { surfaces, borderColors, textColors, hoverColors } from '../../styles/designSystem'
import { useNotificationStore } from '../../stores/notificationStore'
import { reportMutationError } from '../../lib/errors'

interface ConversationModelSelectorProps {
  conversationId: number
  onModelChange?: (engine: string, modelId: string | null, modelName: string) => void
  dropUp?: boolean
}

interface DropdownPosition {
  top: number
  left: number
  width: number
  openUpward: boolean
}

export default function ConversationModelSelector({
  conversationId,
  onModelChange,
  dropUp = false
}: ConversationModelSelectorProps) {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [engineConfig, setEngineConfig] = useState<AgentConfigurationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [dropdownPos, setDropdownPos] = useState<DropdownPosition | null>(null)
  const [error, setError] = useState<string | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const addNotification = useNotificationStore(s => s.addNotification)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        const conversationData = await apiClient.getConversation(conversationId)
        setConversation(conversationData)

        const configData = await apiClient.getAgentConfiguration(conversationData.agent_role)
        setEngineConfig(configData)

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

  const computePosition = useCallback(() => {
    if (!triggerRef.current) return null
    const rect = triggerRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const openUpward = dropUp || spaceBelow < 200
    return {
      top: openUpward ? rect.top : rect.bottom,
      left: rect.right,
      width: rect.width,
      openUpward,
    }
  }, [dropUp])

  const handleToggle = useCallback(() => {
    if (!isOpen) {
      setDropdownPos(computePosition())
    }
    setIsOpen(prev => !prev)
  }, [isOpen, computePosition])

  useEffect(() => {
    if (!isOpen) return
    const update = () => setDropdownPos(computePosition())
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [isOpen, computePosition])

  const handleModelChange = async (newModelId: string | null) => {
    if (!conversation || newModelId === conversation.model_id) return

    try {
      setUpdating(true)
      setError(null)

      const request: UpdateConversationModelRequest = { model_id: newModelId }
      await apiClient.updateConversationModel(conversationId, request)

      let newModelName: string
      if (newModelId === null) {
        newModelName = 'Default'
      } else {
        const newModel = availableModels.find(m => m.id === newModelId)
        newModelName = newModel?.name || newModelId.split(':')[1] || newModelId
      }

      setConversation({ ...conversation, model_id: newModelId })
      setIsOpen(false)

      if (onModelChange) {
        onModelChange(conversation.engine, newModelId, newModelName)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update model')
      reportMutationError(addNotification, err, {
        entityType: null,
        entityId: null,
        entityTitle: null,
        fallbackMessage: 'Failed to update conversation model',
      })
    } finally {
      setUpdating(false)
    }
  }

  const engineRequiresModelSelection = (): boolean => {
    if (!engineConfig || !conversation) return true
    const engineInfo = engineConfig.available_engines.find(e => e.engine === conversation.engine)
    return engineInfo?.requires_model_selection ?? true
  }

  if (loading) {
    return <div className={`text-sm ${textColors.muted}`}>Loading...</div>
  }

  if (error) {
    return <div className="text-sm text-red-600 dark:text-red-400">{error}</div>
  }

  if (!conversation) {
    return null
  }

  const modelDisplayName = conversation.model_id === null
    ? 'Default'
    : (availableModels.find(m => m.id === conversation.model_id)?.name || conversation.model_id.split(':')[1] || conversation.model_id)

  const showDropdown = isOpen && dropdownPos && (availableModels.length > 0 || !engineRequiresModelSelection())

  const itemBase = `w-full text-left px-4 py-2 text-sm ${hoverColors.default} disabled:opacity-50 transition-colors`
  const itemSelected = `${textColors.accent} font-medium`
  const itemDefault = textColors.primary

  return (
    <div className={`flex items-center space-x-2 text-sm ${textColors.secondary}`}>
      <div className="relative">
        <button
          ref={triggerRef}
          onClick={handleToggle}
          disabled={updating || (availableModels.length === 0 && engineRequiresModelSelection())}
          className={`flex items-center space-x-1 hover:${textColors.primary} disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
        >
          <span>{modelDisplayName}</span>
          {(availableModels.length > 1 || !engineRequiresModelSelection()) && (
            <ChevronDownIcon className="w-4 h-4" />
          )}
        </button>

        {showDropdown && createPortal(
          <>
            <div className="fixed inset-0 z-50" onClick={() => setIsOpen(false)} />
            <div
              className={`fixed z-50 w-56 ${surfaces.raised} rounded-md shadow-lg border ${borderColors.default} max-h-64 overflow-y-auto`}
              style={dropdownPos.openUpward
                ? { bottom: window.innerHeight - dropdownPos.top + 8, right: window.innerWidth - dropdownPos.left }
                : { top: dropdownPos.top + 8, right: window.innerWidth - dropdownPos.left }
              }
            >
              {!engineRequiresModelSelection() && (
                <button
                  onClick={() => handleModelChange(null)}
                  disabled={updating}
                  className={`${itemBase} ${conversation.model_id === null ? itemSelected : itemDefault}`}
                >
                  <div className="flex flex-col">
                    <span>Default</span>
                    <span className={`text-xs ${textColors.muted}`}>Use engine's default model</span>
                  </div>
                </button>
              )}
              {availableModels.map((model) => (
                <button
                  key={model.id}
                  onClick={() => handleModelChange(model.id)}
                  disabled={updating}
                  className={`${itemBase} ${model.id === conversation.model_id ? itemSelected : itemDefault}`}
                >
                  <div className="flex flex-col">
                    <span>{model.name}</span>
                    <span className={`text-xs ${textColors.muted}`}>{model.provider} • {model.model_type}</span>
                  </div>
                </button>
              ))}
            </div>
          </>,
          document.body
        )}
      </div>
    </div>
  )
}
