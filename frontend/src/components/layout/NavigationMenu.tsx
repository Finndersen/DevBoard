import { Link, useLocation } from 'react-router-dom'
import {
  HomeIcon,
  Cog6ToothIcon,
  PuzzlePieceIcon,
  FolderIcon,
  ListBulletIcon,
  CodeBracketIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'

interface NavigationSection {
  icon: typeof HomeIcon
  label: string
  route: string
}

const navigationSections: NavigationSection[] = [
  { icon: HomeIcon, label: 'Home', route: '/' },
  { icon: FolderIcon, label: 'Projects', route: '/projects' },
  { icon: ListBulletIcon, label: 'Tasks', route: '/tasks' },
  { icon: CodeBracketIcon, label: 'Codebases', route: '/codebases' },
  { icon: PuzzlePieceIcon, label: 'MCP Servers', route: '/mcp-servers' },
  { icon: Cog6ToothIcon, label: 'Settings', route: '/settings' },
]

export default function NavigationMenu() {
  const location = useLocation()
  const {
    navigationMenuOpen,
    setNavigationMenuOpen,
    navigationCompactMode,
    toggleNavigationCompactMode,
  } = useUIStore()

  if (!navigationMenuOpen) {
    return null
  }

  const isCompact = navigationCompactMode
  const panelWidth = isCompact ? 'w-16' : 'w-56'

  return (
    <>
      {/* Overlay - only on small screens */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
        onClick={() => setNavigationMenuOpen(false)}
      />

      {/* Menu Panel */}
      <div
        className={`${panelWidth} shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 flex flex-col
          fixed inset-y-0 left-0 z-50 lg:relative lg:z-auto`}
      >
        {/* Header */}
        <div className={`flex items-center ${isCompact ? 'justify-center' : 'justify-between'} p-3 border-b border-gray-200 dark:border-gray-700`}>
          {!isCompact && (
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
              DevBoard
            </h2>
          )}
          <div className="flex items-center gap-1">
            {/* Close button on small screens */}
            <button
              onClick={() => setNavigationMenuOpen(false)}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded lg:hidden"
              aria-label="Close menu"
            >
              <XMarkIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
            </button>
            {/* Compact mode toggle on large screens */}
            <button
              onClick={toggleNavigationCompactMode}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded hidden lg:block"
              aria-label={isCompact ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCompact ? (
                <ChevronRightIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              ) : (
                <ChevronLeftIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
              )}
            </button>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-2 space-y-1 flex-1">
          {navigationSections.map((section) => {
            const isActive = location.pathname === section.route ||
              (section.route !== '/' && location.pathname.startsWith(section.route))
            return (
              <Link
                key={section.route}
                to={section.route}
                onClick={() => {
                  // Close on mobile
                  if (window.innerWidth < 1024) {
                    setNavigationMenuOpen(false)
                  }
                }}
                className={`flex items-center ${isCompact ? 'justify-center' : 'gap-3'} px-3 py-2 rounded-md transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title={isCompact ? section.label : undefined}
              >
                <section.icon className="w-5 h-5 shrink-0" />
                {!isCompact && (
                  <span className="font-medium text-sm">{section.label}</span>
                )}
              </Link>
            )
          })}
        </nav>
      </div>
    </>
  )
}
