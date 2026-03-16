import { useEffect } from 'react'
import { useUIStore } from '../stores/uiStore'
import { useDataStore } from '../stores/dataStore'

export function useViewTitle(type: 'project' | 'task' | 'codebase', entityId: string | undefined) {
  const cachedViews = useUIStore(state => state.cachedViews)
  const { updateView } = useUIStore()
  const { getProject, getTask, getCodebase } = useDataStore()

  useEffect(() => {
    if (!entityId) return

    const view = cachedViews.find(t => t.type === type && t.entityId === entityId)
    if (!view) return

    let entity
    let title: string

    switch (type) {
      case 'project':
        entity = getProject(entityId)
        if (entity) {
          const maxLength = 30
          title = entity.name.length > maxLength ? entity.name.slice(0, maxLength - 3) + '...' : entity.name
          if (view.title !== title) {
            updateView(view.id, { title })
          }
        }
        break

      case 'task':
        entity = getTask(entityId)
        if (entity) {
          const maxLength = 30
          title = entity.title.length > maxLength ? entity.title.slice(0, maxLength - 3) + '...' : entity.title
          if (view.title !== title) {
            updateView(view.id, { title })
          }
        }
        break

      case 'codebase':
        entity = getCodebase(entityId)
        if (entity) {
          const maxLength = 30
          title = entity.name.length > maxLength ? entity.name.slice(0, maxLength - 3) + '...' : entity.name
          if (view.title !== title) {
            updateView(view.id, { title })
          }
        }
        break
    }
  }, [type, entityId, cachedViews, updateView, getProject, getTask, getCodebase])
}
