import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { CogIcon, LinkIcon, CloudIcon, CpuChipIcon } from '@heroicons/react/24/outline'
import { ConfigurationForm } from '../components/ConfigurationForm'
import { AgentModelSelector } from '../components/AgentModelSelector'
import { useDarkMode } from '../contexts/DarkModeContext'
import type { ConfigurationDetailResponse } from '../lib/api'

export default function Settings() {
  const navigate = useNavigate()
  const location = useLocation()
  const { isDarkMode, toggleDarkMode } = useDarkMode()
  
  // Get tab from URL query params, default to 'integrations'
  const getTabFromUrl = () => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'integrations' | 'agents' | 'providers' | 'general'
    return ['integrations', 'agents', 'providers', 'general'].includes(tab) ? tab : 'integrations'
  }
  
  const [activeTab, setActiveTab] = useState<'integrations' | 'agents' | 'providers' | 'general'>(getTabFromUrl())
  
  const integrationConfigs = [
    { key: 'integration.github.main', title: 'GitHub Integration', type: 'github' },
    { key: 'integration.jira.main', title: 'Jira Integration', type: 'jira' },
    { key: 'integration.slack.main', title: 'Slack Integration', type: 'slack' },
  ]

  const llmConfigs = [
    { key: 'llm.openai.main', title: 'OpenAI Provider', type: 'openai' },
    { key: 'llm.anthropic.main', title: 'Anthropic Provider', type: 'anthropic' },
    { key: 'llm.gemini.main', title: 'Gemini Provider', type: 'gemini' },
  ]

  const agentTypes = [
    { key: 'project', name: 'Project Q&A Agent', description: 'Answers questions about projects and helps with specifications' },
    { key: 'task_specification', name: 'Task Specification Agent', description: 'Helps define and refine task requirements' },
    { key: 'task_planning', name: 'Task Planning Agent', description: 'Creates implementation plans for tasks' },
    { key: 'task_implementation', name: 'Task Implementation Agent', description: 'Provides implementation guidance and code suggestions' },
    { key: 'investigation', name: 'Investigation Agent', description: 'Analyzes codebases and gathers context' },
  ]
  
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(integrationConfigs[0]?.key || null)
  const [selectedLLMProvider, setSelectedLLMProvider] = useState<string | null>(null)

  const handleConfigurationSave = (config: ConfigurationDetailResponse) => {
    console.log('Configuration saved:', config)
    // Could show a toast notification here
  }

  const handleTestConnection = () => {
    console.log('Connection tested')
    // Could show a toast notification here
  }

  // Update URL when tab changes
  const handleTabChange = (newTab: 'integrations' | 'agents' | 'providers' | 'general') => {
    setActiveTab(newTab)
    const params = new URLSearchParams(location.search)
    params.set('tab', newTab)
    navigate(`/settings?${params.toString()}`, { replace: true })
    
    // Auto-select first item when switching tabs
    if (newTab === 'integrations') {
      setSelectedIntegration(integrationConfigs[0]?.key || null)
      setSelectedLLMProvider(null)
    } else if (newTab === 'providers') {
      setSelectedLLMProvider(llmConfigs[0]?.key || null)
      setSelectedIntegration(null)
    } else {
      setSelectedIntegration(null)
      setSelectedLLMProvider(null)
    }
  }

  // Update activeTab when URL changes
  useEffect(() => {
    const urlTab = getTabFromUrl()
    setActiveTab(urlTab)
  }, [location.search])

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Settings</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Configure integrations, AI providers, and system preferences
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-8">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'integrations' as const, name: 'Integrations', icon: LinkIcon },
            { id: 'agents' as const, name: 'Agents', icon: CpuChipIcon },
            { id: 'providers' as const, name: 'AI Providers', icon: CloudIcon },
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
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Integration List */}
          <div className="xl:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">External Integrations</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Select an integration to configure
                </p>
              </div>
              
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {integrationConfigs.map((integration) => (
                  <button
                    key={integration.key}
                    onClick={() => setSelectedIntegration(integration.key)}
                    className={`w-full px-6 py-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700 ${
                      selectedIntegration === integration.key ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                          {integration.title}
                        </h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                          {integration.type}
                        </p>
                      </div>
                      {selectedIntegration === integration.key && (
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Configuration Form */}
          <div className="xl:col-span-3">
            {selectedIntegration ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <ConfigurationForm
                  configKey={selectedIntegration}
                  title={integrationConfigs.find(i => i.key === selectedIntegration)?.title || ''}
                  onSave={handleConfigurationSave}
                  onTestConnection={handleTestConnection}
                />
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
                <LinkIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                  Select an integration
                </h3>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  Choose an integration from the list to configure its settings
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'agents' && (
        <div>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {agentTypes.map((agent) => (
                <div
                  key={agent.key}
                  className="p-4 border border-gray-200 dark:border-gray-600 rounded-lg hover:border-gray-300 dark:hover:border-gray-500 transition-colors"
                >
                  <AgentModelSelector
                    agentType={agent.key}
                    agentName={agent.name}
                    onModelChange={(agentType, modelId) => {
                      console.log(`Agent ${agentType} model changed to:`, modelId)
                    }}
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    {agent.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'providers' && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* LLM Provider List */}
          <div className="xl:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">AI Providers</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Select a provider to configure
                </p>
              </div>
              
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {llmConfigs.map((provider) => (
                  <button
                    key={provider.key}
                    onClick={() => setSelectedLLMProvider(provider.key)}
                    className={`w-full px-6 py-4 text-left hover:bg-gray-50 dark:hover:bg-gray-700 ${
                      selectedLLMProvider === provider.key ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                          {provider.title}
                        </h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">
                          {provider.type}
                        </p>
                      </div>
                      {selectedLLMProvider === provider.key && (
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Configuration Form */}
          <div className="xl:col-span-3">
            {selectedLLMProvider ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <ConfigurationForm
                  configKey={selectedLLMProvider}
                  title={llmConfigs.find(p => p.key === selectedLLMProvider)?.title || ''}
                  onSave={handleConfigurationSave}
                />
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
                <CloudIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
                  Select an AI provider
                </h3>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  Choose a provider from the list to configure its API settings
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'general' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <CogIcon className="w-5 h-5 text-gray-400" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">General Settings</h3>
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
          </div>
        </div>
      )}
    </div>
  )
}