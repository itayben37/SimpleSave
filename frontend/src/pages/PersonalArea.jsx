import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../utils/api'
import Navbar from '../components/Navbar'

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

// ── Auto-save hook ────────────────────────────────────────────────────────────
// Accumulates changed fields and flushes them via saveFn after a debounce.
function useAutoSave(saveFn, delay = 700) {
  const [status, setStatus] = useState('idle') // idle | saving | saved | error
  const pending = useRef({})
  const timer = useRef(null)

  const flush = useCallback(async () => {
    const fields = pending.current
    pending.current = {}
    if (Object.keys(fields).length === 0) return
    setStatus('saving')
    try {
      await saveFn(fields)
      setStatus('saved')
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 1500)
    } catch {
      setStatus('error')
    }
  }, [saveFn])

  const schedule = useCallback((field, value) => {
    pending.current[field] = value
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(flush, delay)
  }, [flush, delay])

  return { schedule, status }
}

function SaveIndicator({ status }) {
  const map = {
    saving: ['שומר...', 'text-gray-400'],
    saved: ['נשמר ✓', 'text-green-400'],
    error: ['שגיאת שמירה', 'text-red-400'],
    idle: ['', ''],
  }
  const [label, cls] = map[status] || map.idle
  return <span className={`text-xs ${cls}`}>{label}</span>
}

// ── Editable field ────────────────────────────────────────────────────────────
const SELECT_OPTIONS = {
  gender: [['male', 'זכר'], ['female', 'נקבה']],
  marital_status: [['single', 'רווק/ה'], ['married', 'נשוי/אה'], ['divorced', 'גרוש/ה'], ['widowed', 'אלמן/ה']],
  education: [['high_school', 'תיכונית'], ['post_secondary', 'על-תיכונית'], ['bachelor', 'תואר ראשון'], ['master', 'תואר שני']],
  employment_status: [['employee', 'שכיר'], ['self_employed', 'עצמאי'], ['controlling_shareholder', 'בעל שליטה']],
}
const BOOL_OPTIONS = [['true', 'כן'], ['false', 'לא']]

