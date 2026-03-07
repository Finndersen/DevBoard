import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CommandLineIcon } from '@heroicons/react/24/outline'
import SessionsTab from '../components/claude-code/SessionsTab'

type ClaudeCodeTab = 'session-viewer'

const VALID_TABS: ClaudeCodeTab[] = ['session-viewer']

const TAB_LABELS: Record<ClaudeCodeTab, string> = {
  'session-viewer': 'Session Viewer',
}

export default function ClaudeCodeView() {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeTab = useCallback((): ClaudeCodeTab => {
    const tab = searchParams.get('tab') as ClaudeCodeTab
    return VALID_TABS.includes(tab) ? tab : 'session-viewer'
  }, [searchParams])()

  const setActiveTab = (tab: ClaudeCodeTab) => {
    setSearchParams(prev => { prev.set('tab', tab); return prev }, { replace: true })
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex items-center gap-3 mb-3">
          <CommandLineIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Claude Code</h1>
        </div>
        <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 -mb-3 -mx-6 px-6">
          {VALID_TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'session-viewer' && <SessionsTab />}
      </div>
    </div>
  )
}
