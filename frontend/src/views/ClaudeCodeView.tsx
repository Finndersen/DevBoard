import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CommandLineIcon, QueueListIcon } from '@heroicons/react/24/outline'
import type { ForwardRefExoticComponent, SVGProps, RefAttributes } from 'react'
import SessionsTab from '../components/claude-code/SessionsTab'
import ViewHeader from '../components/layout/ViewHeader'

type ClaudeCodeTab = 'session-viewer'

const VALID_TABS: ClaudeCodeTab[] = ['session-viewer']

const TAB_CONFIG: Record<ClaudeCodeTab, { label: string; icon: ForwardRefExoticComponent<SVGProps<SVGSVGElement> & RefAttributes<SVGSVGElement>> }> = {
  'session-viewer': { label: 'Session Viewer', icon: QueueListIcon },
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
      <div className="border-b border-gray-200 dark:border-white/[0.08] px-6 shrink-0">
        <nav className="-mb-px flex space-x-8">
          {VALID_TABS.map(tab => {
            const { label, icon: Icon } = TAB_CONFIG[tab]
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </button>
            )
          })}
        </nav>
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'session-viewer' && <SessionsTab />}
      </div>
    </div>
  )
}
