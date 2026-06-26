import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch } from '../../utils/api'
import {
  EditableField, Section, SaveIndicator, useAutoSave, EditableTable, InfoButton,
} from './shared'

const INFO = {
  public_figure: 'איש ציבור הוא נושא תפקיד ציבורי בכיר (שר, חבר כנסת, שופט, קצין בכיר, מנהל בכיר בחברה ממשלתית) או בן משפחה / מקורב של אדם כזה.',
  credit: 'כולל: תיק בהוצאה לפועל, חשבון מוגבל או הגבלה חמורה, פיגורים בתשלומי משכנתא, צ׳קים שחזרו, הלוואות בכשל, אשראי בכשל, הוראות קבע שלא כובדו, אחר.',
  net_income: 'שכיר — ממוצע שלושת החודשים האחרונים.\nעצמאי — ממוצע שלוש השנים האחרונות.',
  health: 'אם המצב הבריאותי אינו תקין — יש ליצור קשר עם יועץ, שכן נדרש ביטוח חיים למשכנתא.',
  children_shared: 'אם יש בן/בת זוג — האם הילדים משותפים או שיש ילדים נוספים.',
  citizenship: 'שאלה אינפורמטיבית עבור הבנק. אם יש אזרחות נוספת, נשאל האם קיים הסדר מס במדינה אחרת.',
}

// ── A hook to manage one nested per-borrower resource (incomes/expenses/properties)
function useNestedResource(appId, borrowerId, token, resource, initial) {
  const [rows, setRows] = useState(initial || [])
  const timers = useRef({})
  useEffect(() => { setRows(initial || []) }, [borrowerId]) // reset when borrower changes

  const base = `/api/applications/${appId}/borrowers/${borrowerId}/${resource}`

  const addRow = useCallback(async () => {
    const created = await apiFetch(base, { token, method: 'POST', body: { fields: {} } })
    setRows((r) => [...r, created])
  }, [base, token])

  const deleteRow = useCallback(async (id) => {
    setRows((r) => r.filter((x) => x.id !== id))
    await apiFetch(`${base}/${id}`, { token, method: 'DELETE' })
  }, [base, token])

  const changeCell = useCallback((id, name, value) => {
    setRows((r) => r.map((x) => (x.id === id ? { ...x, [name]: value } : x)))
    const key = `${id}.${name}`
    if (timers.current[key]) clearTimeout(timers.current[key])
    timers.current[key] = setTimeout(() => {
      apiFetch(`${base}/${id}`, { token, method: 'PATCH', body: { fields: { [name]: value } } }).catch(() => {})
    }, 600)
  }, [base, token])

  return { rows, addRow, deleteRow, changeCell }
}

