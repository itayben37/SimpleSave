// Thin fetch wrapper: prefixes the API base URL and attaches the auth token.
import { API_URL as API } from '../config/env'

export async function apiFetch(path, { token, method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${text}`)
  }
  if (res.status === 204) return null
  return res.json()
}

// Multipart upload (FormData) — used for real document file uploads. Does NOT
// set Content-Type so the browser adds the correct multipart boundary.
export async function apiUpload(path, { token, file, method = 'POST' } = {}) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}${path}`, { method, headers, body: form })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

// Fetch a protected file with the auth header and open it in a new tab.
// (A plain <a href> can't attach the bearer token, so we stream a blob.)
export async function openProtectedFile(path, { token } = {}) {
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API}${path}`, { headers })
  if (!res.ok) throw new Error(`${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  // Revoke a bit later so the new tab has time to load it.
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}
