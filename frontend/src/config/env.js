// ─────────────────────────────────────────────────────────────────────────────
// SINGLE SOURCE OF TRUTH for environment / deploy configuration.
//
// To move from localhost → deploy you only touch ONE place: the Vite env file
// (frontend/.env.local for dev, frontend/.env.production for the deployed build).
// Every value below is read from import.meta.env so nothing in the code is
// hard-coded to localhost.
//
//   Local dev          (frontend/.env.local):
//     VITE_API_URL=http://localhost:8000
//     VITE_AUTH_BYPASS=true            ← skip registration while building
//
//   Deploy             (frontend/.env.production):
//     VITE_API_URL=https://api.your-domain.com
//     VITE_AUTH_BYPASS=false           ← real Firebase OTP registration
//     + the six VITE_FIREBASE_* keys
//
// IMPORTANT: keep AUTH_BYPASS in sync with the backend AUTH_BYPASS flag
// (backend/.env). Both true = no registration; both false = real auth.
// ─────────────────────────────────────────────────────────────────────────────

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Dev sanity-check: when true the app skips Firebase login/registration entirely.
export const AUTH_BYPASS = import.meta.env.VITE_AUTH_BYPASS === 'true'

// Default role when bypass is on and no role was chosen in the navbar dropdown.
export const AUTH_BYPASS_ROLE = import.meta.env.VITE_AUTH_BYPASS_ROLE || 'client'

// Firebase is only needed for the real auth flow (AUTH_BYPASS=false).
export const FIREBASE_CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

// True only when we actually have Firebase credentials to initialize with.
export const FIREBASE_ENABLED = Boolean(FIREBASE_CONFIG.apiKey)
