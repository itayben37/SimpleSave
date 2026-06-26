import { createContext, useContext, useEffect, useState } from 'react'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import { auth } from '../config/firebase'
import { AUTH_BYPASS, AUTH_BYPASS_ROLE } from '../config/env'

const AuthContext = createContext(null)

// ─── DEV SANITY-CHECK TOGGLE ────────────────────────────────────────────────
// One switch controls registration/verification on BOTH ends:
//   frontend: VITE_AUTH_BYPASS=true   (frontend/.env.local)
//   backend:  AUTH_BYPASS=true        (backend/.env)
// When ON, the app skips the whole Firebase login/registration flow and signs
// you in as a dev user. Every protected page in every role is reachable, and
// the backend trusts an "Authorization: Bearer dev-<role>" token (no Firebase).
//
// Flip BOTH to false to restore the real phone/email OTP registration flow —
// no other code changes needed.
//
// While bypass is ON you can switch roles live from the navbar dropdown
// (stored in localStorage), so you don't even need to edit any file.
// ─────────────────────────────────────────────────────────────────────────────
const ENV_ROLE = AUTH_BYPASS_ROLE
const DEV_ROLE_KEY = 'dev_role'

const VALID_ROLES = ['client', 'advisor', 'admin']

function currentDevRole() {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(DEV_ROLE_KEY) : null
  return VALID_ROLES.includes(stored) ? stored : ENV_ROLE
}

function makeMockUser(role) {
  const names = { client: 'לקוח הדגמה', advisor: 'יועץ הדגמה', admin: 'מנהל הדגמה' }
  return {
    id: `dev-${role}`,
    full_name: names[role] || 'משתמש פיתוח',
    email: `dev-${role}@simplesave.local`,
    role,
    firebaseUid: `dev-${role}`,
    // Backend AUTH_BYPASS parses the role from this token.
    getToken: async () => `dev-${role}`,
  }
}

export function AuthProvider({ children }) {
  const [firebaseUser, setFirebaseUser] = useState(null)
  const [user, setUser] = useState(AUTH_BYPASS ? makeMockUser(currentDevRole()) : null)
  const [loading, setLoading] = useState(!AUTH_BYPASS)

  useEffect(() => {
    if (AUTH_BYPASS) return // skip Firebase entirely in bypass mode

    const unsub = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser)
      if (fbUser) {
        try {
          const token = await fbUser.getIdToken()
          const res = await fetch('/api/auth/sync', {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          })
          if (res.ok) {
            const data = await res.json()
            setUser({ ...data, firebaseUid: fbUser.uid, getToken: () => fbUser.getIdToken() })
          } else {
            setUser(null)
          }
        } catch {
          setUser(null)
        }
      } else {
        setUser(null)
      }
      setLoading(false)
    })
    return unsub
  }, [])

  // Dev-only: switch role live (persists to localStorage, then reloads).
  const setDevRole = (role) => {
    if (!AUTH_BYPASS || !VALID_ROLES.includes(role)) return
    localStorage.setItem(DEV_ROLE_KEY, role)
    window.location.assign('/')
  }

  const logout = async () => {
    if (AUTH_BYPASS) return // nothing to sign out of in bypass mode
    await signOut(auth)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ firebaseUser, user, loading, bypass: AUTH_BYPASS, setDevRole, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
