import { Link, useLocation } from 'react-router-dom'
import {
  HomeIcon,
  Cog6ToothIcon,
  PuzzlePieceIcon,
  FolderIcon,
  ListBulletIcon,
  CodeBracketIcon,
  CommandLineIcon,
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
  { icon: CommandLineIcon, label: 'Claude Code', route: '/claude-code' },
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
        {/* Logo header */}
        <div className={`h-16 flex items-center ${isCompact ? 'justify-center px-2' : 'px-3'} border-b border-gray-200 dark:border-gray-700 flex-shrink-0`}>
          <Link to="/" className={`flex items-center ${isCompact ? '' : 'gap-3'}`}>
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
              <span className="text-white font-bold text-sm">DB</span>
            </div>
            {!isCompact && (
              <span className="text-base font-bold text-gray-900 dark:text-white">
                DevBoard
              </span>
            )}
          </Link>
          {/* Close button on small screens */}
          {!isCompact && (
            <button
              onClick={() => setNavigationMenuOpen(false)}
              className="ml-auto p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded lg:hidden"
              aria-label="Close menu"
            >
              <XMarkIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
            </button>
          )}
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

        {/* Footer: collapse toggle (desktop only) */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-2">
          <button
            onClick={toggleNavigationCompactMode}
            className={`w-full flex items-center ${isCompact ? 'justify-center' : 'gap-2'} px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md hidden lg:flex`}
            aria-label={isCompact ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCompact ? (
              <ChevronRightIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
            ) : (
              <>
                <ChevronLeftIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                <span className="text-xs text-gray-500 dark:text-gray-400">Collapse</span>
              </>
            )}
          </button>
        </div>
      </div>
    </>
  )
}
