interface Tab {
  id: string
  label: string
}

interface InViewTabsProps {
  tabs: Tab[]
  activeTab: string
  onTabChange: (id: string) => void
}

export default function InViewTabs({ tabs, activeTab, onTabChange }: InViewTabsProps) {
  return (
    <div className="border-b border-gray-200 dark:border-gray-700">
      <nav className="flex space-x-4" aria-label="Tabs">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                px-3 py-2 text-sm font-medium border-b-2 transition-colors
                ${isActive
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                }
              `}
              aria-current={isActive ? 'page' : undefined}
            >
              {tab.label}
            </button>
          )
        })}
      </nav>
    </div>
  )
}
