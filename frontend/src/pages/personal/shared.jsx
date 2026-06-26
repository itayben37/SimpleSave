// Shared building blocks for the Personal Area tabs (RTL Hebrew, dark theme).
import { useState, useRef, useCallback } from 'react'

// ── Choice options (value, label) ─────────────────────────────────────────────
export const SELECT_OPTIONS = {
  gender: [['male', 'זכר'], ['female', 'נקבה']],
  marital_status: [['single', 'רווק/ה'], ['married', 'נשוי/אה'], ['divorced', 'גרוש/ה'], ['widowed', 'אלמן/ה']],
  education: [['high_school', 'תיכונית'], ['post_secondary', 'על-תיכונית'], ['bachelor', 'תואר ראשון'], ['master', 'תואר שני']],
  employment_status: [['employee', 'שכיר'], ['self_employed', 'עצמאי'], ['controlling_shareholder', 'בעל שליטה']],
  loan_purpose: [['primary_residence', 'דירה ראשונה'], ['additional_property', 'דירה נוספת'], ['all_purpose', 'כל מטרה'], ['home_improvement', 'שיפוץ']],
  purchase_status: [['searching', 'מחפש נכס'], ['signed_contract', 'חתם חוזה'], ['about_to_sign', 'עומד לחתום']],
  money_needed_by: [['this_month', 'בחודש הקרוב'], ['two_months', 'תוך חודשיים'], ['three_plus_months', 'שלושה חודשים ומעלה']],
  property_source: [['contractor', 'קבלן'], ['second_hand', 'יד שנייה']],
  property_registration_type: [['tabu', 'טאבו'], ['minha', 'מנהל מקרקעי ישראל'], ['mishkenet', 'חברה משכנת']],
  property_type: [['private_house', 'בית פרטי'], ['duplex', 'דו-משפחתי'], ['apartment_building', 'בית משותף']],
  valuation_source: [['self_assessment', 'הערכה עצמית'], ['appraiser', 'שמאי'], ['contractor', 'קבלן']],
  willing_to_transfer_account: [['yes', 'כן'], ['no', 'לא'], ['want_details_first', 'רוצה לשמוע פרטים']],
  refinance_purpose: [['save_total', 'חיסכון בסך ההחזרים'], ['reduce_monthly', 'הקטנת ההחזר החודשי'], ['change_risk', 'שינוי רמת הסיכון'], ['shorten_period', 'קיצור התקופה'], ['consolidate_loans', 'איחוד הלוואות']],
  income_type: [['pension', 'פנסיה'], ['rental', 'שכר דירה'], ['dividend', 'דיבידנד'], ['alimony_received', 'מזונות'], ['other', 'אחר']],
  expense_type: [['loan', 'הלוואה'], ['alimony_paid', 'מזונות'], ['leasing', 'ליסינג'], ['rent', 'שכירות'], ['other', 'אחר']],
  expense_source: [['bank', 'בנק'], ['savings_fund', 'קרן השתלמות'], ['insurance_company', 'חברת ביטוח'], ['other', 'אחר']],
}
export const BOOL_OPTIONS = [['true', 'כן'], ['false', 'לא']]

// ── Auto-save hook ────────────────────────────────────────────────────────────
export function useAutoSave(saveFn, delay = 700) {
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

export function SaveIndicator({ status }) {
  const map = {
    saving: ['שומר...', 'text-gray-400'],
    saved: ['נשמר ✓', 'text-green-400'],
    error: ['שגיאת שמירה', 'text-red-400'],
    idle: ['', ''],
  }
  const [label, cls] = map[status] || map.idle
  return <span className={`text-xs ${cls}`}>{label}</span>
}

const baseInput = 'w-full bg-[#0f1623] border border-gray-700 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none'

// ── Info button (tooltip) ─────────────────────────────────────────────────────
export function InfoButton({ text }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        className="w-4 h-4 rounded-full bg-gray-700 text-gray-300 text-[10px] leading-4 text-center hover:bg-blue-700"
        aria-label="מידע נוסף"
      >ⓘ</button>
      {open && (
        <span className="absolute z-20 right-0 mt-1 w-64 bg-[#0b1220] border border-gray-700 rounded-lg p-3 text-xs text-gray-300 shadow-xl whitespace-pre-line">
          {text}
        </span>
      )}
    </span>
  )
}

