import { Link } from 'react-router-dom'
import { XMarkIcon, HomeIcon, Cog6ToothIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'

interface NavigationSection {
  icon: typeof HomeIcon
  label: string
  route: string
}

const navigationSections: NavigationSection[] = [
  { icon: HomeIcon, label: 'Home', route: '/' },
  { icon: Cog6ToothIcon, label: 'Settings', route: '/settings' }
]

export default function NavigationMenu() {
  const { navigationMenuOpen, setNavigationMenuOpen } = useUIStore()

  if (!navigationMenuOpen) {
    return null
  }

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
        onClick={() => setNavigationMenuOpen(false)}
      />

      {/* Menu Panel */}
      <div className="fixed inset-y-0 left-0 w-64 bg-white dark:bg-gray-800 shadow-lg z-50 transform transition-transform duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Navigation
          </h2>
          <button
            onClick={() => setNavigationMenuOpen(false)}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            aria-label="Close menu"
          >
            <XMarkIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="p-4 space-y-2">
          {navigationSections.map((section) => (
            <Link
              key={section.route}
              to={section.route}
              onClick={() => setNavigationMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-md text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <section.icon className="w-5 h-5" />
              <span className="font-medium">{section.label}</span>
            </Link>
          ))}
        </nav>

        {/* Future: Recent Items Section */}
        <div className="px-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
            Recent
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 italic">
            No recent items
          </p>
        </div>
      </div>
    </>
  )
}
