import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../utils/api'
import { tabLocked, TEST_MODE } from '../utils/testMode'
import Navbar from '../components/Navbar'

import { PersonalDetailsTab } from './personal/PersonalDetailsTab'
import { MortgageDetailsTab } from './personal/MortgageDetailsTab'
import { DocumentsTab } from './personal/DocumentsTab'
import { PrincipalApprovalTab, CollateralsTab, MessagesTab, MyMortgageTab } from './personal/OtherTabs'

// Re-exported for the unit test that renders the personal-details tab in isolation.
export { PersonalDetailsTab }

const STATUS_LABELS = {
  QUESTIONNAIRE_IN_PROGRESS: 'שאלון בתהליך',
  QUESTIONNAIRE_COMPLETE: 'שאלון הושלם',
  REGISTERED: 'נרשמת בהצלחה',
  TIER_SELECTED: 'תכנית נבחרה',
  PERSONAL_DETAILS_COMPLETE: 'פרטים אישיים הושלמו',
  AUTHORIZATION_SIGNED: 'ייפויי כוח נחתמו',
  DOCUMENTS_SUBMITTED: 'מסמכים הוגשו',
  DOCUMENTS_APPROVED: 'מסמכים אושרו',
  PRINCIPAL_APPROVAL_REQUESTED: 'אישור עקרוני נשלח לבנקים',
  PRINCIPAL_APPROVAL_RECEIVED: 'התקבל אישור עקרוני',
  BANK_SELECTED: 'נבחר בנק',
  MORTGAGE_SIGNED: 'המשכנתא נחתמה',
  ACTIVE_MORTGAGE: 'משכנתא פעילה',
}
const TIER_LABELS = { mix_approval: 'אישור מיקס', online_guidance: 'ליווי מקוון', personal_advisor: 'יועץ אישי' }

const TABS = [
  { id: 'personal', label: 'נתונים אישיים' },
  { id: 'mortgage', label: 'נתוני משכנתא' },
  { id: 'documents', label: 'מסמכים', lockType: 'tier' },
  { id: 'principal', label: 'אישור עקרוני', lockType: 'lifecycle' },
  { id: 'collaterals', label: 'בטחונות', lockType: 'lifecycle' },
  { id: 'messages', label: 'הודעות', lockType: 'tier' },
  { id: 'my_mortgage', label: 'המשכנתא שלי', lockType: 'lifecycle' },
]

function isTabLocked(tabId, { tier, status }) {
  const tierSet = !!tier
  const map = {
    documents: tierSet,
    principal: ['DOCUMENTS_APPROVED', 'PRINCIPAL_APPROVAL_REQUESTED', 'PRINCIPAL_APPROVAL_RECEIVED', 'BANK_SELECTED', 'MORTGAGE_SIGNED', 'ACTIVE_MORTGAGE'].includes(status),
    collaterals: ['MORTGAGE_SIGNED', 'COLLATERALS_PENDING', 'COLLATERALS_COMPLETE', 'ACTIVE_MORTGAGE'].includes(status),
    messages: tierSet && (tier === 'online_guidance' || tier === 'personal_advisor'),
    my_mortgage: status === 'ACTIVE_MORTGAGE',
  }
  return !(map[tabId] ?? true)
}

function LockOverlay({ lockType }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center p-8 mt-8">
      <div className="text-5xl mb-4 opacity-40">🔒</div>
      {lockType === 'tier' ? (
        <>
          <p className="text-gray-300 mb-1 font-medium">בחרו תכנית שירות כדי לגשת לתכונה זו</p>
          <Link to="/applications/demo/tiers" className="mt-3 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-lg text-sm font-medium transition">בחר תכנית</Link>
        </>
      ) : (
        <p className="text-gray-300 font-medium">השלימו את השלב הקודם כדי לפתוח תכונה זו</p>
      )}
    </div>
  )
}