// ── Editable field ────────────────────────────────────────────────────────────
export function EditableField({ label, name, kind, value, onChange, options, info, optionsSource }) {
  let control
  const opts = options || (optionsSource ? SELECT_OPTIONS[optionsSource] : SELECT_OPTIONS[name])
  if (kind === 'select') {
    control = (
      <select className={baseInput} value={value ?? ''} onChange={(e) => onChange(name, e.target.value || null)}>
        <option value="">-- בחר --</option>
        {(opts || []).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    )
  } else if (kind === 'bool') {
    control = (
      <select className={baseInput} value={value === null || value === undefined ? '' : String(value)} onChange={(e) => onChange(name, e.target.value === '' ? null : e.target.value === 'true')}>
        <option value="">-- בחר --</option>
        {BOOL_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    )
  } else if (kind === 'textarea') {
    control = <textarea rows={3} className={baseInput} value={value ?? ''} onChange={(e) => onChange(name, e.target.value === '' ? null : e.target.value)} />
  } else {
    control = (
      <input
        type={kind === 'number' ? 'number' : kind === 'date' ? 'date' : 'text'}
        className={baseInput}
        value={value ?? ''}
        onChange={(e) => onChange(name, e.target.value === '' ? null : e.target.value)}
      />
    )
  }
  return (
    <div className="mb-3">
      <label className="block text-xs text-gray-400 mb-1">
        {label}{info && <span className="mr-1"> <InfoButton text={info} /></span>}
      </label>
      {control}
    </div>
  )
}

export function Section({ title, children, action }) {
  return (
    <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5 mb-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold text-sm">{title}</h3>
        {action}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">{children}</div>
    </div>
  )
}

// ── Editable nested table ─────────────────────────────────────────────────────
// columns: [{ name, label, kind, optionsSource }]
// rows: array of objects (each has `id`). Callbacks do the persistence.
export function EditableTable({ title, columns, rows, onAdd, onChange, onDelete, addLabel = '+ הוסף שורה', emptyText = 'לא נוספו רשומות' }) {
  const cellInput = 'w-full bg-[#0f1623] border border-gray-700 rounded px-2 py-1 text-white text-xs focus:border-blue-500 focus:outline-none'
  return (
    <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold text-sm">{title}</h3>
        <button onClick={onAdd} className="text-xs bg-blue-700 hover:bg-blue-600 text-white px-3 py-1 rounded transition">{addLabel}</button>
      </div>
      {rows.length === 0 ? (
        <p className="text-gray-500 text-xs">{emptyText}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 text-right">
                {columns.map((c) => <th key={c.name} className="font-normal pb-2 px-1">{c.label}</th>)}
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-gray-800">
                  {columns.map((c) => (
                    <td key={c.name} className="py-1 px-1 align-top">
                      {c.kind === 'select' ? (
                        <select className={cellInput} value={row[c.name] ?? ''} onChange={(e) => onChange(row.id, c.name, e.target.value || null)}>
                          <option value="">--</option>
                          {(SELECT_OPTIONS[c.optionsSource || c.name] || []).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                        </select>
                      ) : (
                        <input
                          type={c.kind === 'number' ? 'number' : c.kind === 'date' ? 'date' : 'text'}
                          className={cellInput}
                          value={row[c.name] ?? ''}
                          onChange={(e) => onChange(row.id, c.name, e.target.value === '' ? null : e.target.value)}
                        />
                      )}
                    </td>
                  ))}
                  <td className="py-1 text-center">
                    <button onClick={() => onDelete(row.id)} className="text-red-400 hover:text-red-300" aria-label="מחק">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
