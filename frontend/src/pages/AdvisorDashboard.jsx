import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../utils/api'
import Navbar from '../components/Navbar'

const STATUS_LABELS = {
  QUESTIONNAIRE_IN_PROGRESS: 'שאלון בתהליך',
  QUESTIONNAIRE_COMPLETE: 'שאלון הושלם',
  REGISTERED: 'נרשם',
  TIER_SELECTED: 'תכנית נבחרה',
  PERSONAL_DETAILS_COMPLETE: 'פרטים אישיים הושלמו',
  AUTHORIZATION_SIGNED: 'ייפויי כוח נחתמו',
  DOCUMENTS_SUBMITTED: 'מסמכים הוגשו',
  DOCUMENTS_APPROVED: 'מסמכים אושרו',
  PRINCIPAL_APPROVAL_REQUESTED: 'אישור עקרוני נשלח',
  PRINCIPAL_APPROVAL_RECEIVED: 'התקבל אישור עקרוני',
  BANK_SELECTED: 'נבחר בנק',
  MORTGAGE_SIGNED: 'המשכנתא נחתמה',
  COLLATERALS_PENDING: 'בטחונות בהמתנה',
  COLLATERALS_COMPLETE: 'בטחונות הושלמו',
  ACTIVE_MORTGAGE: 'משכנתא פעילה',
}
const TIER_LABELS = { mix_approval: 'אישור מיקס', online_guidance: 'ליווי מקוון', personal_advisor: 'יועץ אישי' }
const DOC_STATUS = { required: ['נדרש', 'text-gray-400'], uploaded: ['הועלה', 'text-blue-400'], approved: ['אושר', 'text-green-400'], rejected: ['נדחה', 'text-red-400'], not_required: ['לא נדרש', 'text-gray-500'] }

const ils = (n) => (n == null ? '—' : '₪' + Number(n).toLocaleString('he-IL'))

