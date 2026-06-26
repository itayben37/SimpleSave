import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import Navbar from '../../components/Navbar'
import MixManager from './MixManager'
import './admin.css'

const TABS = [
  { to: '/admin/mix-manager', label: 'ניהול תמהיל' },
  { to: '/admin/interest-rates', label: 'ריביות שוק' },
  { to: '/admin/parameters', label: 'פרמטרים' },
  { to: '/admin/clients', label: 'לקוחות/לידים' },
  { to: '/admin/advisors', label: 'יועצים' },
]

function Placeholder({ title }) {
  return (
    <div className="admin-placeholder">
      <div className="emoji">🛠️</div>
      <h2>{title}</h2>
      <p>מסך זה ייבנה בשלב הבא. כרגע פעיל מסך "ניהול תמהיל — שעונים".</p>
    </div>
  )
}

export default function AdminShell() {
  return (
    <div className="admin-shell" dir="rtl">
      <Navbar />
      <nav className="admin-tabs">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to}
            className={({ isActive }) => `admin-tab ${isActive ? 'active' : ''}`}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="admin-content">
        <Routes>
          <Route index element={<Navigate to="/admin/mix-manager" replace />} />
          <Route path="mix-manager" element={<MixManager />} />
          <Route path="interest-rates" element={<Placeholder title="ריביות שוק" />} />
          <Route path="parameters" element={<Placeholder title="פרמטרים" />} />
          <Route path="clients" element={<Placeholder title="לקוחות / לידים" />} />
          <Route path="advisors" element={<Placeholder title="ניהול יועצים" />} />
          <Route path="*" element={<Navigate to="/admin/mix-manager" replace />} />
        </Routes>
      </div>
    </div>
  )
}
