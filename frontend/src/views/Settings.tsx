import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { CogIcon, LinkIcon, CpuChipIcon, TagIcon } from '@heroicons/react/24/outline'
import { ConfigurationForm } from '../components/configuration/ConfigurationForm'
import { ConfigurationList } from '../components/configuration/ConfigurationList'
import { AgentConfigurationSelector } from '../components/configuration/AgentConfigurationSelector'
import { CustomFieldSettings } from '../components/settings/CustomFieldSettings'
import { useDarkMode } from '../contexts/DarkModeContext'
import type { ConfigurationDetailResponse } from '../lib/api'
import { Card } from '../components/ui'
import { textColors } from '../styles/designSystem'
import { apiClient } from '../lib/api'

export default function Settings() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isDarkMode, toggleDarkMode } = useDarkMode()
  
  // Get tab from URL query params, default to 'integrations'
  const getTabFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'integrations' | 'agents' | 'custom-fields' | 'general'
    return ['integrations', 'agents', 'custom-fields', 'general'].includes(tab) ? tab : 'integrations'
  }, [location.search])

  const [activeTab, setActiveTab] = useState<'integrations' | 'agents' | 'custom-fields' | 'general'>(getTabFromUrl())
  
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
  ]
  
  const [selectedConfig, setSelectedConfig] = useState<string | null>(integrationConfigs[0]?.key || null)
  const [configStatuses, setConfigStatuses] = useState<Record<string, { isValid: boolean; errors?: string[] }>>({})
  const [configDetailsCache, setConfigDetailsCache] = useState<Record<string, ConfigurationDetailResponse>>({})
  const [loadingStatuses, setLoadingStatuses] = useState(false)

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

  // Update URL when tab changes
  const handleTabChange = (newTab: 'integrations' | 'agents' | 'custom-fields' | 'general') => {
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
  }, [activeTab])

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className={`text-3xl font-bold ${textColors.primary}`}>Settings</h1>
        <p className={`${textColors.secondary} mt-2`}>
          Configure integrations, AI providers, and system preferences
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-8">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'integrations' as const, name: 'Integrations', icon: LinkIcon },
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
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
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
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4"></div>
                    <div className="space-y-3">
                      <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
                      <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
                      <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
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
                <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                  Select an integration
                </h3>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  Choose an integration from the list to configure its settings
                </p>
              </Card>
            )}
          </div>
        </div>
      )}

      {activeTab === 'agents' && (
        <div>
          <Card className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {agentTypes.map((agent) => (
                <div
                  key={agent.key}
                  className="p-4 border border-gray-200 dark:border-gray-600 rounded-lg hover:border-gray-300 dark:hover:border-gray-500 transition-colors"
                >
                  <AgentConfigurationSelector
                    agentRole={agent.key}
                    agentName={agent.name}
                    onConfigChange={(agentRole, engine, modelId) => {
                      console.log(`Agent ${agentRole} config changed to engine: ${engine}, model: ${modelId}`)
                    }}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    {agent.description}
                  </p>
                </div>
              ))}
            </div>
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
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white">Dark Mode</h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Toggle dark mode theme</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={isDarkMode}
                    onChange={toggleDarkMode}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white">Auto-save</h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Automatically save changes</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    defaultChecked={true}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
              </div>
              
              <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-4">API Configuration</h4>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Backend URL
                    </label>
                    <input
                      type="text"
                      defaultValue="http://localhost:8000"
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      URL of the DevBoard backend API
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}