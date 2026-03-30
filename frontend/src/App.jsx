import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import SampleList from './pages/SampleList'
import SampleDetail from './pages/SampleDetail'
import CaseList from './pages/CaseList'
import CaseDetail from './pages/CaseDetail'
import Admin from './pages/Admin'
import Layout from './components/Layout'

function ProtectedRoute({ children }) {
  const { token } = useAuth()
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/cases" replace />} />
        <Route path="cases" element={<CaseList />} />
        <Route path="cases/:caseId" element={<CaseDetail />} />
        <Route path="samples" element={<SampleList />} />
        <Route path="samples/:sampleId" element={<SampleDetail />} />
        <Route path="admin" element={<Admin />} />
      </Route>
    </Routes>
  )
}