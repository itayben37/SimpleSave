import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getStorage } from 'firebase/storage'

import { FIREBASE_CONFIG, FIREBASE_ENABLED } from './env'

// Firebase is only initialized when credentials are present (real auth flow).
// In AUTH_BYPASS mode with no Firebase keys, these stay null and are never used,
// so the app runs without any Firebase project configured.
let app = null
let auth = null
let storage = null

if (FIREBASE_ENABLED) {
  app = initializeApp(FIREBASE_CONFIG)
  auth = getAuth(app)
  storage = getStorage(app)
}

export { auth, storage }
export default app
