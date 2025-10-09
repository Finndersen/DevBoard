import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'
import { useDataStore } from '../stores/dataStore'

/**
 * Hook to automatically update tab title based on entity data
 * Should be called from entity detail views (ProjectDetail, TaskDetail, etc.)
 */
export function useTabTitle(type: 'project' | 'task' | 'codebase', entityId: string | undefined) {
  const tabs = useUIStore(state => state.tabs)
  const { updateTab } = useUIStore()
  const { getProject, getTask, getCodebase } = useDataStore()

  useEffect(() => {
    if (!entityId) return

    // Find tab by entity type and ID (not just active tab)
    const tab = tabs.find(t => t.type === type && t.entityId === entityId)
    if (!tab) return

    // Get entity data and update tab title
    let entity
    let title: string

    switch (type) {
      case 'project':
        entity = getProject(entityId)
        if (entity) {
          // Truncate to max 30 characters
          const maxLength = 30
          title = entity.name.length > maxLength ? entity.name.slice(0, maxLength - 3) + '...' : entity.name
          if (tab.title !== title) {
            updateTab(tab.id, { title })
          }
        }
        break

      case 'task':
        entity = getTask(entityId)
        if (entity) {
          // Truncate to max 30 characters
          const maxLength = 30
          title = entity.title.length > maxLength ? entity.title.slice(0, maxLength - 3) + '...' : entity.title
          if (tab.title !== title) {
            updateTab(tab.id, { title })
          }
        }
        break

      case 'codebase':
        entity = getCodebase(entityId)
        if (entity) {
          // Truncate to max 30 characters
          const maxLength = 30
          title = entity.name.length > maxLength ? entity.name.slice(0, maxLength - 3) + '...' : entity.name
          if (tab.title !== title) {
            updateTab(tab.id, { title })
          }
        }
        break
    }
  }, [type, entityId, tabs, updateTab, getProject, getTask, getCodebase])
}
