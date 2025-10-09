import type { ReactNode } from 'react'
import TopBar from './TopBar'
import TabBar from './TabBar'
import NavigationMenu from './NavigationMenu'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col">
      {/* Top Bar */}
      <TopBar />

      {/* Tab Bar */}
      <TabBar />

      {/* Navigation Menu (Slide-out) */}
      <NavigationMenu />

      {/* Main Content */}
      <main className="flex-1 w-full py-4 px-4 sm:px-6 lg:px-8 overflow-auto">
        {children}
      </main>
    </div>
  )
}
