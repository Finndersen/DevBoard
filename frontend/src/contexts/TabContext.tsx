import { createContext, useContext, type ReactNode } from 'react'

interface TabContextType {
  tabId: string
}

const TabContext = createContext<TabContextType | undefined>(undefined)

// eslint-disable-next-line react-refresh/only-export-components
export function useTabContext() {
  const context = useContext(TabContext)
  if (context === undefined) {
    throw new Error('useTabContext must be used within a TabContextProvider')
  }
  return context
}

interface TabContextProviderProps {
  tabId: string
  children: ReactNode
}

export function TabContextProvider({ tabId, children }: TabContextProviderProps) {
  return (
    <TabContext.Provider value={{ tabId }}>
      {children}
    </TabContext.Provider>
  )
}
