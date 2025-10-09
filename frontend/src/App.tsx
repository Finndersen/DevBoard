import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import Home from './views/Home'
import ProjectDetail from './views/ProjectDetail'
import TaskDetail from './views/TaskDetail'
import Settings from './views/Settings'
import { DarkModeProvider } from './contexts/DarkModeContext'
import { ApprovalsProvider } from './contexts/ApprovalsContext'
import { PendingMessagesProvider } from './contexts/PendingMessagesContext'
import { useURLSync } from './hooks/useURLSync'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import './App.css'

function AppContent() {
  // Synchronize URL with tab state
  useURLSync()

  // Enable global keyboard shortcuts
  useKeyboardShortcuts()

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      {/* Redirect old routes to home */}
      <Route path="/projects" element={<Navigate to="/" replace />} />
      <Route path="/codebases" element={<Navigate to="/" replace />} />
      {/* Entity detail routes */}
      <Route path="/projects/:id" element={<ProjectDetail />} />
      <Route path="/tasks/:id" element={<TaskDetail />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
  )
}

function App() {
  return (
    <DarkModeProvider>
      <ApprovalsProvider>
        <PendingMessagesProvider>
          <Router>
            <AppShell>
              <AppContent />
            </AppShell>
          </Router>
        </PendingMessagesProvider>
      </ApprovalsProvider>
    </DarkModeProvider>
  )
}

export default App