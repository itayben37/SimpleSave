import { useState, useCallback } from 'react'
import { apiFetch } from '../../utils/api'
import { EditableField, Section, SaveIndicator, useAutoSave } from './shared'
import { EligibilityCard } from './OtherTabs'

const EQUITY_SOURCES = [
  ['checking', 'עו"ש'], ['savings', 'חיסכון'], ['loans', 'הלוואות'],
  ['family', 'עזרה ממשפחה'], ['study_fund', 'קרן השתלמות'], ['other', 'אחר'],
]

export function MortgageDetailsTab({ app, token, onSaved }) {
  const [m, setM] = useState({
    loan_purpose: app.loan_purpose,
    purchase_status: app.purchase_status,
    contract_signed_date: app.contract_signed_date,
    money_needed_by: app.money_needed_by,
    previously_owned_property: app.previously_owned_property,
    property_source: app.property_source,
    property_registration_type: app.property_registration_type,
    property_address_city: app.property_address_city,
    property_address_street: app.property_address_street,
    property_address_number: app.property_address_number,
    property_address_apartment: app.property_address_apartment,
    property_type: app.property_type,
    property_floor: app.property_floor,
    property_total_floors: app.property_total_floors,
    property_age_years: app.property_age_years,
    property_area_sqm: app.property_area_sqm,
    property_value: app.property_value,
    valuation_source: app.valuation_source,
    equity_amount: app.equity_amount,
    loan_amount: app.loan_amount,
    desired_monthly_min: app.desired_monthly_min,
    desired_monthly_max: app.desired_monthly_max,
    previously_applied_to_banks: app.previously_applied_to_banks,
    willing_to_transfer_account: app.willing_to_transfer_account,
    refinance_inject_amount: app.refinance_inject_amount,
    refinance_purpose: app.refinance_purpose,
  })
  const [equity, setEquity] = useState(app.equity_sources || {})
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
  const changeEquity = (key, value) => {
    const next = { ...equity, [key]: value === '' || value === null ? undefined : Number(value) }
    setEquity(next)
    schedule('equity_sources', next)
  }
  const F = (label, name, kind = 'text', extra = {}) => (
    <EditableField label={label} name={name} kind={kind} value={m[name]} onChange={change} {...extra} />
  )

  const isRefinance = m.loan_purpose === 'all_purpose'

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold text-lg">נתוני משכנתא</h2>
        <SaveIndicator status={status} />
      </div>

      {m.loan_purpose === 'primary_residence' && m.previously_owned_property !== true && (
        <EligibilityCard app={app} token={token} />
      )}

      <Section title="סטטוס רכישה">
        {F('שלב הרכישה', 'purchase_status', 'select')}
        {m.purchase_status === 'signed_contract' && F('תאריך חתימת חוזה', 'contract_signed_date', 'date')}
        {m.purchase_status === 'signed_contract' && F('מתי נדרש הכסף', 'money_needed_by', 'select')}
      </Section>

      <Section title="סוג ומטרת ההלוואה">
        {F('סוג רכישה / מטרה', 'loan_purpose', 'select')}
        {m.loan_purpose === 'primary_residence' && F('האם הייתה בבעלותך דירה בעבר', 'previously_owned_property', 'bool')}
        {F('מקור הנכס', 'property_source', 'select')}
        {F('רישום הנכס', 'property_registration_type', 'select')}
      </Section>

      <Section title="כתובת הנכס">
        {F('עיר', 'property_address_city')}
        {F('רחוב', 'property_address_street')}
        {F('מספר', 'property_address_number')}
        {F('דירה', 'property_address_apartment')}
      </Section>

      <Section title="פרטי הנכס">
        {F('סוג נכס', 'property_type', 'select')}
        {F('קומה', 'property_floor', 'number')}
        {F('סה״כ קומות', 'property_total_floors', 'number')}
        {F('גיל המבנה (שנים)', 'property_age_years', 'number')}
        {F('שטח (מ״ר)', 'property_area_sqm', 'number')}
      </Section>

      <Section title="שווי, הון ומימון">
        {F('שווי הנכס / סכום רכישה (₪)', 'property_value', 'number')}
        {F('מקור הערכת שווי', 'valuation_source', 'select')}
        {F('הון עצמי (₪)', 'equity_amount', 'number')}
        {F('סכום ההלוואה המבוקש (₪)', 'loan_amount', 'number')}
      </Section>

      <Section title="מקורות ההון העצמי (₪)">
        {EQUITY_SOURCES.map(([key, label]) => (
          <EditableField
            key={key} label={label} name={`equity_${key}`} kind="number"
            value={equity[key] ?? ''} onChange={(_, v) => changeEquity(key, v)}
          />
        ))}
      </Section>

      <Section title="החזר חודשי רצוי (₪)">
        {F('מינימום', 'desired_monthly_min', 'number')}
        {F('מקסימום', 'desired_monthly_max', 'number')}
      </Section>

      <Section title="שאלות נוספות">
        {F('הוגשה בקשה למשכנתא לפני העבודה איתנו?', 'previously_applied_to_banks', 'bool')}
        {F('תסכים להעביר חשבון בנק בתנאים טובים יותר?', 'willing_to_transfer_account', 'select')}
      </Section>

      {isRefinance && (
        <Section title="מחזור משכנתא">
          {F('סכום להזרמה למשכנתא (₪)', 'refinance_inject_amount', 'number')}
          {F('מטרת המחזור', 'refinance_purpose', 'select')}
        </Section>
      )}

      <div className="bg-[#1a2333] rounded-xl border border-gray-800 p-5">
        <div className="flex justify-between items-center">
          <span className="text-gray-400 text-sm">אחוז מימון</span>
          <span className="text-white font-semibold">{ratio != null ? `${(ratio * 100).toFixed(1)}%` : '—'}</span>
        </div>
      </div>
    </div>
  )
}