// ── The form for a single borrower ────────────────────────────────────────────
function BorrowerForm({ app, borrower, token, onSaved }) {
  const [b, setB] = useState(borrower)
  useEffect(() => { setB(borrower) }, [borrower.id])

  const save = useCallback(async (fields) => {
    const updated = await apiFetch(`/api/applications/${app.application_id}/borrowers/${borrower.id}`, {
      token, method: 'PATCH', body: { fields },
    })
    onSaved && onSaved()
    return updated
  }, [app.application_id, borrower.id, token, onSaved])

  const { schedule, status } = useAutoSave(save)
  const change = (name, value) => {
    setB((prev) => ({ ...prev, [name]: value }))
    schedule(name, value)
  }
  const F = (label, name, kind = 'text', extra = {}) => (
    <EditableField label={label} name={name} kind={kind} value={b[name]} onChange={change} {...extra} />
  )

  // Seniority < 1 year → show previous-workplace block
  const monthsAtJob = b.employment_start_date
    ? (Date.now() - new Date(b.employment_start_date).getTime()) / (1000 * 60 * 60 * 24 * 30.4)
    : null
  const showPrevWorkplace = monthsAtJob !== null && monthsAtJob < 12

  // Nested resources
  const incomes = useNestedResource(app.application_id, borrower.id, token, 'incomes', borrower.additional_incomes)
  const expenses = useNestedResource(app.application_id, borrower.id, token, 'expenses', borrower.fixed_expenses)
  const properties = useNestedResource(app.application_id, borrower.id, token, 'properties', borrower.additional_properties)

  // Checking accounts are a JSONB array on the borrower — managed locally + saved whole.
  const [accounts, setAccounts] = useState(() =>
    (borrower.checking_accounts || []).map((a, i) => ({ id: a.id || `acc-${i}`, ...a })))
  useEffect(() => {
    setAccounts((borrower.checking_accounts || []).map((a, i) => ({ id: a.id || `acc-${i}`, ...a })))
  }, [borrower.id])
  const persistAccounts = (next) => {
    setAccounts(next)
    schedule('checking_accounts', next.map(({ id, ...rest }) => rest)) // eslint-disable-line no-unused-vars
  }

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
        {F('ילדים משותפים', 'children_shared', 'bool', { info: INFO.children_shared })}
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
        {F('הכנסה נטו חודשית (₪)', 'net_income', 'number', { info: INFO.net_income })}
        {showPrevWorkplace && (
          <>
            <div className="sm:col-span-2 text-xs text-amber-300/80 mb-1">ותק נמוך משנה — נא למלא מקום עבודה קודם:</div>
            {F('מעסיק קודם', 'prev_employer_name')}
            {F('תחילת עבודה קודמת', 'prev_employment_start_date', 'date')}
            {F('סיום עבודה קודמת', 'prev_employment_end_date', 'date')}
          </>
        )}
      </Section>

      <Section title="רגולציה ובריאות">
        {F('אזרחות נוספת', 'has_additional_citizenship', 'bool', { info: INFO.citizenship })}
        {b.has_additional_citizenship && F('הסדר מס בחו"ל', 'has_foreign_tax_obligation', 'bool')}
        {F('קרבה לאיש ציבור', 'is_politically_exposed', 'bool', { info: INFO.public_figure })}
        {F('מצב בריאותי תקין', 'has_health_issues', 'bool', { info: INFO.health })}
        {F('בעיות אשראי (7 שנים)', 'has_credit_issues', 'bool', { info: INFO.credit })}
        {b.has_credit_issues && F('פירוט בעיות האשראי', 'credit_issues_detail', 'textarea')}
        {F('מעשן/ת', 'is_smoker', 'bool')}
      </Section>

      <Section title="זכאות דירה ראשונה">
        {F('חודשי שירות צבאי', 'military_service_months', 'number')}
        {F('אחים בארץ', 'num_siblings_in_country', 'number')}
        {F('ילדים מתחת לגיל 18', 'children_under_18', 'number')}
      </Section>

      <Section title="שכירות / השכרה">
        {F('משלם/מקבל שכר דירה', 'has_rental_payment', 'bool')}
        {b.has_rental_payment && F('סכום שכר דירה חודשי (₪)', 'rental_payment_amount', 'number')}
      </Section>

      <Section title="קרן השתלמות / חיסכון">
        {F('קרן השתלמות / חיסכון', 'has_savings_fund', 'bool')}
        {b.has_savings_fund && F('סכום צפוי (₪)', 'savings_fund_amount', 'number')}
        {b.has_savings_fund && F('מועד נזילות', 'savings_fund_available_date', 'date')}
      </Section>

      <EditableTable
        title="הכנסות נוספות"
        addLabel="+ הוסף הכנסה"
        emptyText="לא נוספו הכנסות נוספות"
        columns={[
          { name: 'income_type', label: 'סוג', kind: 'select' },
          { name: 'income_type_detail', label: 'פירוט', kind: 'text' },
          { name: 'monthly_amount', label: 'סכום חודשי (₪)', kind: 'number' },
        ]}
        rows={incomes.rows}
        onAdd={incomes.addRow}
        onChange={incomes.changeCell}
        onDelete={incomes.deleteRow}
      />

      <EditableTable
        title="הוצאות קבועות והלוואות"
        addLabel="+ הוסף הוצאה / הלוואה"
        emptyText="לא נוספו הוצאות קבועות"
        columns={[
          { name: 'expense_type', label: 'סוג', kind: 'select' },
          { name: 'monthly_amount', label: 'החזר חודשי (₪)', kind: 'number' },
          { name: 'remaining_balance', label: 'יתרה (₪)', kind: 'number' },
          { name: 'end_date', label: 'מועד סיום', kind: 'date' },
          { name: 'interest_rate', label: 'ריבית', kind: 'number' },
          { name: 'source', label: 'מקור', kind: 'select', optionsSource: 'expense_source' },
        ]}
        rows={expenses.rows}
        onAdd={expenses.addRow}
        onChange={expenses.changeCell}
        onDelete={expenses.deleteRow}
      />

      <EditableTable
        title="חשבונות עו״ש"
        addLabel="+ הוסף חשבון"
        emptyText="לא נוספו חשבונות"
        columns={[
          { name: 'bank', label: 'בנק', kind: 'text' },
          { name: 'branch', label: 'סניף', kind: 'number' },
          { name: 'account_number', label: 'מספר חשבון', kind: 'number' },
        ]}
        rows={accounts}
        onAdd={() => persistAccounts([...accounts, { id: `acc-${Date.now()}` }])}
        onChange={(id, name, value) => persistAccounts(accounts.map((a) => (a.id === id ? { ...a, [name]: value } : a)))}
        onDelete={(id) => persistAccounts(accounts.filter((a) => a.id !== id))}
      />

      <EditableTable
        title="נכסים נוספים"
        addLabel="+ הוסף נכס"
        emptyText="לא נוספו נכסים נוספים"
        columns={[
          { name: 'property_type', label: 'סוג', kind: 'select' },
          { name: 'city', label: 'עיר', kind: 'text' },
          { name: 'street', label: 'רחוב', kind: 'text' },
          { name: 'number', label: 'מספר', kind: 'text' },
          { name: 'area_sqm', label: 'שטח (מ״ר)', kind: 'number' },
          { name: 'estimated_value', label: 'שווי (₪)', kind: 'number' },
          { name: 'existing_mortgage', label: 'משכנתא קיימת (₪)', kind: 'number' },
        ]}
        rows={properties.rows}
        onAdd={properties.addRow}
        onChange={properties.changeCell}
        onDelete={properties.deleteRow}
      />
    </div>
  )
}

