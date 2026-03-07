import { useEffect, useRef } from 'react'
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
  const shouldPushHistory = useUIStore(state => state.shouldPushHistory)

  // Track if we initiated the navigation to avoid pushing duplicate history entries
  const isNavigatingRef = useRef(false)

  // Parse URL to determine tab type and entity ID
  const parseURL = (pathname: string): { type: TabType; entityId: string; title: string } | null => {
    // Home
    if (pathname === '/') {
      return { type: 'home', entityId: 'main', title: 'Home' }
    }

    // List views
    if (pathname === '/projects') {
      return { type: 'projects-list', entityId: 'main', title: 'Projects' }
    }
    if (pathname === '/tasks') {
      return { type: 'tasks-list', entityId: 'main', title: 'Tasks' }
    }
    if (pathname === '/codebases') {
      return { type: 'codebases-list', entityId: 'main', title: 'Codebases' }
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

    // Codebase detail
    const codebaseMatch = pathname.match(/^\/codebases\/(\d+)$/)
    if (codebaseMatch) {
      return { type: 'codebase', entityId: codebaseMatch[1], title: `Codebase #${codebaseMatch[1]}` }
    }

    // Settings
    if (pathname === '/settings') {
      return { type: 'settings', entityId: 'main', title: 'Settings' }
    }

    // MCP Servers
    if (pathname === '/mcp-servers') {
      return { type: 'mcp-servers', entityId: 'main', title: 'MCP Servers' }
    }

    // Claude Code
    if (pathname === '/claude-code') {
      return { type: 'claude-code', entityId: 'main', title: 'Claude Code' }
    }

    return null
  }

  // Sync URL to tabs (URL changed -> open/switch tab)
  useEffect(() => {
    // Skip if we initiated this navigation
    if (isNavigatingRef.current) {
      isNavigatingRef.current = false
      return
    }

    const tabInfo = parseURL(location.pathname)
    if (!tabInfo) return

    // Check if tab already exists
    const existingTab = findTabByEntity(tabInfo.type, tabInfo.entityId)
    if (existingTab) {
      // Switch to existing tab if not already active
      // Pass fromUrlSync=true to avoid setting shouldPushHistory (URL already changed)
      switchTab(existingTab.id, { fromUrlSync: true })
    } else {
      // Open new tab
      // Pass fromUrlSync=true to avoid setting shouldPushHistory (URL already changed)
      openTab(tabInfo, { fromUrlSync: true })
    }
  }, [location.pathname, openTab, switchTab, findTabByEntity])

  // Sync tabs to URL (active tab changed -> update URL)
  useEffect(() => {
    const activeTab = getActiveTab()
    if (!activeTab) return

    // Generate URL from active tab (base path only, ignore query params)
    let targetPath = '/'

    switch (activeTab.type) {
      case 'home':
        targetPath = '/'
        break
      case 'projects-list':
        targetPath = '/projects'
        break
      case 'tasks-list':
        targetPath = '/tasks'
        break
      case 'codebases-list':
        targetPath = '/codebases'
        break
      case 'project':
        targetPath = `/projects/${activeTab.entityId}`
        break
      case 'task':
        targetPath = `/tasks/${activeTab.entityId}`
        break
      case 'codebase':
        targetPath = `/codebases/${activeTab.entityId}`
        break
      case 'settings':
        targetPath = '/settings'
        break
      case 'mcp-servers':
        targetPath = '/mcp-servers'
        break
      case 'claude-code':
        targetPath = '/claude-code'
        break
    }

    // Only navigate if URL pathname needs to change (ignore query params here)
    // Query param changes (like tab switches within a project) are handled by the component itself
    if (location.pathname !== targetPath) {
      // Mark that we're initiating navigation
      isNavigatingRef.current = true

      // Determine if we should push or replace:
      // - Push for new tabs (shouldPushHistory = true) to create history entries
      // - Replace when already on the same tab (shouldPushHistory = false) to avoid duplicates
      // Use the flag from the store which is set by openTab/switchTab
      navigate(targetPath, { replace: !shouldPushHistory })
    }
  }, [activeTabId, location.pathname, navigate, getActiveTab, shouldPushHistory])
}
