import { PlusIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'
import Tab from './Tab'
import { useNavigate } from 'react-router-dom'

export default function TabBar() {
  const { tabs, activeTabId, switchTab, closeTab, openTab } = useUIStore()
  const navigate = useNavigate()

  const handleTabSelect = (tabId: string) => {
    switchTab(tabId)
  }

  const handleTabClose = (tabId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    closeTab(tabId)
  }

  const handleNewTab = () => {
    // Open home tab by default
    openTab({
      type: 'home',
      entityId: 'main',
      title: 'Home'
    })

    // Navigate to home
    navigate('/')
  }

  if (tabs.length === 0) {
    return null
  }

  return (
    <div className="flex items-center border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-x-auto">
      {/* Tabs */}
      <div className="flex flex-1 overflow-x-auto">
        {tabs.map((tab) => (
          <Tab
            key={tab.id}
            tab={tab}
            isActive={tab.id === activeTabId}
            onSelect={() => handleTabSelect(tab.id)}
            onClose={(e) => handleTabClose(tab.id, e)}
          />
        ))}
      </div>

      {/* New Tab Button */}
      <button
        onClick={handleNewTab}
        className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex-shrink-0 border-l border-gray-200 dark:border-gray-700"
        aria-label="New tab"
        title="Open new tab (Cmd+T)"
      >
        <PlusIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>
    </div>
  )
}