export default function PersonalArea() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('personal')
  const [app, setApp] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [token, setToken] = useState(null)

  const loadApp = useCallback(async () => {
    if (!user) return
    const t = await user.getToken()
    setToken(t)
    try {
      const j = await apiFetch('/api/applications/me', { token: t })
      setApp(j.application)
    } catch {
      setError('שגיאה בטעינת הנתונים')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { loadApp() }, [loadApp])

  if (loading) return <Shell><p className="text-gray-400 p-8">טוען...</p></Shell>
  if (error) return <Shell><p className="text-red-400 p-8">{error}</p></Shell>
  if (!app) return (
    <Shell>
      <div className="text-center py-20">
        <p className="text-gray-300 text-lg mb-2">עדיין לא התחלת בקשת משכנתא</p>
        <p className="text-gray-500 text-sm mb-6">מלא את השאלון כדי לראות את שעוני העלות שלך</p>
        <Link to="/wizard" className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-medium transition">התחל שאלון</Link>
      </div>
    </Shell>
  )

  const role = user?.role
  const locked = (tabId) => {
    const tab = TABS.find((t) => t.id === tabId)
    if (!tab?.lockType) return false
    return tabLocked(isTabLocked(tabId, { tier: app.tier, status: app.status }))
  }

  function renderContent() {
    if (locked(activeTab)) {
      return <LockOverlay lockType={TABS.find((t) => t.id === activeTab).lockType} />
    }
    switch (activeTab) {
      case 'personal': return <PersonalDetailsTab app={app} token={token} onSaved={loadApp} />
      case 'mortgage': return <MortgageDetailsTab app={app} token={token} onSaved={loadApp} />
      case 'documents': return <DocumentsTab app={app} token={token} role={role} onSaved={loadApp} />
      case 'principal': return <PrincipalApprovalTab app={app} token={token} />
      case 'collaterals': return <CollateralsTab app={app} token={token} />
      case 'messages': return <MessagesTab app={app} token={token} />
      case 'my_mortgage': return <MyMortgageTab app={app} token={token} />
      default: return null
    }
  }

  const borrowerName = app.borrowers[0]?.first_name
    ? `${app.borrowers[0].first_name} ${app.borrowers[0].last_name || ''}`
    : 'לקוח חדש'

  return (
    <div className="min-h-screen bg-[#0f1623] flex flex-col" dir="rtl">
      <Navbar />
      {TEST_MODE && (
        <div className="bg-amber-900/30 border-b border-amber-700/40 text-amber-200 text-xs px-6 py-1.5 text-center flex-shrink-0">
          מצב בדיקה פעיל — כל הלשוניות פתוחות והוולידציה מנוטרלת (VITE_TEST_MODE=true)
        </div>
      )}
      <div className="bg-[#1a2333] border-b border-gray-800 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-white font-semibold">{borrowerName}</span>
          <span className="bg-blue-900/60 text-blue-200 text-xs px-2 py-0.5 rounded-full border border-blue-800">
            {STATUS_LABELS[app.status] || app.status}
          </span>
          <span className="text-gray-600 text-xs">מספר בקשה: #{app.application_id.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-4">
          {app.advisor_name
            ? <span className="text-sm text-gray-400">יועץ: <span className="text-white">{app.advisor_name}</span></span>
            : <span className="text-sm text-gray-600">יועץ יוקצה בקרוב</span>}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 bg-[#1a2333] border-l border-gray-800 flex flex-col flex-shrink-0">
          <nav className="flex-1 py-3 overflow-y-auto">
            {TABS.map((tab) => {
              const isLocked = locked(tab.id)
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full text-right px-5 py-3 flex items-center justify-between text-sm transition-colors
                    ${isActive ? 'bg-blue-600/20 text-blue-300 border-l-2 border-blue-500' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'}
                    ${isLocked ? 'opacity-50' : ''}`}
                >
                  <span>{tab.label}</span>
                  {isLocked && <span className="text-gray-700 text-xs">🔒</span>}
                </button>
              )
            })}
          </nav>
          <div className="p-4 border-t border-gray-800">
            <p className="text-gray-600 text-xs mb-2">תכנית שירות</p>
            {app.tier
              ? <span className="text-blue-400 text-sm">{TIER_LABELS[app.tier]}</span>
              : <Link to={`/applications/${app.application_id}/tiers`} className="block text-center text-xs bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg transition">בחר תכנית</Link>}
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto p-6 bg-[#0f1623]">
          <div className="max-w-3xl">{renderContent()}</div>
        </main>
      </div>
    </div>
  )
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[#0f1623]" dir="rtl">
      <Navbar />
      <div className="max-w-3xl mx-auto">{children}</div>
    </div>
  )
}
