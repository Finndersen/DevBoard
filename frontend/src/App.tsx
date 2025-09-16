import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ProjectDashboard from './views/ProjectDashboard'
import ProjectDetail from './views/ProjectDetail'
import TaskDetail from './views/TaskDetail'
import Codebases from './views/Codebases'
import Settings from './views/Settings'
import { DarkModeProvider } from './contexts/DarkModeContext'
import { ApprovalsProvider } from './contexts/ApprovalsContext'
import './App.css'

function App() {
  return (
    <DarkModeProvider>
      <ApprovalsProvider>
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<ProjectDashboard />} />
              <Route path="/projects" element={<ProjectDashboard />} />
              <Route path="/projects/:id" element={<ProjectDetail />} />
              <Route path="/tasks/:id" element={<TaskDetail />} />
              <Route path="/codebases" element={<Codebases />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </Router>
      </ApprovalsProvider>
    </DarkModeProvider>
  )
}

export default App