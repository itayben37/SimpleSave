import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const API = import.meta.env.VITE_API_URL || ''

const TIERS = [
  {
    id: 'mix_approval',
    name: 'אישור מיקס',
    price: 'חינם',
    description: 'קבל אישור עקרוני למיקס המשכנתא שלך',
    features: [
      'שאלון מקוון',
      'חישוב שעוני עלות',
      'אישור עקרוני',
      'תמיכה בצ\'אט',
    ],
    highlighted: false,
    cta: 'בחר מסלול זה',
  },
  {
    id: 'online_guidance',
    name: 'ליווי מקוון',
    price: '₪990',
    description: 'ליווי מקצועי מלא עד לחתימה על המשכנתא',
    features: [
      'כל מה שב"אישור מיקס"',
      'ליווי יועץ מקוון',
      'ניהול מסמכים',
      'בחירת בנק מומלץ',
      'שליחת בקשה לבנקים',
    ],
    highlighted: true,
    cta: 'הצטרף — הכי פופולרי',
  },
  {
    id: 'personal_advisor',
    name: 'יועץ אישי',
    price: '₪2,490',
    description: 'יועץ משכנתאות אישי לאורך כל הדרך',
    features: [
      'כל מה שב"ליווי מקוון"',
      'פגישה אישית',
      'ייצוג מול בנקים',
      'ניהול ביטחונות',
      'תמיכה עד רישום',
    ],
    highlighted: false,
    cta: 'בחר מסלול זה',
  },
]

export default function TierSelection() {
  const { applicationId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [selecting, setSelecting] = useState(null)
  const [error, setError] = useState(null)

  const handleSelect = async (tierId) => {
    if (!applicationId) return
    setSelecting(tierId)
    setError(null)
    try {
      const token = await user.getToken()
      const res = await fetch(`${API}/api/applications/${applicationId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wizard_data: { tier: tierId },
          advance_status: true,
        }),
      })
      if (!res.ok) throw new Error()
      navigate(`/applications/${applicationId}/details`)
    } catch {
      setError('שגיאה בבחירת מסלול. נסה שנית.')
    } finally {
      setSelecting(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#0f1623] py-12 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-3">בחר את המסלול המתאים לך</h1>
          <p className="text-gray-400 text-lg">כל המסלולים כוללים חישוב שעוני עלות מותאם אישית</p>
        </div>

        {error && (
          <p className="text-red-400 text-center mb-6">{error}</p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {TIERS.map(tier => (
            <div
              key={tier.id}
              className={`relative rounded-2xl p-6 flex flex-col border-2 transition-all
                ${tier.highlighted
                  ? 'border-blue-500 bg-[#1a2f4a] shadow-xl shadow-blue-500/20'
                  : 'border-gray-700 bg-[#1a2333]'
                }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-blue-500 text-white text-xs font-bold px-4 py-1 rounded-full">
                    הכי פופולרי
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h2 className="text-xl font-bold text-white mb-1">{tier.name}</h2>
                <p className="text-gray-400 text-sm mb-4">{tier.description}</p>
                <div className="text-3xl font-bold text-white">
                  {tier.price}
                  {tier.price !== 'חינם' && <span className="text-gray-400 text-base font-normal"> חד-פעמי</span>}
                </div>
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {tier.features.map(f => (
                  <li key={f} className="flex items-center gap-2 text-gray-300 text-sm">
                    <span className="text-green-400 text-base">✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleSelect(tier.id)}
                disabled={!!selecting}
                className={`w-full py-3 rounded-lg font-semibold transition
                  ${tier.highlighted
                    ? 'bg-blue-600 hover:bg-blue-500 text-white'
                    : 'bg-gray-700 hover:bg-gray-600 text-white'
                  } disabled:opacity-50`}
              >
                {selecting === tier.id ? 'בוחר...' : tier.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="text-center text-gray-600 text-sm mt-8">
          ניתן לשדרג בכל שלב. כל הנתונים שלך שמורים בבטחה.
        </p>
      </div>
    </div>
  )
}
