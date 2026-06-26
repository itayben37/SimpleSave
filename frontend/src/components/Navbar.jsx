import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const ROLE_LABELS = { client: 'לקוח', advisor: 'יועץ', admin: 'מנהל' }

export default function Navbar() {
  const { user, bypass, setDevRole } = useAuth()
  const role = user?.role

  const personalHref = role === 'admin' ? '/admin' : role === 'advisor' ? '/advisor' : '/personal'
  // Show "New Mortgage" for end-users (clients) and unauthenticated guests
  const showNewMortgage = !role || role === 'client'

  return (
    <header dir="rtl" className="bg-[#0f1623] border-b border-gray-800 px-6 py-3 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-xl font-bold text-blue-400 hover:text-blue-300 transition-colors">
          SimpleSave
        </Link>

        {/* Dev-only role switcher — lets you browse every role without re-login */}
        {bypass && (
          <div className="flex items-center gap-2 bg-amber-900/30 border border-amber-700/40 rounded-lg px-2 py-1">
            <span className="text-amber-300 text-[11px] font-medium">מצב בדיקה</span>
            <select
              value={role}
              onChange={(e) => setDevRole(e.target.value)}
              className="bg-[#0f1623] text-amber-200 text-xs border border-amber-700/40 rounded px-1.5 py-0.5 focus:outline-none"
              title="החלף תפקיד (מצב פיתוח בלבד)"
            >
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      <nav className="flex items-center gap-6 text-sm">
        <Link to="/" className="text-gray-300 hover:text-white transition-colors">בית</Link>
        {showNewMortgage && (
          <Link to="/wizard" className="text-gray-300 hover:text-white transition-colors">משכנתא חדשה</Link>
        )}
        <Link to={personalHref} className="text-gray-300 hover:text-white transition-colors">אזור אישי</Link>
        <a href="#about" className="text-gray-300 hover:text-white transition-colors">אודות</a>

        {bypass ? (
          <span className="text-gray-400 text-xs">
            {user?.full_name} · <span className="text-blue-400">{ROLE_LABELS[role]}</span>
          </span>
        ) : (
          <Link
            to="/login"
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded-lg transition-colors font-medium"
          >
            הרשמה / כניסה
          </Link>
        )}
      </nav>
    </header>
  )
}