// ── Tab wrapper: borrower selector + add borrower ─────────────────────────────
export function PersonalDetailsTab({ app, token, onSaved }) {
  const borrowers = (app.borrowers || []).slice().sort((a, b) => a.sequence_number - b.sequence_number)
  const [activeId, setActiveId] = useState(borrowers[0]?.id)
  const [adding, setAdding] = useState(false)

  const active = borrowers.find((b) => b.id === activeId) || borrowers[0]

  const addBorrower = async () => {
    setAdding(true)
    try {
      const created = await apiFetch(`/api/applications/${app.application_id}/borrowers`, { token, method: 'POST' })
      await (onSaved && onSaved())
      setActiveId(created.id)
    } finally {
      setAdding(false)
    }
  }

  if (!active) return <p className="text-gray-400">לא נמצאו פרטי לווה.</p>

  return (
    <div>
      {borrowers.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {borrowers.map((b, i) => (
            <button
              key={b.id}
              onClick={() => setActiveId(b.id)}
              className={`text-xs px-3 py-1.5 rounded-full border transition
                ${b.id === active.id
                  ? 'bg-blue-600/30 border-blue-500 text-blue-200'
                  : 'border-gray-700 text-gray-400 hover:text-gray-200'}`}
            >
              {b.first_name ? `${b.first_name} ${b.last_name || ''}` : `לווה ${i + 1}`}
            </button>
          ))}
          <button
            onClick={addBorrower}
            disabled={adding}
            className="text-xs px-3 py-1.5 rounded-full border border-dashed border-gray-600 text-gray-400 hover:text-blue-300 hover:border-blue-500 transition disabled:opacity-50"
          >
            {adding ? '...' : '+ הוסף לווה'}
          </button>
          <span className="mr-1"><InfoButton text="כל לווה ממלא את פרטיו בנפרד. לזוג נשוי — יש לכלול את שני בני הזוג באישור." /></span>
        </div>
      )}
      <BorrowerForm key={active.id} app={app} borrower={active} token={token} onSaved={onSaved} />
    </div>
  )
}
