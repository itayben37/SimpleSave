import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'

import Home from './pages/Home'
import Login from './pages/Login'
import Wizard from './pages/Wizard'
import Clocks from './pages/Clocks'
import TierSelection from './pages/TierSelection'

// Placeholder pages for future phases
const PersonalArea = () => <div>Personal Area — Phase 3</div>
const AdminDashboard = () => <div>Admin Dashboard — Phase 5</div>
const AdvisorDashboard = () => <div>Advisor Dashboard — Phase 4</div>

function RequireAuth({ children, roles }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">טוען...</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />

      {/* Phase 2 — wizard + results */}
      <Route path="/wizard" element={<RequireAuth roles={['client', 'admin', 'advisor']}><Wizard /></RequireAuth>} />
      <Route path="/applications/:applicationId/clocks" element={<RequireAuth><Clocks /></RequireAuth>} />
      <Route path="/applications/:applicationId/tiers" element={<RequireAuth><TierSelection /></RequireAuth>} />

      {/* Client */}
      <Route
        path="/personal/*"
        element={
          <RequireAuth roles={['client']}>
            <PersonalArea />
          </RequireAuth>
        }
      />

      {/* Advisor */}
      <Route
        path="/advisor/*"
        element={
          <RequireAuth roles={['advisor']}>
            <AdvisorDashboard />
          </RequireAuth>
        }
      />

      {/* Admin */}
      <Route
        path="/admin/*"
        element={
          <RequireAuth roles={['admin']}>
            <AdminDashboard />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
