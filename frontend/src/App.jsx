import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'

// Public pages (implemented in Phase 2)
import Home from './pages/Home'
import Login from './pages/Login'

// Placeholder pages for future phases
const Wizard = () => <div>Wizard — Phase 2</div>
const Clocks = () => <div>Clocks — Phase 2</div>
const TierSelection = () => <div>Tier Selection — Phase 2</div>
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
      <Route path="/wizard" element={<Wizard />} />
      <Route path="/clocks" element={<Clocks />} />
      <Route path="/tiers" element={<TierSelection />} />

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