function StatusBadge({ status }) {
  const active = status === 'ACTIVE_MORTGAGE'
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${active ? 'bg-green-900/30 border-green-700/40 text-green-300' : 'bg-blue-900/20 border-blue-700/30 text-blue-300'}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function ClientDetail({ token, applicationId, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch(`/api/advisors/clients/${applicationId}`, { token })
      .then((j) => setData(j.application))
      .catch(() => setError('שגיאה בטעינת פרטי הלקוח'))
  }, [token, applicationId])

  if (error) return <p className="text-red-400">{error}</p>
  if (!data) return <p className="text-gray-400">טוען...</p>

  const b = data.borrowers?.[0] || {}
  const field = (label, val) => (
    <div className="mb-2"><span className="text-gray-500 text-xs">{label}: </span><span className="text-white text-sm">{val ?? '—'}</span></div>
  )

  return (
    <div>
      <button onClick={onBack} className="text-blue-400 hover:text-blue-300 text-sm mb-4">→ חזרה לרשימה</button>
      <h2 className="text-xl font-bold text-white mb-1">{data.client_name}</h2>
      <div className="flex items-center gap-3 mb-6">
        <StatusBadge status={data.status} />
        {data.tier && <span className="text-xs text-gray-400">{TIER_LABELS[data.tier]}</span>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5">
          <h3 className="text-white font-semibold text-sm mb-3">פרטי לווה</h3>
          {field('שם מלא', `${b.first_name || ''} ${b.last_name || ''}`.trim())}
          {field('תאריך לידה', b.birth_date)}
          {field('מצב משפחתי', b.marital_status)}
          {field('תעסוקה', b.occupation)}
          {field('הכנסה נטו', ils(b.net_income))}
          {field('טלפון', b.phone)}
        </div>
        <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5">
          <h3 className="text-white font-semibold text-sm mb-3">נתוני משכנתא</h3>
          {field('שווי נכס', ils(data.property_value))}
          {field('הון עצמי', ils(data.equity_amount))}
          {field('סכום הלוואה', ils(data.loan_amount))}
          {field('אחוז מימון', data.financing_ratio != null ? (data.financing_ratio * 100).toFixed(1) + '%' : '—')}
        </div>
      </div>

      <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5 mt-4">
        <h3 className="text-white font-semibold text-sm mb-3">מסמכים ({data.documents?.length || 0})</h3>
        {(!data.documents || data.documents.length === 0) && <p className="text-gray-500 text-sm">אין מסמכים עדיין</p>}
        <div className="space-y-2">
          {data.documents?.map((d) => {
            const [lbl, cls] = DOC_STATUS[d.status] || ['—', 'text-gray-400']
            return (
              <div key={d.id} className="flex items-center justify-between text-sm border-b border-gray-800 pb-1.5">
                <span className="text-gray-200">{d.name}</span>
                <span className={`text-xs ${cls}`}>{lbl}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function ClientsTab({ token, onOpen }) {
  const [clients, setClients] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    apiFetch('/api/advisors/clients', { token })
      .then((j) => setClients(j.clients))
      .catch(() => setError('שגיאה בטעינת הלקוחות'))
  }, [token])

  if (error) return <p className="text-red-400">{error}</p>
  if (!clients) return <p className="text-gray-400">טוען...</p>
  if (clients.length === 0) return <p className="text-gray-400">אין לקוחות משויכים</p>

  return (
    <div className="bg-[#1a2333] rounded-xl border border-gray-800 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-[#0f1623] text-gray-400 text-xs">
          <tr>
            <th className="text-right px-4 py-3">לקוח</th>
            <th className="text-right px-4 py-3">סטטוס</th>
            <th className="text-right px-4 py-3">תכנית</th>
            <th className="text-right px-4 py-3">סכום הלוואה</th>
            <th className="text-right px-4 py-3">מסמכים</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {clients.map((c) => (
            <tr key={c.application_id} className="border-t border-gray-800 hover:bg-[#0f1623]/50">
              <td className="px-4 py-3 text-white font-medium">{c.client_name}</td>
              <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
              <td className="px-4 py-3 text-gray-300">{TIER_LABELS[c.tier] || '—'}</td>
              <td className="px-4 py-3 text-gray-300">{ils(c.loan_amount)}</td>
              <td className="px-4 py-3 text-gray-300">{c.documents_approved}/{c.documents_total}</td>
              <td className="px-4 py-3 text-left">
                <button onClick={() => onOpen(c.application_id)} className="text-blue-400 hover:text-blue-300 text-xs">צפייה ←</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TasksTab({ token }) {
  const [tasks, setTasks] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    apiFetch('/api/advisors/tasks', { token })
      .then((j) => setTasks(j.tasks))
      .catch(() => setError('שגיאה בטעינת המשימות'))
  }, [token])
  useEffect(() => { load() }, [load])

  const toggle = async (t) => {
    await apiFetch(`/api/advisors/tasks/${t.id}`, { token, method: 'PATCH', body: { is_complete: !t.is_complete } })
    load()
  }

  if (error) return <p className="text-red-400">{error}</p>
  if (!tasks) return <p className="text-gray-400">טוען...</p>
  if (tasks.length === 0) return <p className="text-gray-400">אין משימות</p>

  return (
    <div className="space-y-2">
      {tasks.map((t) => (
        <div key={t.id} className={`flex items-center gap-3 bg-[#1a2333] rounded-lg border p-3 ${t.overdue ? 'border-red-700/40' : 'border-gray-800'}`}>
          <input type="checkbox" checked={t.is_complete} onChange={() => toggle(t)} className="w-4 h-4 accent-blue-500" />
          <span className={`flex-1 text-sm ${t.is_complete ? 'text-gray-500 line-through' : 'text-white'}`}>{t.title}</span>
          {t.due_date && <span className={`text-xs ${t.overdue ? 'text-red-400' : 'text-gray-400'}`}>{t.due_date}{t.overdue ? ' · באיחור' : ''}</span>}
        </div>
      ))}
    </div>
  )
}

export default function AdvisorDashboard() {
  const { user } = useAuth()
  const [token, setToken] = useState(null)
  const [tab, setTab] = useState('clients')
  const [openClient, setOpenClient] = useState(null)

  useEffect(() => { if (user) user.getToken().then(setToken) }, [user])
  if (!token) return (
    <div className="min-h-screen bg-[#0f1623]" dir="rtl"><Navbar /><p className="text-gray-400 p-8">טוען...</p></div>
  )

  return (
    <div className="min-h-screen bg-[#0f1623]" dir="rtl">
      <Navbar />
      <main className="max-w-5xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-white mb-6">לוח יועץ</h1>

        {openClient ? (
          <ClientDetail token={token} applicationId={openClient} onBack={() => setOpenClient(null)} />
        ) : (
          <>
            <div className="flex gap-2 mb-6 border-b border-gray-800">
              {[['clients', 'הלקוחות שלי'], ['tasks', 'משימות']].map(([id, label]) => (
                <button key={id} onClick={() => setTab(id)}
                  className={`px-4 py-2 text-sm transition-colors ${tab === id ? 'text-blue-400 border-b-2 border-blue-400 -mb-px' : 'text-gray-400 hover:text-white'}`}>
                  {label}
                </button>
              ))}
            </div>
            {tab === 'clients' ? <ClientsTab token={token} onOpen={setOpenClient} /> : <TasksTab token={token} />}
          </>
        )}
      </main>
    </div>
  )
}
