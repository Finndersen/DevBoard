import { createContext, useContext, type ReactNode } from 'react'

import type { ViewType } from '../stores/uiStore'

interface ViewContextType {
  viewId: string
  viewType: ViewType
  entityId: string
}

const ViewContext = createContext<ViewContextType | undefined>(undefined)

// eslint-disable-next-line react-refresh/only-export-components
export function useViewContext() {
  const context = useContext(ViewContext)
  if (context === undefined) {
    throw new Error('useViewContext must be used within a ViewContextProvider')
  }
  return context
}

interface ViewContextProviderProps {
  viewId: string
  viewType: ViewType
  entityId: string
  children: ReactNode
}

export function ViewContextProvider({ viewId, viewType, entityId, children }: ViewContextProviderProps) {
  return (
    <ViewContext.Provider value={{ viewId, viewType, entityId }}>
      {children}
    </ViewContext.Provider>
  )
}
