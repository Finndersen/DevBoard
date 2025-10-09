import { Link } from 'react-router-dom'
import { Bars3Icon } from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'
import NotificationsPanel from '../notifications/NotificationsPanel'

export default function TopBar() {
  const { toggleNavigationMenu } = useUIStore()

  return (
    <nav className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Left side: Menu button and Logo */}
          <div className="flex items-center space-x-3">
            {/* Navigation Menu Toggle */}
            <button
              onClick={toggleNavigationMenu}
              className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Toggle navigation menu"
              title="Toggle navigation (Cmd+B)"
            >
              <Bars3Icon className="w-6 h-6 text-gray-600 dark:text-gray-400" />
            </button>

            {/* Logo & Title */}
            <Link to="/" className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">DB</span>
              </div>
              <span className="text-xl font-bold text-gray-900 dark:text-white">
                DevBoard
              </span>
            </Link>
          </div>

          {/* Right side: Notifications */}
          <div className="flex items-center">
            <NotificationsPanel />
          </div>
        </div>
      </div>
    </nav>
  )
}
