import { useState, useEffect, useRef, useCallback } from 'react'
import {
  ChevronDownIcon,
  ArrowPathIcon,
  PlusIcon,
  XMarkIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'
import type {
  AgentEngineInfo,
  ModelInfo,
  AvailableModelsByEngineResponse,
  MCPToolSummary,
  AgentEngine,
  BackgroundAgentCreate,
  BackgroundAgentUpdate,
} from '../lib/api'
import { apiClient } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import {
  useBackgroundAgent,
  useCreateBackgroundAgent,
  useUpdateBackgroundAgent,
} from '../hooks/useBackgroundAgents'
import { MCPToolSelectorModal } from '../components/configuration/MCPToolSelectorModal'
import { textColors, borderColors, surfaces, statusColors } from '../styles/designSystem'
import { standardInputClasses, standardTextareaClasses } from '../styles/inputStyles'
import { Button } from '../components/ui'

interface Props {
  id: string
}

interface ScheduleTrigger {
  cron_expression: string
}

interface EventTrigger {
  event_type_pattern: string
}

const DEFAULT_ENGINE: AgentEngine = 'internal'

function isValidCronField(field: string, min: number, max: number): boolean {
  if (field === '*') return true
  if (/^\*\/\d+$/.test(field)) return true // step: */5
  const num = Number(field)
  return Number.isInteger(num) && num >= min && num <= max
}

function isValidCron(expr: string): boolean {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return false
  const [minute, hour, dom, month, dow] = parts
  return (
    isValidCronField(minute, 0, 59) &&
    isValidCronField(hour, 0, 23) &&
    isValidCronField(dom, 1, 31) &&
    isValidCronField(month, 1, 12) &&
    isValidCronField(dow, 0, 7)
  )
}

export default function BackgroundAgentEditor({ id }: Props) {
  const isNew = id === 'new'
  const { navigateTo } = useUIStore()

  const { data: existingAgent, loading: agentLoading } = useBackgroundAgent(isNew ? null : id)
  const { mutate: createAgent, loading: creating, error: createError } = useCreateBackgroundAgent()
  const { mutate: updateAgent, loading: updating, error: updateError } = useUpdateBackgroundAgent()

  // Static reference data
  const [availableEngines, setAvailableEngines] = useState<AgentEngineInfo[]>([])
  const [availableModels, setAvailableModels] = useState<AvailableModelsByEngineResponse | null>(null)
  const [allTools, setAllTools] = useState<MCPToolSummary[]>([])
  const [dataLoading, setDataLoading] = useState(true)
  const [dataError, setDataError] = useState<string | null>(null)
  const [formPopulated, setFormPopulated] = useState(false)

  // Form fields
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [selectedEngine, setSelectedEngine] = useState<AgentEngine>(DEFAULT_ENGINE)
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [scheduleTriggers, setScheduleTriggers] = useState<ScheduleTrigger[]>([])
  const [eventTriggers, setEventTriggers] = useState<EventTrigger[]>([])
  const [assignedTools, setAssignedTools] = useState<MCPToolSummary[]>([])
  const [initialState, setInitialState] = useState('{}')
  const [stateError, setStateError] = useState<string | null>(null)

  // UI state
  const [isEngineOpen, setIsEngineOpen] = useState(false)
  const [isModelOpen, setIsModelOpen] = useState(false)
  const [isToolSelectorOpen, setIsToolSelectorOpen] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const engineDropdownRef = useRef<HTMLDivElement>(null)
  const modelDropdownRef = useRef<HTMLDivElement>(null)

  // Load engines, models, and available tools
  const loadStaticData = useCallback(async () => {
    try {
      setDataLoading(true)
      setDataError(null)
      const [configResponse, modelsResponse, toolsResponse] = await Promise.all([
        apiClient.getAgentConfiguration('project'),
        apiClient.getAvailableModelsByEngine(),
        apiClient.getAvailableMCPTools(),
      ])
      setAvailableEngines(configResponse.available_engines)
      setAvailableModels(modelsResponse)
      setAllTools(toolsResponse)
    } catch (err) {
      setDataError(err instanceof Error ? err.message : 'Failed to load configuration data')
    } finally {
      setDataLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStaticData()
  }, [loadStaticData])

  // Populate form when editing an existing agent (after static data has loaded)
  useEffect(() => {
    if (!formPopulated && !isNew && existingAgent && !dataLoading && allTools !== null) {
      setName(existingAgent.name)
      setDescription(existingAgent.description ?? '')
      setPrompt(existingAgent.prompt)
      setSelectedEngine(existingAgent.engine)
      setSelectedModel(existingAgent.model_id)
      setScheduleTriggers(
        existingAgent.schedule_triggers.map((t) => ({ cron_expression: t.cron_expression })),
      )
      setEventTriggers(
        existingAgent.event_triggers.map((t) => ({ event_type_pattern: t.event_type_pattern })),
      )
      setInitialState(JSON.stringify(existingAgent.state, null, 2))
      // Resolve tool IDs to MCPToolSummary objects using the loaded tool list
      const resolved = existingAgent.mcp_tool_ids
        .map((toolId) => allTools.find((t) => t.tool_id === toolId))
        .filter((t): t is MCPToolSummary => t !== undefined)
      setAssignedTools(resolved)
      setFormPopulated(true)
    }
  }, [formPopulated, isNew, existingAgent, dataLoading, allTools])

  // Close dropdowns on outside click
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
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isEngineOpen, isModelOpen])

  // --- Engine / Model helpers ---

  const getSelectedEngineInfo = (): AgentEngineInfo | null =>
    availableEngines.find((e) => e.engine === selectedEngine) ?? null

  const getAvailableModelsForEngine = (engine: string = selectedEngine): ModelInfo[] =>
    availableModels?.models_by_engine[engine] ?? []

  const selectedEngineRequiresModelSelection = (): boolean =>
    getSelectedEngineInfo()?.requires_model_selection ?? true

  const getModelDisplayText = (): string => {
    if (selectedModel === null) return 'Default'
    const model = getAvailableModelsForEngine().find((m) => m.id === selectedModel)
    return model ? model.name : selectedModel
  }

  const handleEngineChange = (engine: AgentEngine) => {
    const engineInfo = availableEngines.find((e) => e.engine === engine)
    if (!engineInfo?.is_available) return
    setSelectedEngine(engine)
    setIsEngineOpen(false)
    if (!engineInfo.requires_model_selection) {
      setSelectedModel(null)
    } else {
      const models = getAvailableModelsForEngine(engine)
      setSelectedModel(models[0]?.id ?? null)
    }
  }

  // --- Trigger helpers ---

  const addScheduleTrigger = () =>
    setScheduleTriggers((prev) => [...prev, { cron_expression: '' }])

  const updateScheduleTrigger = (index: number, value: string) =>
    setScheduleTriggers((prev) => prev.map((t, i) => (i === index ? { cron_expression: value } : t)))

  const removeScheduleTrigger = (index: number) =>
    setScheduleTriggers((prev) => prev.filter((_, i) => i !== index))

  const addEventTrigger = () =>
    setEventTriggers((prev) => [...prev, { event_type_pattern: '' }])

  const updateEventTrigger = (index: number, value: string) =>
    setEventTriggers((prev) =>
      prev.map((t, i) => (i === index ? { event_type_pattern: value } : t)),
    )

  const removeEventTrigger = (index: number) =>
    setEventTriggers((prev) => prev.filter((_, i) => i !== index))

  // --- MCP tools ---

  const handleAddTools = async (toolIds: number[]) => {
    const newTools = toolIds
      .map((tid) => allTools.find((t) => t.tool_id === tid))
      .filter((t): t is MCPToolSummary => t !== undefined)
    setAssignedTools((prev) => [...prev, ...newTools])
  }

  const handleRemoveTool = (toolId: number) =>
    setAssignedTools((prev) => prev.filter((t) => t.tool_id !== toolId))

  // --- State JSON ---

  const handleStateBlur = () => {
    if (!initialState.trim()) {
      setStateError(null)
      return
    }
    try {
      JSON.parse(initialState)
      setStateError(null)
    } catch {
      setStateError('Invalid JSON')
    }
  }

  // --- Save / Cancel ---

  const validate = (): boolean => {
    const errors: Record<string, string> = {}
    if (!name.trim()) errors.name = 'Name is required'
    if (!prompt.trim()) errors.prompt = 'Prompt is required'
    for (let i = 0; i < scheduleTriggers.length; i++) {
      const expr = scheduleTriggers[i].cron_expression.trim()
      if (expr && !isValidCron(expr)) {
        errors[`cron_${i}`] = 'Invalid cron expression (expected 5 fields)'
      }
    }
    if (initialState.trim()) {
      try {
        JSON.parse(initialState)
      } catch {
        errors.initialState = 'Invalid JSON'
      }
    }
    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSave = async () => {
    if (!validate()) return

    let parsedState: Record<string, unknown> = {}
    try {
      parsedState = initialState.trim() ? JSON.parse(initialState) : {}
    } catch {
      return
    }

    const validScheduleTriggers = scheduleTriggers
      .filter((t) => t.cron_expression.trim())
      .map((t) => ({ cron_expression: t.cron_expression.trim() }))

    const validEventTriggers = eventTriggers
      .filter((t) => t.event_type_pattern.trim())
      .map((t) => ({ event_type_pattern: t.event_type_pattern.trim() }))

    try {
      let saved
      if (isNew) {
        const payload: BackgroundAgentCreate = {
          name: name.trim(),
          description: description.trim() || null,
          prompt: prompt.trim(),
          engine: selectedEngine,
          model_id: selectedModel,
          mcp_tool_ids: assignedTools.map((t) => t.tool_id),
          schedule_triggers: validScheduleTriggers,
          event_triggers: validEventTriggers,
        }
        saved = await createAgent(payload)
        // Set initial state if non-empty
        if (Object.keys(parsedState).length > 0) {
          await apiClient.updateBackgroundAgentState(saved.id, parsedState)
        }
      } else {
        const payload: BackgroundAgentUpdate = {
          name: name.trim(),
          description: description.trim() || null,
          prompt: prompt.trim(),
          engine: selectedEngine,
          model_id: selectedModel,
          mcp_tool_ids: assignedTools.map((t) => t.tool_id),
          schedule_triggers: validScheduleTriggers,
          event_triggers: validEventTriggers,
        }
        saved = await updateAgent(id, payload)
        await apiClient.updateBackgroundAgentState(saved.id, parsedState)
      }
      navigateTo({
        type: 'background-agent-detail',
        entityId: String(saved.id),
        title: saved.name,
      })
    } catch {
      // Errors are captured by mutation hook state
    }
  }

  const handleCancel = () => {
    if (isNew) {
      navigateTo({ type: 'background-agents-list', entityId: 'list', title: 'Agents' })
    } else {
      navigateTo({
        type: 'background-agent-detail',
        entityId: id,
        title: existingAgent?.name ?? 'Agent',
      })
    }
  }

  const isLoading = dataLoading || (!isNew && agentLoading)
  const isSaving = creating || updating
  const saveError = createError ?? updateError

  // --- Shared input classes ---
  const inputClasses = `${standardInputClasses} text-sm placeholder-gray-400 dark:placeholder-gray-500`
  const textareaInputClasses = `${standardTextareaClasses} text-sm placeholder-gray-400 dark:placeholder-gray-500`
  const dropdownButtonClasses = `relative w-full bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded-md pl-3 pr-10 py-2 text-left cursor-pointer focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm ${textColors.primary}`
  const dropdownMenuClasses = `absolute z-10 mt-1 w-full bg-white dark:bg-gray-800 shadow-lg max-h-60 rounded-md py-1 text-sm ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none`

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <ArrowPathIcon className="w-6 h-6 animate-spin text-gray-400" />
        <span className={`ml-2 text-sm ${textColors.secondary}`}>Loading...</span>
      </div>
    )
  }

  if (dataError) {
    return (
      <div className="p-6 text-center">
        <div className={`text-sm ${statusColors.error.text}`}>{dataError}</div>
        <button
          onClick={loadStaticData}
          className="mt-4 px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-500"
        >
          Retry
        </button>
      </div>
    )
  }

  const selectedEngineInfo = getSelectedEngineInfo()
  const availableModelsForEngine = getAvailableModelsForEngine()
  const agentTitle = isNew ? 'Create Agent' : `Edit ${existingAgent?.name ?? 'Agent'}`

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div
        className={`flex items-center justify-between px-6 py-4 border-b ${borderColors.default} flex-shrink-0`}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={handleCancel}
            className={`text-sm ${textColors.secondary} hover:${textColors.primary} transition-colors`}
          >
            ← Agents
          </button>
          <span className={`text-gray-300 dark:text-gray-600`}>/</span>
          <h1 className={`text-lg font-semibold ${textColors.primary}`}>{agentTitle}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCancel} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave} loading={isSaving}>
            {isNew ? 'Create Agent' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl px-6 py-6 space-y-6">
          {saveError && (
            <div
              className={`px-4 py-3 rounded-md ${statusColors.error.bg} ${statusColors.error.text} text-sm border ${statusColors.error.border}`}
            >
              {saveError}
            </div>
          )}

          {/* Basic Info */}
          <div className="space-y-4">
            <div>
              <label className={`block text-sm font-medium ${textColors.primary} mb-1`}>
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Daily Standup Summariser"
                className={inputClasses}
                aria-invalid={!!validationErrors.name}
              />
              {validationErrors.name && (
                <p className={`mt-1 text-xs ${statusColors.error.text}`}>{validationErrors.name}</p>
              )}
            </div>

            <div>
              <label className={`block text-sm font-medium ${textColors.primary} mb-1`}>
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this agent do?"
                rows={2}
                className={textareaInputClasses}
              />
            </div>

            <div>
              <label className={`block text-sm font-medium ${textColors.primary} mb-1`}>
                Prompt <span className="text-red-500">*</span>
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Define the agent's behaviour..."
                rows={8}
                className={`${textareaInputClasses} font-mono leading-relaxed`}
                aria-invalid={!!validationErrors.prompt}
              />
              {validationErrors.prompt ? (
                <p className={`mt-1 text-xs ${statusColors.error.text}`}>{validationErrors.prompt}</p>
              ) : (
                <p className={`mt-1 text-xs ${textColors.muted}`}>
                  The system prompt that defines this agent&apos;s behaviour. Supports markdown.
                </p>
              )}
            </div>
          </div>

          <hr className={`border-t ${borderColors.default}`} />

          {/* Engine & Model */}
          <div className="space-y-3">
            <h3 className={`text-sm font-semibold ${textColors.primary}`}>Engine &amp; Model</h3>
            <div className="grid grid-cols-2 gap-4">
              {/* Engine Dropdown */}
              <div>
                <label className={`block text-xs font-medium ${textColors.secondary} mb-1`}>
                  Engine <span className="text-red-500">*</span>
                </label>
                <div className="relative" ref={engineDropdownRef}>
                  <button
                    type="button"
                    onClick={() => setIsEngineOpen((v) => !v)}
                    className={dropdownButtonClasses}
                  >
                    <span className="block truncate">
                      {selectedEngineInfo?.display_name ?? selectedEngine}
                    </span>
                    <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                      <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                    </span>
                  </button>
                  {isEngineOpen && (
                    <div className={dropdownMenuClasses}>
                      {availableEngines.map((engine) => {
                        const isUnavailable = !engine.is_available
                        return (
                          <button
                            key={engine.engine}
                            type="button"
                            onClick={() => handleEngineChange(engine.engine as AgentEngine)}
                            disabled={isUnavailable}
                            className={`w-full text-left px-3 py-2 ${isUnavailable ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer'} ${selectedEngine === engine.engine && !isUnavailable ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : `${textColors.primary}`}`}
                          >
                            <div className="font-medium">
                              {engine.display_name}
                              {isUnavailable && (
                                <span className={`ml-2 text-xs ${textColors.muted}`}>
                                  (Unavailable)
                                </span>
                              )}
                            </div>
                            <div className={`text-xs ${textColors.muted}`}>
                              {isUnavailable && engine.unavailable_reason
                                ? engine.unavailable_reason
                                : engine.description}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Model Dropdown */}
              <div>
                <label className={`block text-xs font-medium ${textColors.secondary} mb-1`}>
                  Model
                </label>
                <div className="relative" ref={modelDropdownRef}>
                  <button
                    type="button"
                    onClick={() => setIsModelOpen((v) => !v)}
                    className={dropdownButtonClasses}
                  >
                    <span className="block truncate">{getModelDisplayText()}</span>
                    <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                      <ChevronDownIcon className="w-4 h-4 text-gray-400" />
                    </span>
                  </button>
                  {isModelOpen && (
                    <div className={dropdownMenuClasses}>
                      {!selectedEngineRequiresModelSelection() && (
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedModel(null)
                            setIsModelOpen(false)
                          }}
                          className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 ${selectedModel === null ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : textColors.primary}`}
                        >
                          <div className="font-medium">Default</div>
                          <div className={`text-xs ${textColors.muted}`}>
                            Use engine&apos;s default model
                          </div>
                        </button>
                      )}
                      {availableModelsForEngine.map((model) => (
                        <button
                          key={model.id}
                          type="button"
                          onClick={() => {
                            setSelectedModel(model.id)
                            setIsModelOpen(false)
                          }}
                          className={`w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 ${selectedModel === model.id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : textColors.primary}`}
                        >
                          <div className="font-medium">{model.name}</div>
                          <div className={`text-xs ${textColors.muted} capitalize`}>
                            {model.model_type}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className={`mt-1 text-xs ${textColors.muted}`}>
                  Leave as Default to use engine default
                </p>
              </div>
            </div>
          </div>

          <hr className={`border-t ${borderColors.default}`} />

          {/* Schedule Triggers */}
          <div className="space-y-3">
            <h3 className={`text-sm font-semibold ${textColors.primary}`}>⏰ Schedule Triggers</h3>
            <div className={`${surfaces.raised} border ${borderColors.default} rounded-lg p-4 space-y-3`}>
              {scheduleTriggers.length === 0 && (
                <p className={`text-xs ${textColors.muted}`}>No schedule triggers configured.</p>
              )}
              {scheduleTriggers.map((trigger, index) => (
                <div key={index} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={trigger.cron_expression}
                      onChange={(e) => updateScheduleTrigger(index, e.target.value)}
                      placeholder="e.g. 0 9 * * *"
                      className={`${inputClasses} font-mono`}
                      aria-label={`Schedule trigger ${index + 1}`}
                      aria-invalid={!!validationErrors[`cron_${index}`]}
                    />
                    <button
                      type="button"
                      onClick={() => removeScheduleTrigger(index)}
                      className={`flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded`}
                      aria-label="Remove schedule trigger"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                  {validationErrors[`cron_${index}`] && (
                    <p className={`text-xs ${statusColors.error.text}`}>
                      {validationErrors[`cron_${index}`]}
                    </p>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addScheduleTrigger}
                className={`flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline`}
              >
                <PlusIcon className="w-3.5 h-3.5" />
                Add schedule
              </button>
            </div>
          </div>

          {/* Event Triggers */}
          <div className="space-y-3">
            <h3 className={`text-sm font-semibold ${textColors.primary}`}>⚡ Event Triggers</h3>
            <div className={`${surfaces.raised} border ${borderColors.default} rounded-lg p-4 space-y-3`}>
              {eventTriggers.length === 0 && (
                <p className={`text-xs ${textColors.muted}`}>No event triggers configured.</p>
              )}
              {eventTriggers.map((trigger, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={trigger.event_type_pattern}
                    onChange={(e) => updateEventTrigger(index, e.target.value)}
                    placeholder="e.g. task.completed, github.pr.*"
                    className={inputClasses}
                    aria-label={`Event trigger ${index + 1}`}
                  />
                  <button
                    type="button"
                    onClick={() => removeEventTrigger(index)}
                    className="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded"
                    aria-label="Remove event trigger"
                  >
                    <XMarkIcon className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={addEventTrigger}
                  className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  <PlusIcon className="w-3.5 h-3.5" />
                  Add event trigger
                </button>
                <p className={`text-xs ${textColors.muted}`}>
                  Event type patterns to match. Use * as a wildcard (e.g. task.*, github.pr.*).
                </p>
              </div>
            </div>
          </div>

          <hr className={`border-t ${borderColors.default}`} />

          {/* MCP Tools */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className={`text-sm font-semibold ${textColors.primary}`}>MCP Tools</h3>
                <p className={`text-xs ${textColors.muted} mt-0.5`}>
                  External tools available to this agent
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsToolSelectorOpen(true)}
                className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 border border-blue-600 dark:border-blue-400 rounded-md flex items-center gap-1.5"
              >
                <PlusIcon className="w-4 h-4" />
                Add Tools
              </button>
            </div>

            {assignedTools.length === 0 ? (
              <div
                className={`border border-dashed ${borderColors.default} rounded-lg p-6 text-center`}
              >
                <WrenchScrewdriverIcon className={`w-8 h-8 mx-auto text-gray-400 dark:text-gray-500`} />
                <p className={`text-sm ${textColors.muted} mt-2`}>No MCP tools configured</p>
                <p className={`text-xs text-gray-400 dark:text-gray-500 mt-1`}>
                  Add tools to extend this agent&apos;s capabilities
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {assignedTools.map((tool) => (
                  <div
                    key={tool.tool_id}
                    className={`flex items-center justify-between p-3 ${surfaces.sunken} border ${borderColors.default} rounded-lg`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-sm font-medium ${textColors.primary} truncate`}>
                        {tool.tool_name}
                      </span>
                      <span
                        className={`text-xs ${textColors.muted} px-2 py-0.5 bg-gray-200 dark:bg-white/[0.06] rounded flex-shrink-0`}
                      >
                        {tool.server_name}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveTool(tool.tool_id)}
                      className="ml-3 p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
                      aria-label={`Remove ${tool.tool_name}`}
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <hr className={`border-t ${borderColors.default}`} />

          {/* Initial State */}
          <div>
            <label className={`block text-sm font-medium ${textColors.primary} mb-1`}>
              Initial State (JSON)
            </label>
            <textarea
              value={initialState}
              onChange={(e) => setInitialState(e.target.value)}
              onBlur={handleStateBlur}
              rows={5}
              className={`${textareaInputClasses} font-mono`}
              placeholder="{}"
              aria-invalid={!!(stateError || validationErrors.initialState)}
            />
            {stateError || validationErrors.initialState ? (
              <p className={`mt-1 text-xs ${statusColors.error.text}`}>
                {stateError ?? validationErrors.initialState}
              </p>
            ) : (
              <p className={`mt-1 text-xs ${textColors.muted}`}>
                Optional persistent state the agent can read/write between runs.
              </p>
            )}
          </div>

          {/* Bottom padding */}
          <div className="h-6" />
        </div>
      </div>

      {/* MCP Tool Selector Modal */}
      <MCPToolSelectorModal
        isOpen={isToolSelectorOpen}
        onClose={() => setIsToolSelectorOpen(false)}
        onAdd={handleAddTools}
        excludeToolIds={assignedTools.map((t) => t.tool_id)}
      />
    </div>
  )
}
