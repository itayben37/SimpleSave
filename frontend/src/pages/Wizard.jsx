import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Navbar from '../components/Navbar'

const AUTH_BYPASS = import.meta.env.VITE_AUTH_BYPASS === 'true'

const API = import.meta.env.VITE_API_URL || ''

// ── Wizard step definitions ───────────────────────────────────────────────────

const STEPS = [
  { id: 1, title: 'מטרת ההלוואה', fields: ['loan_purpose'] },
  { id: 2, title: 'פרטי הנכס', fields: ['property_value', 'loan_amount', 'first_home'] },
  { id: 3, title: 'מספר לווים', fields: ['num_borrowers'] },
  { id: 4, title: 'מעמד אישי', fields: ['marital_status', 'num_children', 'wedding_duration_years'] },
  { id: 5, title: 'שירות צבאי', fields: ['military_service_type'] },
  { id: 6, title: 'אחים זכאים', fields: ['eligible_siblings_count'] },
  { id: 7, title: 'הכנסה חודשית', fields: ['total_monthly_income', 'total_monthly_obligations'] },
  { id: 8, title: 'תאריך לידה', fields: ['primary_borrower_birth_date'] },
  { id: 9, title: 'משכנתא קיימת', fields: ['existing_mortgage_balance', 'vatikei_interest'] },
  { id: 10, title: 'סיכום', fields: [] },
]

const STORAGE_KEY = 'simplesave_wizard'

function loadDraft() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveDraft(data) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

// ── Validation ────────────────────────────────────────────────────────────────

function validateStep(step, data) {
  const errs = {}
  if (step === 1) {
    if (!data.loan_purpose) errs.loan_purpose = 'נדרש לבחור מטרת הלוואה'
  }
  if (step === 2) {
    const pv = parseFloat(data.property_value)
    const la = parseFloat(data.loan_amount)
    if (!data.property_value || isNaN(pv) || pv < 100000)
      errs.property_value = 'ערך נכס חייב להיות לפחות ₪100,000'
    if (!data.loan_amount || isNaN(la) || la < 50000)
      errs.loan_amount = 'סכום הלוואה חייב להיות לפחות ₪50,000'
    if (pv && la && la > pv * 0.9)
      errs.loan_amount = 'סכום הלוואה לא יכול לעלות על 90% מערך הנכס'
  }
  if (step === 3) {
    const n = parseInt(data.num_borrowers)
    if (!n || n < 1 || n > 4) errs.num_borrowers = 'מספר לווים: 1–4'
  }
  if (step === 4) {
    if (!data.marital_status) errs.marital_status = 'נדרש לבחור מעמד אישי'
  }
  if (step === 7) {
    const inc = parseFloat(data.total_monthly_income)
    if (!data.total_monthly_income || isNaN(inc) || inc <= 0)
      errs.total_monthly_income = 'נדרשת הכנסה חודשית חיובית'
  }
  if (step === 8) {
    if (!data.primary_borrower_birth_date) errs.primary_borrower_birth_date = 'נדרש תאריך לידה'
    else {
      const age = Math.floor((Date.now() - new Date(data.primary_borrower_birth_date)) / 31557600000)
      if (age < 18 || age > 80) errs.primary_borrower_birth_date = 'גיל הלווה חייב להיות בין 18 ל-80'
    }
  }
  return errs
}

// ── Step components ───────────────────────────────────────────────────────────

function Field({ label, error, children }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      {children}
      {error && <p className="text-red-400 text-xs mt-1">{error}</p>}
    </div>
  )
}

function Input({ name, value, onChange, type = 'text', placeholder, min }) {
  return (
    <input
      type={type}
      name={name}
      value={value || ''}
      onChange={onChange}
      placeholder={placeholder}
      min={min}
      className="w-full bg-[#0f1623] border border-gray-600 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
    />
  )
}

