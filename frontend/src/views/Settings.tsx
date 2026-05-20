import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { CogIcon, Cog6ToothIcon, LinkIcon, CpuChipIcon, TagIcon, SparklesIcon } from '@heroicons/react/24/outline'
import ViewHeader from '../components/layout/ViewHeader'
import { ConfigurationForm } from '../components/configuration/ConfigurationForm'
import { ConfigurationList } from '../components/configuration/ConfigurationList'
import { AgentRoleList } from '../components/configuration/AgentRoleList'
import { AgentRoleConfigPanel } from '../components/configuration/AgentRoleConfigPanel'
import { CustomFieldSettings } from '../components/settings/CustomFieldSettings'
import { LanguageModelSettings } from '../components/settings/LanguageModelSettings'
import { useDarkMode } from '../contexts/DarkModeContext'
import type { ConfigurationDetailResponse } from '../lib/api'
import { Card } from '../components/ui'
import { textColors, borderColors } from '../styles/designSystem'
import { apiClient } from '../lib/api'

export default function Settings() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isDarkMode, toggleDarkMode } = useDarkMode()
  
  // Get tab from URL query params, default to 'integrations'
  const getTabFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'integrations' | 'models' | 'agents' | 'custom-fields' | 'general'
    return ['integrations', 'models', 'agents', 'custom-fields', 'general'].includes(tab) ? tab : 'integrations'
  }, [location.search])

  const [activeTab, setActiveTab] = useState<'integrations' | 'models' | 'agents' | 'custom-fields' | 'general'>(getTabFromUrl())
  
  const integrationConfigs = [
    { key: 'integration.github.main', title: 'GitHub', type: 'github' },
    { key: 'integration.jira.main', title: 'Jira', type: 'jira' },
    { key: 'integration.slack.main', title: 'Slack', type: 'slack' },
  ]

  const llmConfigs = [
    { key: 'llm.openai.main', title: 'OpenAI', type: 'openai' },
    { key: 'llm.anthropic.main', title: 'Anthropic', type: 'anthropic' },
    { key: 'llm.google.main', title: 'Google', type: 'google' },
  ]

  const agentTypes = [
    { key: 'project', name: 'Project Q&A Agent', description: 'Answers questions about projects and helps with specifications' },
    { key: 'task_planning', name: 'Task Planning Agent', description: 'Creates implementation plans for tasks' },
    { key: 'task_implementation', name: 'Task Implementation Agent', description: 'Provides implementation guidance and code suggestions' },
    { key: 'task_pr_review', name: 'Task PR Review Agent', description: 'Reviews pull requests and provides feedback' },
    { key: 'investigation', name: 'Investigation Agent', description: 'Analyzes codebases and gathers context' },
    { key: 'code_review', name: 'Code Review Agent', description: 'Reviews code changes and provides detailed feedback' },
  ]
  
  const [selectedConfig, setSelectedConfig] = useState<string | null>(integrationConfigs[0]?.key || null)
  const [selectedAgentRole, setSelectedAgentRole] = useState<string>(agentTypes[0]?.key || 'project')
  const [configStatuses, setConfigStatuses] = useState<Record<string, { isValid: boolean; errors?: string[] }>>({})
  const [configDetailsCache, setConfigDetailsCache] = useState<Record<string, ConfigurationDetailResponse>>({})
  const [loadingStatuses, setLoadingStatuses] = useState(false)
  const [devboardConfig, setDevboardConfig] = useState<ConfigurationDetailResponse | null>(null)
  const [loadingDevboardConfig, setLoadingDevboardConfig] = useState(false)
  const [claudeCodeEngineConfig, setClaudeCodeEngineConfig] = useState<ConfigurationDetailResponse | null>(null)
  const [loadingClaudeCodeEngine, setLoadingClaudeCodeEngine] = useState(false)

  const handleConfigurationSave = (config: ConfigurationDetailResponse) => {
    console.log('Configuration saved:', config)
    // Update both status and cached details after save
    setConfigStatuses(prev => ({
      ...prev,
      [config.key]: {
        isValid: config.is_valid,
        errors: config.validation_errors
      }
    }))
    setConfigDetailsCache(prev => ({
      ...prev,
      [config.key]: config
    }))
    // Could show a toast notification here
  }

  const handleTestConnection = () => {
    console.log('Connection tested')
    // Could show a toast notification here
  }

  const loadConfigurationStatuses = async () => {
    try {
      setLoadingStatuses(true)
      
      // Fetch integration configurations
      const integrationConfigsData = await apiClient.listConfigurations('integration.')
      // Fetch LLM provider configurations  
      const llmConfigsData = await apiClient.listConfigurations('llm.')
      
      const statusMap: Record<string, { isValid: boolean; errors?: string[] }> = {}
      const detailsCache: Record<string, ConfigurationDetailResponse> = {}
      
      // Process integration configs
      integrationConfigsData.forEach(config => {
        statusMap[config.key] = {
          isValid: config.is_valid,
          errors: config.validation_errors || undefined
        }
        detailsCache[config.key] = config
      })
      
      // Process LLM configs
      llmConfigsData.forEach(config => {
        statusMap[config.key] = {
          isValid: config.is_valid,
          errors: config.validation_errors || undefined
        }
        detailsCache[config.key] = config
      })
      
      setConfigStatuses(statusMap)
      setConfigDetailsCache(detailsCache)
    } catch (error) {
      console.error('Failed to load configuration statuses:', error)
    } finally {
      setLoadingStatuses(false)
    }
  }

  const loadDevboardConfig = async () => {
    try {
      setLoadingDevboardConfig(true)
      const configs = await apiClient.listConfigurations('devboard.')
      const config = configs.find(c => c.key === 'devboard.main')
      if (config) setDevboardConfig(config)
    } catch (error) {
      console.error('Failed to load devboard config:', error)
    } finally {
      setLoadingDevboardConfig(false)
    }
  }

  const loadClaudeCodeEngineConfig = async () => {
    try {
      setLoadingClaudeCodeEngine(true)
      const config = await apiClient.getConfigurationDetail('agents.claude_code')
      setClaudeCodeEngineConfig(config)
    } catch (error) {
      console.error('Failed to load Claude Code Engine config:', error)
    } finally {
      setLoadingClaudeCodeEngine(false)
    }
  }

  // Update URL when tab changes
  const handleTabChange = (newTab: 'integrations' | 'models' | 'agents' | 'custom-fields' | 'general') => {
    setActiveTab(newTab)
    const params = new URLSearchParams(location.search)
    params.set('tab', newTab)
    navigate(`/settings?${params.toString()}`, { replace: true })

    // Auto-select first item when switching to integrations
    if (newTab === 'integrations') {
      setSelectedConfig(integrationConfigs[0]?.key || null)
      // Load configuration statuses when switching to integrations
      loadConfigurationStatuses()
    } else {
      setSelectedConfig(null)
    }

    if (newTab === 'general') {
      loadDevboardConfig()
    }

    if (newTab === 'agents') {
      loadClaudeCodeEngineConfig()
    }
  }

  // Update activeTab when URL changes
  useEffect(() => {
    const urlTab = getTabFromUrl()
    setActiveTab(urlTab)
  }, [getTabFromUrl])

  // Load configuration statuses on mount if on integrations tab
  useEffect(() => {
    if (activeTab === 'integrations') {
      loadConfigurationStatuses()
    }
    if (activeTab === 'general') {
      loadDevboardConfig()
    }
    if (activeTab === 'agents') {
      loadClaudeCodeEngineConfig()
    }
  }, [activeTab])

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <ViewHeader
        icon={Cog6ToothIcon}
        iconColor="text-gray-600 dark:text-gray-400"
        title="Settings"
      />

      <div className="flex-1 overflow-auto py-6">
      {/* Navigation Tabs */}
      <div className={`border-b ${borderColors.default} mb-8`}>
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'integrations' as const, name: 'Integrations', icon: LinkIcon },
            { id: 'models' as const, name: 'Models', icon: SparklesIcon },
            { id: 'agents' as const, name: 'Agents', icon: CpuChipIcon },
            { id: 'custom-fields' as const, name: 'Task Custom Fields', icon: TagIcon },
            { id: 'general' as const, name: 'General', icon: CogIcon },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.name}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'integrations' && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Combined Integration List */}
          <div className="md:col-span-1">
            <Card padding="none">
              <div className={`px-6 py-4 border-b ${borderColors.default}`}>
                <h3 className={`text-lg font-medium ${textColors.primary}`}>All Integrations</h3>
                <p className={`text-sm ${textColors.secondary} mt-1`}>
                  Configure external connections
                </p>
              </div>
              
              <ConfigurationList
                integrationConfigs={integrationConfigs}
                llmConfigs={llmConfigs}
                selectedConfig={selectedConfig}
                configStatuses={configStatuses}
                onSelectConfig={setSelectedConfig}
              />
            </Card>
          </div>

          {/* Configuration Form */}
          <div className="md:col-span-3">
            {selectedConfig ? (
              loadingStatuses || !configDetailsCache[selectedConfig] ? (
                <Card className="p-6">
                  <div className="animate-pulse">
                    <div className="h-4 bg-gray-200 dark:bg-white/[0.06] rounded w-1/4 mb-4"></div>
                    <div className="space-y-3">
                      <div className="h-10 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
                      <div className="h-10 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
                      <div className="h-10 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
                    </div>
                  </div>
                </Card>
              ) : (
                <Card padding="none">
                  <ConfigurationForm
                    config={configDetailsCache[selectedConfig]}
                    title={[...integrationConfigs, ...llmConfigs].find(i => i.key === selectedConfig)?.title || ''}
                    onSave={handleConfigurationSave}
                    onTestConnection={selectedConfig.includes('integration') ? handleTestConnection : undefined}
                  />
                </Card>
              )
            ) : (
              <Card className="p-8 text-center">
                <LinkIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className={`mt-4 text-lg font-medium ${textColors.primary}`}>
                  Select an integration
                </h3>
                <p className={`mt-2 text-sm ${textColors.secondary}`}>
                  Choose an integration from the list to configure its settings
                </p>
              </Card>
            )}
          </div>
        </div>
      )}

      {activeTab === 'models' && (
        <LanguageModelSettings />
      )}

      {activeTab === 'agents' && (
        <div className="space-y-6">
          {/* Agent Role List and Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* Agent Role List */}
            <div className="md:col-span-1">
              <Card padding="none">
                <div className={`px-6 py-4 border-b ${borderColors.default}`}>
                  <h3 className={`text-lg font-medium ${textColors.primary}`}>Agent Roles</h3>
                  <p className={`text-sm ${textColors.secondary} mt-1`}>
                    Configure AI agent behavior
                  </p>
                </div>

                <AgentRoleList
                  roles={agentTypes}
                  selectedRole={selectedAgentRole}
                  onSelectRole={setSelectedAgentRole}
                />
              </Card>
            </div>

            {/* Agent Configuration Panel */}
            <div className="md:col-span-3">
              <Card className="p-6">
                {(() => {
                  const selectedAgent = agentTypes.find(a => a.key === selectedAgentRole)
                  if (!selectedAgent) return null
                  return (
                    <AgentRoleConfigPanel
                      key={selectedAgent.key}
                      agentRole={selectedAgent.key}
                      agentName={selectedAgent.name}
                      agentDescription={selectedAgent.description}
                    />
                  )
                })()}
              </Card>
            </div>
          </div>

          {/* Claude Code Engine Configuration */}
          <Card className="p-6">
            <div className="mb-4">
              <h3 className={`text-base font-medium ${textColors.primary}`}>Claude Code Engine</h3>
            </div>
            {loadingClaudeCodeEngine ? (
              <div className="animate-pulse">
                <div className="h-10 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
              </div>
            ) : claudeCodeEngineConfig && claudeCodeEngineConfig.fields.length > 0 ? (
              <div className="flex items-center space-x-4">
                <label className={`text-sm font-medium ${textColors.primary}`}>
                  Client Mode
                </label>
                <select
                  value={claudeCodeEngineConfig.fields[0]?.effective_value || ''}
                  onChange={async (e) => {
                    const newValue = e.target.value
                    try {
                      const updated = await apiClient.updateConfigurationFields('agents.claude_code', {
                        client_mode: newValue
                      })
                      setClaudeCodeEngineConfig(updated)
                    } catch (error) {
                      console.error('Failed to update Claude Code Engine config:', error)
                    }
                  }}
                  className={`px-3 py-2 border ${borderColors.input} rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-white/[0.06] dark:text-white`}
                >
                  {claudeCodeEngineConfig.fields[0]?.enum_values?.map((value) => (
                    <option key={value} value={value}>
                      {value.charAt(0).toUpperCase() + value.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className={`text-sm ${textColors.secondary}`}>Failed to load configuration.</div>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'custom-fields' && (
        <CustomFieldSettings />
      )}

      {activeTab === 'general' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center space-x-2 mb-4">
              <CogIcon className="w-5 h-5 text-gray-400" />
              <h3 className={`text-lg font-medium ${textColors.primary}`}>General Settings</h3>
            </div>
            
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className={`text-sm font-medium ${textColors.primary}`}>Dark Mode</h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Toggle dark mode theme</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={isDarkMode}
                    onChange={toggleDarkMode}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-white/[0.06] peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              <div className={`border-t ${borderColors.default} pt-6`}>
                <h4 className={`text-sm font-medium ${textColors.primary} mb-4`}>API Configuration</h4>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Backend URL
                    </label>
                    <input
                      type="text"
                      defaultValue="http://localhost:8000"
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-white/[0.06] dark:text-white"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      URL of the DevBoard backend API
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Card padding="none">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-white/[0.08]">
              <h3 className={`text-lg font-medium ${textColors.primary}`}>Workspace Configuration</h3>
              <p className={`text-sm ${textColors.secondary} mt-1`}>Configure how task workspaces are managed</p>
            </div>
            {loadingDevboardConfig ? (
              <div className="p-6 animate-pulse">
                <div className="h-10 bg-gray-200 dark:bg-white/[0.06] rounded"></div>
              </div>
            ) : devboardConfig ? (
              <ConfigurationForm
                config={devboardConfig}
                title=""
                onSave={(config) => setDevboardConfig(config)}
              />
            ) : (
              <div className="p-6 text-sm text-gray-500 dark:text-gray-400">Failed to load configuration.</div>
            )}
          </Card>
        </div>
      )}
      </div>
    </div>
  )
}