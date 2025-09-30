import { useState, useCallback } from 'react'

/**
 * Custom hook for managing modal state
 * Eliminates boilerplate for modal open/close state management
 */
export function useModal(initialState = false) {
  const [isOpen, setIsOpen] = useState(initialState)
  
  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])
  const toggle = useCallback(() => setIsOpen(prev => !prev), [])
  
  return { 
    isOpen, 
    open, 
    close, 
    toggle 
  }
}