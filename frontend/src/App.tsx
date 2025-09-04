import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ProjectDashboard from './views/ProjectDashboard'
import ProjectDetail from './views/ProjectDetail'
import TaskDetail from './views/TaskDetail'
import Settings from './views/Settings'
import './App.css'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<ProjectDashboard />} />
          <Route path="/projects" element={<ProjectDashboard />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/tasks/:id" element={<TaskDetail />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App