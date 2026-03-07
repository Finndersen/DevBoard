import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CommandLineIcon } from '@heroicons/react/24/outline'
import { textColors } from '../styles/designSystem'
import SessionsTab from '../components/claude-code/SessionsTab'

type ClaudeCodeTab = 'sessions'

const VALID_TABS: ClaudeCodeTab[] = ['sessions']

export default function ClaudeCodeView() {
  const [searchParams, setSearchParams] = useSearchParams()

  const getActiveTab = useCallback((): ClaudeCodeTab => {
    const tab = searchParams.get('tab') as ClaudeCodeTab
    return VALID_TABS.includes(tab) ? tab : 'sessions'
  }, [searchParams])

  const activeTab = getActiveTab()

  const setActiveTab = (tab: ClaudeCodeTab) => {
    setSearchParams(prev => {
      prev.set('tab', tab)
      return prev
    }, { replace: true })
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex items-center gap-3">
          <CommandLineIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          <div>
            <h1 className={`text-xl font-semibold ${textColors.primary}`}>Claude Code</h1>
            <p className={`text-sm ${textColors.secondary}`}>
              Browse and search Claude Code project session histories
            </p>
          </div>
        </div>

        {/* Sub-tab navigation */}
        <div className="mt-4 flex gap-1 border-b border-gray-200 dark:border-gray-700 -mb-4 -mx-6 px-6">
          <button
            onClick={() => setActiveTab('sessions')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'sessions'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            }`}
          >
            Sessions
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'sessions' && <SessionsTab />}
      </div>
    </div>
  )
}