function EditableField({ label, name, kind, value, onChange }) {
  const base = 'w-full bg-[#0f1623] border border-gray-700 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none'
  let control
  if (kind === 'select') {
    control = (
      <select className={base} value={value ?? ''} onChange={(e) => onChange(name, e.target.value || null)}>
        <option value="">-- בחר --</option>
        {SELECT_OPTIONS[name].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    )
  } else if (kind === 'bool') {
    control = (
      <select className={base} value={value === null || value === undefined ? '' : String(value)} onChange={(e) => onChange(name, e.target.value === '' ? null : e.target.value === 'true')}>
        <option value="">-- בחר --</option>
        {BOOL_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    )
  } else {
    control = (
      <input
        type={kind === 'number' ? 'number' : kind === 'date' ? 'date' : 'text'}
        className={base}
        value={value ?? ''}
        onChange={(e) => onChange(name, e.target.value === '' ? null : e.target.value)}
      />
    )
  }
  return (
    <div className="mb-3">
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {control}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5 mb-4">
      <h3 className="text-white font-semibold text-sm mb-4">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">{children}</div>
    </div>
  )
}

// ── Personal details tab ──────────────────────────────────────────────────────
function PersonalDetailsTab({ app, token, onSaved }) {
  const borrower = app.borrowers[0]
  const [b, setB] = useState(borrower || {})

  const save = useCallback(async (fields) => {
    const updated = await apiFetch(`/api/applications/${app.application_id}/borrowers/${b.id}`, {
      token, method: 'PATCH', body: { fields },
    })
    onSaved && onSaved()
    return updated
  }, [app.application_id, b.id, token, onSaved])

  const { schedule, status } = useAutoSave(save)
  const change = (name, value) => {
    setB((prev) => ({ ...prev, [name]: value }))
    schedule(name, value)
  }

  if (!borrower) {
    return <p className="text-gray-400">לא נמצאו פרטי לווה.</p>
  }

  const F = (label, name, kind = 'text') => (
    <EditableField label={label} name={name} kind={kind} value={b[name]} onChange={change} />
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold text-lg">פרטים אישיים</h2>
        <SaveIndicator status={status} />
      </div>

      <Section title="פרטים בסיסיים">
        {F('שם פרטי', 'first_name')}
        {F('שם משפחה', 'last_name')}
        {F('מין', 'gender', 'select')}
        {F('תאריך לידה', 'birth_date', 'date')}
        {F('מצב משפחתי', 'marital_status', 'select')}
        {F('מספר ילדים', 'num_children', 'number')}
        {F('השכלה', 'education', 'select')}
        {F('תאריך נישואים', 'wedding_date', 'date')}
      </Section>

      <Section title="פרטי קשר וכתובת">
        {F('טלפון', 'phone')}
        {F('אימייל', 'email')}
        {F('עיר', 'address_city')}
        {F('רחוב', 'address_street')}
        {F('מספר בית', 'address_number')}
        {F('דירה', 'address_apartment')}
      </Section>

      <Section title="תעסוקה והכנסה">
        {F('סטטוס עיסוק', 'employment_status', 'select')}
        {F('מקצוע', 'occupation')}
        {F('מקום עבודה', 'employer_name')}
        {F('עיר מקום עבודה', 'employer_city')}
        {F('תאריך תחילת עבודה', 'employment_start_date', 'date')}
        {F('הכנסה נטו חודשית (₪)', 'net_income', 'number')}
      </Section>

      <Section title="רגולציה ובריאות">
        {F('אזרחות נוספת', 'has_additional_citizenship', 'bool')}
        {F('חבות מס בחו"ל', 'has_foreign_tax_obligation', 'bool')}
        {F('קרבה לאיש ציבור', 'is_politically_exposed', 'bool')}
        {F('מצב בריאותי תקין', 'has_health_issues', 'bool')}
        {F('בעיות אשראי (7 שנים)', 'has_credit_issues', 'bool')}
        {F('מעשן/ת', 'is_smoker', 'bool')}
      </Section>

      <Section title="זכאות דירה ראשונה">
        {F('חודשי שירות צבאי', 'military_service_months', 'number')}
        {F('אחים בארץ', 'num_siblings_in_country', 'number')}
        {F('ילדים מתחת לגיל 18', 'children_under_18', 'number')}
      </Section>
    </div>
  )
}

// ── Mortgage details tab ──────────────────────────────────────────────────────
const LOAN_PURPOSE_OPTIONS = [
  ['primary_residence', 'דירה ראשונה'], ['additional_property', 'דירה נוספת'],
  ['all_purpose', 'כל מטרה'], ['home_improvement', 'שיפוץ'],
]

function MortgageDetailsTab({ app, token, onSaved }) {
  const [m, setM] = useState({
    loan_purpose: app.loan_purpose, property_value: app.property_value,
    loan_amount: app.loan_amount, equity: app.equity_amount,
  })
  const [ratio, setRatio] = useState(app.financing_ratio)

  const save = useCallback(async (fields) => {
    await apiFetch(`/api/applications/${app.application_id}`, {
      token, method: 'PATCH', body: { wizard_data: fields },
    })
    const refreshed = await apiFetch(`/api/applications/${app.application_id}`, { token })
    setRatio(refreshed.financing_ratio)
    onSaved && onSaved()
  }, [app.application_id, token, onSaved])

  const { schedule, status } = useAutoSave(save)
  const change = (name, value) => {
    setM((prev) => ({ ...prev, [name]: value }))
    schedule(name, value)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold text-lg">נתוני משכנתא</h2>
        <SaveIndicator status={status} />
      </div>
      <Section title="פרטי ההלוואה">
        <EditableField label="מטרת ההלוואה" name="loan_purpose" kind="select" value={m.loan_purpose} onChange={change} />
        <EditableField label="ערך הנכס (₪)" name="property_value" kind="number" value={m.property_value} onChange={change} />
        <EditableField label="סכום ההלוואה (₪)" name="loan_amount" kind="number" value={m.loan_amount} onChange={change} />
        <EditableField label="הון עצמי (₪)" name="equity" kind="number" value={m.equity} onChange={change} />
      </Section>
      <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5">
        <div className="flex justify-between items-center">
          <span className="text-gray-400 text-sm">אחוז מימון</span>
          <span className="text-white font-semibold">{ratio != null ? `${(ratio * 100).toFixed(1)}%` : '—'}</span>
        </div>
      </div>
    </div>
  )
}

// Override the select option source for loan_purpose
SELECT_OPTIONS.loan_purpose = LOAN_PURPOSE_OPTIONS

// ── Documents tab ─────────────────────────────────────────────────────────────
const DOC_STATUS = {
  required: ['נדרש', 'bg-gray-700 text-gray-300'],
  uploaded: ['הועלה — בבדיקה', 'bg-blue-900/40 text-blue-300'],
  approved: ['אושר', 'bg-green-900/40 text-green-300'],
  rejected: ['נדחה — נדרש תיקון', 'bg-red-900/40 text-red-300'],
  not_required: ['לא נדרש', 'bg-gray-800 text-gray-500'],
}

function DocumentsTab({ app, token }) {
  const [docs, setDocs] = useState([])
  const [summary, setSummary] = useState({ blocking_total: 0, blocking_approved: 0 })
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    apiFetch(`/api/documents/application/${app.application_id}`, { token })
      .then((j) => {
        setDocs(j.documents)
        setSummary({ blocking_total: j.blocking_total, blocking_approved: j.blocking_approved })
      })
      .finally(() => setLoading(false))
  }, [app.application_id, token])

  useEffect(() => { load() }, [load])

  const upload = async (doc) => {
    setBusyId(doc.id)
    try {
      await apiFetch(`/api/documents/${doc.id}`, {
        token, method: 'PATCH',
        body: { action: 'upload', file_name: `${doc.name}.pdf` },
      })
      load()
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <p className="text-gray-400">טוען מסמכים...</p>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white font-semibold text-lg">מסמכים נדרשים</h2>
        <span className="text-xs text-gray-500">{summary.blocking_approved} מתוך {summary.blocking_total} מסמכי חובה אושרו</span>
      </div>
      <div className="space-y-3">
        {docs.map((doc) => {
          const [label, cls] = DOC_STATUS[doc.status] || DOC_STATUS.required
          return (
            <div key={doc.id} className="bg-[#1a2333] rounded-xl border border-gray-800 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full ${doc.required_for_principal_approval ? 'bg-yellow-500' : 'bg-gray-600'}`} />
                <div>
                  <span className="text-white text-sm">{doc.name}</span>
                  {doc.required_for_principal_approval && (
                    <span className="text-xs text-yellow-500/70 bg-yellow-900/20 px-2 py-0.5 rounded mr-2">חובה לאישור עקרוני</span>
                  )}
                  {doc.rejection_reason && <p className="text-red-400 text-xs mt-1">{doc.rejection_reason}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-1 rounded ${cls}`}>{label}</span>
                {doc.status !== 'approved' && (
                  <button
                    onClick={() => upload(doc)}
                    disabled={busyId === doc.id}
                    className="text-xs bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded transition disabled:opacity-50"
                  >
                    {busyId === doc.id ? '...' : doc.status === 'required' ? 'העלה' : 'העלה מחדש'}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
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

// ── Main component ────────────────────────────────────────────────────────────
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

  const locked = (tabId) => {
    const tab = TABS.find((t) => t.id === tabId)
    if (!tab?.lockType) return false
    return isTabLocked(tabId, { tier: app.tier, status: app.status })
  }

  function renderContent() {
    if (locked(activeTab)) {
      return <LockOverlay lockType={TABS.find((t) => t.id === activeTab).lockType} />
    }
    switch (activeTab) {
      case 'personal': return <PersonalDetailsTab app={app} token={token} onSaved={loadApp} />
      case 'mortgage': return <MortgageDetailsTab app={app} token={token} onSaved={loadApp} />
      case 'documents': return <DocumentsTab app={app} token={token} />
      default: return (
        <div className="text-center py-20 text-gray-600">
          <p className="text-2xl mb-2">🚧</p>
          <p>עמוד זה יפותח בשלב הבא</p>
        </div>
      )
    }
  }

  const borrowerName = app.borrowers[0]?.first_name
    ? `${app.borrowers[0].first_name} ${app.borrowers[0].last_name || ''}`
    : 'לקוח חדש'

  return (
    <div className="min-h-screen bg-[#0f1623] flex flex-col" dir="rtl">
      <Navbar />
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
