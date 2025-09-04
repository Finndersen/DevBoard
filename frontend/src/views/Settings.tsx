import { useState, useEffect } from 'react'
import { CogIcon, LinkIcon, CloudIcon } from '@heroicons/react/24/outline'
import { apiClient } from '../lib/api'
import type { Integration, LLMProvider } from '../lib/api'

export default function Settings() {
  const [activeTab, setActiveTab] = useState<'integrations' | 'llm' | 'general'>('integrations')
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [llmProviders, setLLMProviders] = useState<LLMProvider[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const [integrationsData, llmData] = await Promise.all([
        apiClient.getIntegrations(),
        apiClient.getLLMProviders()
      ])

      setIntegrations(integrationsData)
      setLLMProviders(llmData)
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleIntegrationToggle = async (integrationId: string) => {
    try {
      await apiClient.toggleIntegration(integrationId)
      await fetchSettings()
    } catch (error) {
      console.error('Failed to toggle integration:', error)
    }
  }

  const handleLLMProviderToggle = async (providerId: string) => {
    try {
      await apiClient.toggleLLMProvider(providerId)
      await fetchSettings()
    } catch (error) {
      console.error('Failed to toggle LLM provider:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

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
            { id: 'llm' as const, name: 'AI Providers', icon: CloudIcon },
            { id: 'general' as const, name: 'General', icon: CogIcon },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
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
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">External Integrations</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Connect DevBoard to external services for enhanced functionality
              </p>
            </div>
            
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {integrations.length === 0 ? (
                <div className="px-6 py-8 text-center">
                  <LinkIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No integrations configured</h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Integrations will be available once they are set up.
                  </p>
                </div>
              ) : (
                integrations.map((integration) => (
                  <div key={integration.id} className="px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${
                        integration.status === 'connected' ? 'bg-green-400' : 'bg-red-400'
                      }`} />
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">{integration.name}</h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">{integration.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        integration.status === 'connected'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                          : 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400'
                      }`}>
                        {integration.status}
                      </span>
                      <button
                        onClick={() => handleIntegrationToggle(integration.id)}
                        className="text-sm text-blue-600 hover:text-blue-500 dark:text-blue-400"
                      >
                        Configure
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'llm' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">AI Providers</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Configure AI language model providers for chat agents
              </p>
            </div>
            
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {llmProviders.length === 0 ? (
                <div className="px-6 py-8 text-center">
                  <CloudIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No AI providers configured</h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    AI providers will be available once they are configured.
                  </p>
                </div>
              ) : (
                llmProviders.map((provider) => (
                  <div key={provider.id} className="px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className={`w-3 h-3 rounded-full ${
                        provider.enabled ? 'bg-green-400' : 'bg-gray-400'
                      }`} />
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 dark:text-white">{provider.name}</h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">{provider.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={provider.enabled}
                          onChange={() => handleLLMProviderToggle(provider.id)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                      </label>
                      <button className="text-sm text-blue-600 hover:text-blue-500 dark:text-blue-400">
                        Configure
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
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
                    defaultChecked={window.matchMedia('(prefers-color-scheme: dark)').matches}
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