import { BrowserRouter as Router } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import TabContentContainer from './components/layout/TabContentContainer'
import { DarkModeProvider } from './contexts/DarkModeContext'
import { PendingMessagesProvider } from './contexts/PendingMessagesContext'
import { useURLSync } from './hooks/useURLSync'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import './App.css'

function AppContent() {
  // Synchronize URL with tab state
  useURLSync()

  // Enable global keyboard shortcuts
  useKeyboardShortcuts()

  return <TabContentContainer />
}

function App() {
  return (
    <DarkModeProvider>
      <PendingMessagesProvider>
        <Router>
          <AppShell>
            <AppContent />
          </AppShell>
        </Router>
      </PendingMessagesProvider>
    </DarkModeProvider>
  )
}

export default App