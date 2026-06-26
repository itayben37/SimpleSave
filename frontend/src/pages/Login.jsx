import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import {
  RecaptchaVerifier,
  signInWithPhoneNumber,
  signInWithEmailLink,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
} from 'firebase/auth'
import { auth } from '../config/firebase'
import { useAuth } from '../context/AuthContext'

const EMAIL_STORAGE_KEY = 'simplesave_email_for_signin'

export default function Login() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [channel, setChannel] = useState('phone') // 'phone' | 'email'
  const [value, setValue] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otp, setOtp] = useState('')
  const [confirmationResult, setConfirmationResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Redirect if already logged in
  if (user) {
    if (user.role === 'admin') navigate('/admin', { replace: true })
    else if (user.role === 'advisor') navigate('/advisor', { replace: true })
    else navigate('/personal', { replace: true })
  }

  // ── Phone OTP flow ──
  const sendPhoneOtp = async () => {
    setError('')
    setLoading(true)
    try {
      if (!window.recaptchaVerifier) {
        window.recaptchaVerifier = new RecaptchaVerifier(auth, 'recaptcha-container', {
          size: 'invisible',
        })
      }
      const result = await signInWithPhoneNumber(auth, value, window.recaptchaVerifier)
      setConfirmationResult(result)
      setOtpSent(true)
    } catch (e) {
      setError('שליחת הקוד נכשלה. בדוק את מספר הטלפון ונסה שנית.')
    } finally {
      setLoading(false)
    }
  }

  const verifyPhoneOtp = async () => {
    setError('')
    setLoading(true)
    try {
      await confirmationResult.confirm(otp)
      navigate('/', { replace: true })
    } catch {
      setError('הקוד שגוי או פג תוקפו. נסה שנית.')
    } finally {
      setLoading(false)
    }
  }

  // ── Email magic-link flow ──
  const sendEmailLink = async () => {
    setError('')
    setLoading(true)
    try {
      const appUrl = import.meta.env.VITE_APP_URL || window.location.origin
      await sendSignInLinkToEmail(auth, value, {
        url: appUrl + '/login',
        handleCodeInApp: true,
      })
      localStorage.setItem(EMAIL_STORAGE_KEY, value)
      setOtpSent(true)
    } catch {
      setError('שליחת הקישור נכשלה. בדוק את כתובת המייל ונסה שנית.')
    } finally {
      setLoading(false)
    }
  }

  // Handle returning from email link
  const handleEmailLink = async () => {
    if (isSignInWithEmailLink(auth, window.location.href)) {
      const email = localStorage.getItem(EMAIL_STORAGE_KEY) || prompt('הזן את כתובת המייל שלך לאימות')
      if (!email) return
      try {
        await signInWithEmailLink(auth, email, window.location.href)
        localStorage.removeItem(EMAIL_STORAGE_KEY)
        navigate('/', { replace: true })
      } catch {
        setError('אימות הקישור נכשל. נסה לבקש קישור חדש.')
      }
    }
  }

  // Auto-handle email link on mount (useEffect prevents re-calling on re-renders)
  useEffect(() => {
    if (isSignInWithEmailLink(auth, window.location.href)) {
      handleEmailLink()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = () => (channel === 'phone' ? sendPhoneOtp() : sendEmailLink())
  const handleVerify = () => (channel === 'phone' ? verifyPhoneOtp() : null)

  return (
    <main className="min-h-screen bg-slate-50" dir="rtl">
      <Navbar />
      <div className="flex items-center justify-center px-4 py-16">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8 w-full max-w-sm">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">כניסה ל-SimpleSave</h1>
        <p className="text-sm text-slate-500 mb-6">ללא סיסמה — נשלח לך קוד אימות</p>

        {/* Channel toggle */}
        <div className="flex rounded-lg border border-slate-200 overflow-hidden mb-4">
          {['phone', 'email'].map((c) => (
            <button
              key={c}
              onClick={() => { setChannel(c); setOtpSent(false); setError('') }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                channel === c ? 'bg-brand text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {c === 'phone' ? 'טלפון' : 'מייל'}
            </button>
          ))}
        </div>

        {!otpSent ? (
          <>
            <input
              type={channel === 'phone' ? 'tel' : 'email'}
              placeholder={channel === 'phone' ? '+972-50-0000000' : 'name@example.com'}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-brand"
              dir="ltr"
            />
            <button
              onClick={handleSend}
              disabled={loading || !value}
              className="w-full bg-brand text-white rounded-lg py-2.5 font-semibold text-sm hover:bg-brand-hover disabled:opacity-50 transition-colors"
            >
              {loading ? 'שולח...' : 'שלח קוד אימות'}
            </button>
          </>
        ) : channel === 'phone' ? (
          <>
            <p className="text-sm text-slate-600 mb-3">קוד נשלח ל-{value}</p>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
              className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm mb-4 text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-brand"
              dir="ltr"
            />
            <button
              onClick={handleVerify}
              disabled={loading || otp.length !== 6}
              className="w-full bg-brand text-white rounded-lg py-2.5 font-semibold text-sm hover:bg-brand-hover disabled:opacity-50 transition-colors"
            >
              {loading ? 'מאמת...' : 'אמת קוד'}
            </button>
          </>
        ) : (
          <p className="text-sm text-slate-600 text-center py-2">
            קישור אימות נשלח ל-{value}.<br />בדוק את תיבת המייל שלך.
          </p>
        )}

        {error && <p className="text-error text-sm mt-3 text-center">{error}</p>}

        <div id="recaptcha-container" />
      </div>
      </div>
    </main>
  )
}