function Select({ name, value, onChange, options }) {
  return (
    <select
      name={name}
      value={value || ''}
      onChange={onChange}
      className="w-full bg-[#0f1623] border border-gray-600 rounded px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
    >
      <option value="">-- בחר --</option>
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function StepContent({ step, data, errors, onChange }) {
  const inp = (name, label, props = {}) => (
    <Field key={name} label={label} error={errors[name]}>
      <Input name={name} value={data[name]} onChange={onChange} {...props} />
    </Field>
  )
  const sel = (name, label, options) => (
    <Field key={name} label={label} error={errors[name]}>
      <Select name={name} value={data[name]} onChange={onChange} options={options} />
    </Field>
  )

  if (step === 1) return sel('loan_purpose', 'מטרת ההלוואה', [
    { value: 'primary_residence', label: 'דירה ראשונה' },
    { value: 'additional_property', label: 'דירה נוספת' },
    { value: 'all_purpose', label: 'כל מטרה' },
    { value: 'home_improvement', label: 'שיפוץ' },
  ])

  if (step === 2) return (
    <>
      {inp('property_value', 'ערך הנכס (₪)', { type: 'number', min: '100000', placeholder: '1500000' })}
      {inp('loan_amount', 'סכום ההלוואה (₪)', { type: 'number', min: '50000', placeholder: '1000000' })}
      <Field label="דירה ראשונה?" error={errors.first_home}>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            name="first_home"
            checked={!!data.first_home}
            onChange={e => onChange({ target: { name: 'first_home', value: e.target.checked } })}
            className="w-4 h-4"
          />
          <span className="text-gray-300">כן, זו דירתי הראשונה</span>
        </label>
      </Field>
    </>
  )

  if (step === 3) return inp('num_borrowers', 'מספר לווים', { type: 'number', min: '1', placeholder: '1' })

  if (step === 4) return (
    <>
      {sel('marital_status', 'מעמד אישי', [
        { value: 'single', label: 'רווק/ה' },
        { value: 'married', label: 'נשוי/אה' },
        { value: 'divorced', label: 'גרוש/ה' },
        { value: 'widowed', label: 'אלמן/ה' },
      ])}
      {inp('num_children', 'מספר ילדים', { type: 'number', min: '0', placeholder: '0' })}
      {inp('wedding_duration_years', 'שנות נישואין', { type: 'number', min: '0', placeholder: '0' })}
    </>
  )

  if (step === 5) return sel('military_service_type', 'שירות צבאי', [
    { value: 'none', label: 'לא שירתי' },
    { value: 'regular', label: 'שירות סדיר (36+ חודשים)' },
    { value: 'reserve_100plus_days', label: 'מילואים 100+ ימים' },
  ])

  if (step === 6) return inp('eligible_siblings_count', 'מספר אחים/אחיות זכאים לדירה', { type: 'number', min: '0', placeholder: '0' })

  if (step === 7) return (
    <>
      {inp('total_monthly_income', 'הכנסה חודשית כוללת (₪)', { type: 'number', min: '1', placeholder: '15000' })}
      {inp('total_monthly_obligations', 'התחייבויות חודשיות (₪)', { type: 'number', min: '0', placeholder: '2000' })}
    </>
  )

  if (step === 8) return inp('primary_borrower_birth_date', 'תאריך לידה (לווה ראשי)', { type: 'date' })

  if (step === 9) return (
    <>
      {inp('existing_mortgage_balance', 'יתרת משכנתא קיימת (₪)', { type: 'number', min: '0', placeholder: '0' })}
      <Field label="מעוניין בדירה במחיר למשתכן?" error={errors.vatikei_interest}>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            name="vatikei_interest"
            checked={!!data.vatikei_interest}
            onChange={e => onChange({ target: { name: 'vatikei_interest', value: e.target.checked } })}
            className="w-4 h-4"
          />
          <span className="text-gray-300">כן, אני מתעניין/ת בתכנית ותיקי הארץ</span>
        </label>
      </Field>
    </>
  )

  if (step === 10) return (
    <div className="space-y-3 text-gray-300">
      <h3 className="text-lg font-semibold text-white mb-4">סיכום השאלון</h3>
      {[
        ['מטרת הלוואה', data.loan_purpose],
        ['ערך נכס', data.property_value ? `₪${Number(data.property_value).toLocaleString('he-IL')}` : '-'],
        ['סכום הלוואה', data.loan_amount ? `₪${Number(data.loan_amount).toLocaleString('he-IL')}` : '-'],
        ['דירה ראשונה', data.first_home ? 'כן' : 'לא'],
        ['מספר לווים', data.num_borrowers || '-'],
        ['מעמד אישי', data.marital_status || '-'],
        ['מספר ילדים', data.num_children ?? '-'],
        ['שירות צבאי', data.military_service_type || '-'],
        ['הכנסה חודשית', data.total_monthly_income ? `₪${Number(data.total_monthly_income).toLocaleString('he-IL')}` : '-'],
        ['תאריך לידה', data.primary_borrower_birth_date || '-'],
      ].map(([label, val]) => (
        <div key={label} className="flex justify-between border-b border-gray-700 pb-2">
          <span className="text-gray-400">{label}</span>
          <span className="text-white">{val}</span>
        </div>
      ))}
    </div>
  )

  return null
}

// ── Main wizard component ─────────────────────────────────────────────────────

export default function Wizard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(1)
  const [data, setData] = useState(loadDraft)
  const [errors, setErrors] = useState({})
  const [applicationId, setApplicationId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState(null)

  // Create application on first mount if not already started
  useEffect(() => {
    if (AUTH_BYPASS) {
      setApplicationId('demo')
      return
    }
    const stored = sessionStorage.getItem('simplesave_app_id')
    if (stored) {
      setApplicationId(stored)
      return
    }
    user?.getToken().then(token =>
      fetch(`${API}/api/applications`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }).then(r => r.json()).then(j => {
        if (j.application_id) {
          sessionStorage.setItem('simplesave_app_id', j.application_id)
          setApplicationId(j.application_id)
        }
      })
    ).catch(() => {
      setSubmitError('שגיאה ביצירת בקשה. רענן את הדף ונסה שנית.')
    })
  }, [user])

  const handleChange = useCallback(e => {
    const { name, value } = e.target
    setData(prev => {
      const next = { ...prev, [name]: value }
      saveDraft(next)
      return next
    })
    setErrors(prev => ({ ...prev, [name]: undefined }))
  }, [])

  const autoSave = useCallback(async (stepData) => {
    if (!applicationId) return
    try {
      const token = await user.getToken()
      await fetch(`${API}/api/applications/${applicationId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ wizard_data: stepData }),
      })
    } catch {
      // silent — draft is in sessionStorage
    }
  }, [applicationId, user])

  const handleNext = async () => {
    const errs = validateStep(currentStep, data)
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }
    setErrors({})
    setSaving(true)
    await autoSave(data)
    setSaving(false)

    if (currentStep < STEPS.length) {
      setCurrentStep(prev => prev + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(prev => prev - 1)
  }

  const handleSubmit = async () => {
    if (!applicationId) {
      setSubmitError('שגיאה: לא נמצא מזהה בקשה. רענן את הדף ונסה שנית.')
      return
    }
    setSaving(true)
    setSubmitError(null)
    try {
      if (!AUTH_BYPASS) {
        const token = await user.getToken()
        await fetch(`${API}/api/applications/${applicationId}`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            wizard_data: data,
            advance_status: true,
          }),
        })
      }
      sessionStorage.removeItem(STORAGE_KEY)
      navigate(`/applications/${applicationId}/clocks`)
    } catch (err) {
      setSubmitError('שגיאה בשמירת הנתונים. נסה שנית.')
    } finally {
      setSaving(false)
    }
  }

  const progress = ((currentStep - 1) / (STEPS.length - 1)) * 100
  const step = STEPS[currentStep - 1]

  return (
    <div className="min-h-screen bg-[#0f1623]">
      <Navbar />
    <div className="flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>שלב {currentStep} מתוך {STEPS.length}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Card */}
        <div className="bg-[#1a2333] rounded-xl p-8 shadow-xl">
          <h2 className="text-2xl font-bold text-white mb-6">{step.title}</h2>

          <StepContent
            step={currentStep}
            data={data}
            errors={errors}
            onChange={handleChange}
          />

          {submitError && (
            <p className="text-red-400 text-sm mt-3">{submitError}</p>
          )}

          <div className="flex justify-between mt-8 gap-3">
            <button
              onClick={handleBack}
              disabled={currentStep === 1}
              className="px-5 py-2 rounded bg-gray-700 text-white disabled:opacity-30 hover:bg-gray-600 transition"
            >
              חזור
            </button>

            {currentStep < STEPS.length ? (
              <button
                onClick={handleNext}
                disabled={saving}
                className="px-6 py-2 rounded bg-blue-600 text-white hover:bg-blue-500 transition disabled:opacity-60"
              >
                {saving ? 'שומר...' : 'הבא'}
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={saving}
                className="px-6 py-2 rounded bg-green-600 text-white hover:bg-green-500 transition disabled:opacity-60"
              >
                {saving ? 'שולח...' : 'צפה בשעוני עלות'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
    </div>
  )
}
