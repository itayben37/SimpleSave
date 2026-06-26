import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch, apiUpload, openProtectedFile } from '../../utils/api'

const DOC_STATUS = {
  required: ['נדרש', 'bg-gray-700 text-gray-300'],
  uploaded: ['הועלה — בבדיקה', 'bg-blue-900/40 text-blue-300'],
  approved: ['אושר', 'bg-green-900/40 text-green-300'],
  rejected: ['נדחה — נדרש תיקון', 'bg-red-900/40 text-red-300'],
  not_required: ['לא נדרש', 'bg-gray-800 text-gray-500'],
}

function DocRow({ doc, token, isAdvisor, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)
  const [label, cls] = DOC_STATUS[doc.status] || DOC_STATUS.required

  const upload = async (file) => {
    if (!file) return
    setBusy(true)
    try {
      await apiUpload(`/api/documents/${doc.id}/file`, { token, file })
      onChanged()
    } finally { setBusy(false) }
  }

  const review = async (action) => {
    setBusy(true)
    try {
      const body = { action }
      if (action === 'reject') body.rejection_reason = window.prompt('סיבת הדחייה:') || 'נדרש תיקון'
      await apiFetch(`/api/documents/${doc.id}`, { token, method: 'PATCH', body })
      onChanged()
    } finally { setBusy(false) }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); upload(e.dataTransfer.files[0]) }}
      className={`bg-[#1a2333] rounded-xl border p-4 flex items-center justify-between transition
        ${dragOver ? 'border-blue-500 bg-blue-900/10' : 'border-gray-800'}`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${doc.required_for_principal_approval ? 'bg-yellow-500' : 'bg-gray-600'}`} />
        <div className="min-w-0">
          {doc.has_file ? (
            <button onClick={() => openProtectedFile(`/api/documents/${doc.id}/file`, { token })}
                    className="text-blue-300 hover:text-blue-200 text-sm underline truncate">
              {doc.name}{doc.file_name ? ` — ${doc.file_name}` : ''}
            </button>
          ) : (
            <span className="text-white text-sm">{doc.name}</span>
          )}
          {doc.required_for_principal_approval && (
            <span className="text-xs text-yellow-500/70 bg-yellow-900/20 px-2 py-0.5 rounded mr-2">חובה לאישור עקרוני</span>
          )}
          {doc.description && <p className="text-gray-500 text-xs mt-0.5">{doc.description}</p>}
          {doc.rejection_reason && <p className="text-red-400 text-xs mt-1">{doc.rejection_reason}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`text-xs px-2 py-1 rounded ${cls}`}>{label}</span>
        <input ref={inputRef} type="file" className="hidden" onChange={(e) => upload(e.target.files[0])} />
        {isAdvisor ? (
          doc.status === 'uploaded' && (
            <>
              <button onClick={() => review('approve')} disabled={busy} className="text-xs bg-green-700 hover:bg-green-600 text-white px-3 py-1 rounded disabled:opacity-50">אשר</button>
              <button onClick={() => review('reject')} disabled={busy} className="text-xs bg-red-700 hover:bg-red-600 text-white px-3 py-1 rounded disabled:opacity-50">דחה</button>
            </>
          )
        ) : (
          doc.status !== 'approved' && (
            <button onClick={() => inputRef.current?.click()} disabled={busy}
                    className="text-xs bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded transition disabled:opacity-50">
              {busy ? '...' : doc.has_file ? 'העלה מחדש' : 'העלה'}
            </button>
          )
        )}
      </div>
    </div>
  )
}

function AuthorizationBanner({ app, token, onSigned }) {
  const [busy, setBusy] = useState(false)
  if (app.authorization_signed_at) {
    return (
      <div className="bg-green-900/20 border border-green-800/50 rounded-xl p-4 mb-5 text-sm text-green-300">
        ✓ ייפויי הכוח נחתמו — אנו רשאים לעבוד מול הבנקים עבורך.
      </div>
    )
  }
  const sign = async () => {
    setBusy(true)
    try {
      await apiFetch(`/api/applications/${app.application_id}/sign-authorization`, { token, method: 'POST' })
      onSigned && onSigned()
    } finally { setBusy(false) }
  }
  return (
    <div className="bg-blue-900/20 border border-blue-700/50 rounded-xl p-4 mb-5 flex items-center justify-between">
      <div>
        <p className="text-white text-sm font-medium mb-1">חתימה על ייפויי כוח לבנקים</p>
        <p className="text-gray-400 text-xs">חתימה על ייפויי הכוח מאפשרת לנו לפנות לבנקים ולקדם את המשכנתא שלך.</p>
      </div>
      <button onClick={sign} disabled={busy} className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-5 py-2 rounded-lg transition disabled:opacity-50">
        {busy ? '...' : 'חתום עכשיו'}
      </button>
    </div>
  )
}

export function DocumentsTab({ app, token, role, onSaved }) {
  const [docs, setDocs] = useState([])
  const [summary, setSummary] = useState({ blocking_total: 0, blocking_approved: 0 })
  const [loading, setLoading] = useState(true)
  const isAdvisor = role === 'advisor' || role === 'admin'

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

  if (loading) return <p className="text-gray-400">טוען מסמכים...</p>

  const allApproved = summary.blocking_total > 0 && summary.blocking_approved === summary.blocking_total

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white font-semibold text-lg">מסמכים נדרשים</h2>
        <span className="text-xs text-gray-500">{summary.blocking_approved} מתוך {summary.blocking_total} מסמכי חובה אושרו</span>
      </div>

      <AuthorizationBanner app={app} token={token} onSigned={onSaved} />

      <p className="text-gray-500 text-xs mb-3">ניתן להעלות קובץ בלחיצה על "העלה" או בגרירת קובץ אל השורה.</p>

      <div className="space-y-3">
        {docs.map((doc) => (
          <DocRow key={doc.id} doc={doc} token={token} isAdvisor={isAdvisor} onChanged={load} />
        ))}
      </div>

      {allApproved && (
        <div className="mt-6 bg-green-900/20 border border-green-800/50 rounded-xl p-4 text-center">
          <p className="text-green-300 text-sm">כל מסמכי החובה אושרו — ניתן להתקדם לשלב האישור העקרוני.</p>
        </div>
      )}
    </div>
  )
}
