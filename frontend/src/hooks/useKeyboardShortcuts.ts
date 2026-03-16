import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUIStore } from '../stores/uiStore'

/**
 * Global keyboard shortcuts hook
 * Should be called at the app level to enable keyboard shortcuts
 */
export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const { toggleNavigationCompactMode, navigateTo } = useUIStore()

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
      const modifierKey = isMac ? event.metaKey : event.ctrlKey

      // Ignore shortcuts when typing in input fields
      const target = event.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        // Only allow Cmd/Ctrl shortcuts, not character keys
        if (!modifierKey) {
          return
        }
      }

      // Cmd/Ctrl + B: Toggle compact mode
      if (modifierKey && event.key === 'b') {
        event.preventDefault()
        toggleNavigationCompactMode()
        return
      }

      // Cmd/Ctrl + T: Navigate to home
      if (modifierKey && event.key === 't') {
        event.preventDefault()
        navigateTo({
          type: 'home',
          entityId: 'main',
          title: 'Home'
        })
        navigate('/')
        return
      }

      // Cmd/Ctrl + Shift + N: Focus notifications (not implemented yet, would need to trigger open)
      if (modifierKey && event.shiftKey && event.key === 'N') {
        event.preventDefault()
        // This would need a state in NotificationsPanel to be controllable
        console.log('Toggle notifications panel')
        return
      }

      // Escape: Close any open modals/menus (handled by components individually)
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [toggleNavigationCompactMode, navigateTo, navigate])
}
