import { BrowserRouter as Router } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import { DarkModeProvider } from './contexts/DarkModeContext'
import { PendingMessagesProvider } from './contexts/PendingMessagesContext'
import './App.css'

function App() {
  return (
    <DarkModeProvider>
      <PendingMessagesProvider>
        <Router>
          <AppShell />
        </Router>
      </PendingMessagesProvider>
    </DarkModeProvider>
  )
}

export default App
