import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CommandLineIcon } from '@heroicons/react/24/outline'
import SessionsTab from '../components/claude-code/SessionsTab'
import ViewHeader from '../components/layout/ViewHeader'

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
      <ViewHeader icon={CommandLineIcon} title="Claude Code" />
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 px-6 bg-white dark:bg-gray-800 shrink-0">
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
      <div className="flex-1 overflow-hidden">
        {activeTab === 'session-viewer' && <SessionsTab />}
      </div>
    </div>
  )
}
