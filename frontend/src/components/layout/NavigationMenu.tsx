import { Link, useLocation } from 'react-router-dom'
import { surfaces, borderColors, textColors } from '../../styles/designSystem'
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
  PlusIcon,
  NewspaperIcon,
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
  { icon: NewspaperIcon, label: 'Events', route: '/events' },
  { icon: CodeBracketIcon, label: 'Codebases', route: '/codebases' },
  { icon: PuzzlePieceIcon, label: 'MCP Servers', route: '/mcp-servers' },
  { icon: CommandLineIcon, label: 'Claude Code', route: '/claude-code' },
  { icon: Cog6ToothIcon, label: 'Settings', route: '/settings' },
]

export default function NavigationMenu() {
  const location = useLocation()
  const {
    navigationCompactMode,
    toggleNavigationCompactMode,
    openCreateTaskModal,
  } = useUIStore()

  const isCompact = navigationCompactMode
  const panelWidth = isCompact ? 'w-16' : 'w-40'

  return (
    <div
      className={`${panelWidth} shrink-0 ${surfaces.raised} border-r ${borderColors.default} transition-all duration-200 flex flex-col`}
    >
      {/* Logo header */}
      <div className={`h-16 flex items-center ${isCompact ? 'justify-center px-2' : 'px-3'} border-b ${borderColors.default} flex-shrink-0`}>
        <Link to="/" className={`flex items-center ${isCompact ? '' : 'gap-3'}`}>
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
            <span className="text-white font-bold text-sm">DB</span>
          </div>
          {!isCompact && (
            <span className={`text-base font-bold ${textColors.primary}`}>
              DevBoard
            </span>
          )}
        </Link>
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
              className={`flex items-center ${isCompact ? 'justify-center' : 'gap-3'} px-2 py-2 rounded-md transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              title={isCompact ? section.label : undefined}
            >
              <section.icon className="w-5 h-5 shrink-0" />
              {!isCompact && (
                <span className="font-medium text-sm flex-1">{section.label}</span>
              )}
              {!isCompact && section.label === 'Tasks' && (
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    openCreateTaskModal()
                  }}
                  className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                  title="New task"
                >
                  <PlusIcon className="w-4 h-4" />
                </button>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer: collapse toggle */}
      <div className={`border-t ${borderColors.default} p-2`}>
        <button
          onClick={toggleNavigationCompactMode}
          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
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
  )
}
