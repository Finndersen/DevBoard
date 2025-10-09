import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useUIStore } from '../stores/uiStore'
import type { TabType } from '../stores/uiStore'

/**
 * Hook to synchronize URL with tab state
 * - On URL change: Opens/switches to appropriate tab
 * - On tab switch: Updates URL
 */
export function useURLSync() {
  const location = useLocation()
  const navigate = useNavigate()
  const { openTab, switchTab, getActiveTab, findTabByEntity } = useUIStore()
  const activeTabId = useUIStore(state => state.activeTabId)

  // Parse URL to determine tab type and entity ID
  const parseURL = (pathname: string): { type: TabType; entityId: string; title: string } | null => {
    // Home (consolidated projects and codebases view)
    if (pathname === '/' || pathname === '/projects' || pathname === '/codebases') {
      return { type: 'home', entityId: 'main', title: 'Home' }
    }

    // Project detail
    const projectMatch = pathname.match(/^\/projects\/(\d+)$/)
    if (projectMatch) {
      return { type: 'project', entityId: projectMatch[1], title: `Project #${projectMatch[1]}` }
    }

    // Task detail
    const taskMatch = pathname.match(/^\/tasks\/(\d+)$/)
    if (taskMatch) {
      return { type: 'task', entityId: taskMatch[1], title: `Task #${taskMatch[1]}` }
    }

    // Settings
    if (pathname === '/settings') {
      return { type: 'settings', entityId: 'main', title: 'Settings' }
    }

    return null
  }

  // Sync URL to tabs (URL changed -> open/switch tab)
  useEffect(() => {
    const tabInfo = parseURL(location.pathname)
    if (!tabInfo) return

    // Check if tab already exists
    const existingTab = findTabByEntity(tabInfo.type, tabInfo.entityId)
    if (existingTab) {
      // Switch to existing tab if not already active
      switchTab(existingTab.id)
    } else {
      // Open new tab
      openTab(tabInfo)
    }
  }, [location.pathname, openTab, switchTab, findTabByEntity])

  // Sync tabs to URL (active tab changed -> update URL)
  useEffect(() => {
    const activeTab = getActiveTab()
    if (!activeTab) return

    // Generate URL from active tab
    let targetPath = '/'

    switch (activeTab.type) {
      case 'home':
        targetPath = '/'
        break
      case 'project':
        targetPath = `/projects/${activeTab.entityId}`
        break
      case 'task':
        targetPath = `/tasks/${activeTab.entityId}`
        break
      case 'codebase':
        // Codebases are managed in Home view now
        targetPath = '/'
        break
      case 'settings':
        targetPath = '/settings'
        break
    }

    // Only navigate if URL needs to change (prevent infinite loop)
    if (location.pathname !== targetPath) {
      navigate(targetPath, { replace: true })
    }
  }, [activeTabId, location.pathname, navigate, getActiveTab])
}
