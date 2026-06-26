import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../../utils/api'

function Loading() { return <p className="text-gray-400">טוען...</p> }
function Empty({ children }) {
  return <div className="text-center py-16 text-gray-500"><p className="text-3xl mb-2">📭</p><p className="text-sm">{children}</p></div>
}

// ── Approval in Principle ─────────────────────────────────────────────────────
export function PrincipalApprovalTab({ app, token }) {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    apiFetch(`/api/applications/${app.application_id}/principal-approvals`, { token })
      .then((j) => setRows(j.principal_approvals)).catch(() => setRows([]))
  }, [app.application_id, token])

  if (rows === null) return <Loading />
  const bankSelected = !!app.selected_bank_id

  return (
    <div>
      <h2 className="text-white font-semibold text-lg mb-4">אישור עקרוני</h2>
      <p className="text-gray-500 text-xs mb-5">הבנקים שהעניקו אישור עקרוני מוצגים בהדגשה. הבנק עם התנאים הטובים ביותר מסומן.</p>
      {rows.length === 0 ? (
        <Empty>טרם התקבלו אישורים עקרוניים מהבנקים. נעדכן אותך כאן ברגע שיתקבלו.</Empty>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {rows.map((a) => {
            const lit = a.status === 'approved'
            const dim = bankSelected && app.selected_bank_id !== a.bank_id
            return (
              <div key={a.id}
                className={`rounded-xl border p-4 text-center transition
                  ${a.is_best_offer ? 'border-yellow-500 bg-yellow-900/10' : 'border-gray-800 bg-[#1a2333]'}
                  ${lit ? '' : 'opacity-50'} ${dim ? 'opacity-30 grayscale' : ''}`}>
                {a.is_best_offer && <div className="text-yellow-400 text-xs mb-1">★ התנאים הטובים ביותר</div>}
                {a.bank_logo
                  ? <img src={a.bank_logo} alt={a.bank_name} className="h-8 mx-auto mb-2 object-contain" />
                  : <div className="text-white text-sm font-medium mb-2">{a.bank_name}</div>}
                <div className={`text-xs ${lit ? 'text-green-300' : 'text-gray-500'}`}>
                  {a.status === 'approved' ? 'אושר' : a.status === 'pending' ? 'בבדיקה' : a.status === 'rejected' ? 'נדחה' : a.status}
                </div>
                {a.approved_amount != null && <div className="text-white text-sm mt-1">₪{a.approved_amount.toLocaleString()}</div>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Collaterals ───────────────────────────────────────────────────────────────
const COLLATERAL_STATUS = {
  pending: ['ממתין', 'text-gray-400'], submitted: ['הוגש', 'text-blue-300'], approved: ['אושר', 'text-green-300'],
}
export function CollateralsTab({ app, token }) {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    apiFetch(`/api/applications/${app.application_id}/collaterals`, { token })
      .then((j) => setRows(j.collaterals)).catch(() => setRows([]))
  }, [app.application_id, token])

  if (rows === null) return <Loading />
  return (
    <div>
      <h2 className="text-white font-semibold text-lg mb-4">בטחונות</h2>
      <p className="text-gray-500 text-xs mb-5">רשימת הבטחונות שיש להחזיר לבנק לאחר חתימת המשכנתא.</p>
      {rows.length === 0 ? (
        <Empty>טרם הוגדרו בטחונות. היועץ יוסיף אותם כאן בהמשך התהליך.</Empty>
      ) : (
        <div className="space-y-2">
          {rows.map((c) => {
            const [lbl, cls] = COLLATERAL_STATUS[c.status] || COLLATERAL_STATUS.pending
            return (
              <div key={c.id} className="bg-[#1a2333] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
                <span className="text-white text-sm">{c.description}</span>
                <span className={`text-xs ${cls}`}>{lbl}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Messages ──────────────────────────────────────────────────────────────────
export function MessagesTab({ app, token }) {
  const [messages, setMessages] = useState(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const endRef = useRef(null)

  const load = useCallback(() => {
    apiFetch(`/api/messages/${app.application_id}`, { token })
      .then((j) => setMessages(j.messages)).catch(() => setMessages([]))
  }, [app.application_id, token])
  useEffect(() => { load() }, [load])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    if (!text.trim()) return
    setSending(true)
    try {
      await apiFetch(`/api/messages/${app.application_id}`, { token, method: 'POST', body: { body: text.trim() } })
      setText('')
      load()
    } finally { setSending(false) }
  }

  if (messages === null) return <Loading />
  return (
    <div className="flex flex-col h-[70vh]">
      <h2 className="text-white font-semibold text-lg mb-4">הודעות ליועץ</h2>
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 pl-1">
        {messages.length === 0 && <Empty>אין הודעות עדיין. כתבו ליועץ שלכם.</Empty>}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.is_mine ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${m.is_mine ? 'bg-blue-600/30 border border-blue-700' : 'bg-[#1a2333] border border-gray-800'}`}>
              {!m.is_mine && <p className="text-xs text-gray-400 mb-0.5">{m.sender_name || 'יועץ'}</p>}
              <p className="text-white text-sm whitespace-pre-line">{m.body}</p>
              {m.sent_at && <p className="text-[10px] text-gray-500 mt-1">{new Date(m.sent_at).toLocaleString('he-IL')}</p>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="כתוב הודעה..."
          className="flex-1 bg-[#0f1623] border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
        />
        <button onClick={send} disabled={sending} className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-5 py-2 rounded-lg transition disabled:opacity-50">שלח</button>
      </div>
    </div>
  )
}

// ── My Mortgage (post-signing) ────────────────────────────────────────────────
export function MyMortgageTab({ app, token }) {
  const [clocks, setClocks] = useState(null)
  useEffect(() => {
    apiFetch(`/api/calculations/clocks/${app.application_id}`, { token })
      .then((j) => setClocks(j.clocks)).catch(() => setClocks([]))
  }, [app.application_id, token])

  if (clocks === null) return <Loading />
  const active = app.status === 'ACTIVE_MORTGAGE'
  const selected = clocks.find((c) => c.mix_id === app.selected_mix_id) || clocks[0]

  return (
    <div>
      <h2 className="text-white font-semibold text-lg mb-4">המשכנתא שלי</h2>
      {!active && (
        <div className="bg-amber-900/20 border border-amber-800/40 rounded-xl p-4 mb-5 text-amber-200 text-sm">
          התצוגה תוצג במלואה לאחר חתימת המשכנתא. בינתיים מוצג התמהיל הנבחר לפי החישוב שלך.
        </div>
      )}
      {!selected ? (
        <Empty>אין נתוני תמהיל זמינים. השלימו את השאלון כדי לראות את שעוני העלות.</Empty>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="החזר חודשי התחלתי" value={`₪${Math.round(selected.monthly_payment_initial).toLocaleString()}`} />
            <Stat label="סך תשלום" value={`₪${Math.round(selected.total_payment).toLocaleString()}`} />
            <Stat label="סך ריבית" value={`₪${Math.round(selected.total_interest).toLocaleString()}`} />
            <Stat label="רמת סיכון" value={`${selected.risk_score_percentage?.toFixed?.(0) ?? '—'}%`} />
          </div>
          {Array.isArray(selected.stacked_bar_data) && selected.stacked_bar_data.length > 0 && (
            <div className="bg-[#1a2333] border border-gray-800 rounded-xl p-5">
              <h3 className="text-white text-sm font-semibold mb-3">פירוט מסלולים</h3>
              <div className="space-y-2">
                {selected.stacked_bar_data.map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-gray-300">{t.label || t.track_type || `מסלול ${i + 1}`}</span>
                    <span className="text-gray-400">{t.percentage != null ? `${t.percentage}%` : ''}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
function Stat({ label, value }) {
  return (
    <div className="bg-[#1a2333] border border-gray-800 rounded-xl p-4">
      <p className="text-gray-500 text-xs mb-1">{label}</p>
      <p className="text-white font-semibold text-sm">{value}</p>
    </div>
  )
}

// ── Eligibility card (Ministry-of-Housing "Price for Residents") ──────────────
export function EligibilityCard({ app, token }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    apiFetch(`/api/applications/${app.application_id}/eligibility`, { token })
      .then(setData).catch(() => setData({ available: false }))
  }, [app.application_id, token])

  if (!data || !data.available) return null
  return (
    <div className="bg-indigo-900/20 border border-indigo-700/40 rounded-xl p-5 mb-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-white font-semibold text-sm">זכאות משרד הבינוי (מחיר למשתכן / ותיקי הארץ)</h3>
        <span className={`text-sm font-bold ${data.is_eligible ? 'text-green-300' : 'text-amber-300'}`}>
          {data.eligibility_score} נק׳ {data.is_eligible ? '— זכאי/ת' : `(סף ${data.threshold})`}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        {Object.entries(data.score_breakdown || {}).map(([k, v]) => (
          <div key={k} className="flex justify-between bg-[#0f1623] rounded px-2 py-1">
            <span className="text-gray-400">{EL_LABELS[k] || k}</span>
            <span className="text-white">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
const EL_LABELS = {
  marital_status: 'מצב משפחתי', children: 'ילדים', military_service: 'שירות צבאי',
  eligible_siblings: 'אחים זכאים', wedding_duration: 'ותק נישואים', age: 'גיל',
}
