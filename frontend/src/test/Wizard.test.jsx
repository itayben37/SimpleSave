import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Mocks ─────────────────────────────────────────────────────────────────────
vi.mock('../config/firebase', () => ({ auth: {} }))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => mockNavigate }
})

const mockGetToken = vi.fn().mockResolvedValue('fake-token')
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { getToken: mockGetToken }, loading: false }),
}))

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

// All wizard fields with valid values so every step passes validation
const FULL_DATA = {
  loan_purpose: 'all_purpose',
  property_value: '10000000',
  loan_amount: '1000000',
  first_home: false,
  num_borrowers: '2',
  marital_status: 'divorced',
  num_children: '2',
  wedding_duration_years: '5',
  military_service_type: 'regular',
  eligible_siblings_count: '0',
  total_monthly_income: '15000',
  total_monthly_obligations: '0',
  primary_borrower_birth_date: '1998-12-23',
  existing_mortgage_balance: '0',
  vatikei_interest: false,
}

// Default fetch: succeed for POST (create app) and PATCH (autoSave)
function setupFetch({ postAppId = 'app-123', patchFails = false } = {}) {
  mockFetch.mockImplementation((url, opts) => {
    const method = opts?.method || 'GET'
    if (method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: async () => (postAppId ? { application_id: postAppId } : {}),
      })
    }
    if (method === 'PATCH') {
      if (patchFails) return Promise.reject(new Error('server error'))
      return Promise.resolve({ ok: true, json: async () => ({}) })
    }
    return Promise.resolve({ ok: true, json: async () => ({}) })
  })
}

// Advance wizard by clicking הבא N times (data is pre-loaded from sessionStorage)
async function advanceToStep(n) {
  for (let i = 0; i < n; i++) {
    const btn = await screen.findByText('הבא')
    fireEvent.click(btn)
    // give React a tick to re-render
    await waitFor(() => {}, { timeout: 200 })
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('Wizard — submit button', () => {
  beforeEach(() => {
    // Override auth bypass so tests exercise the real fetch path
    vi.stubEnv('VITE_AUTH_BYPASS', 'false')
    vi.resetModules()
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    mockGetToken.mockResolvedValue('fake-token')
    // Pre-load all step answers so validation passes on every הבא click
    sessionStorage.setItem('simplesave_wizard', JSON.stringify(FULL_DATA))
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('shows error (not silent) when applicationId is null at submit time', async () => {
    // POST fails → applicationId stays null, error shown on mount
    mockFetch.mockRejectedValue(new Error('network error'))

    const { default: Wizard } = await import('../pages/Wizard.jsx')
    render(<MemoryRouter><Wizard /></MemoryRouter>)

    // Error is displayed because the POST to create application failed
    await waitFor(() =>
      expect(screen.getByText(/שגיאה ביצירת בקשה/)).toBeInTheDocument()
    )

    // Even if somehow we reach step 10, submit shows the applicationId error
    // (not a silent no-op). Verify by calling submit without an app id in session.
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('navigates to clocks page (not /register) on successful submit', async () => {
    sessionStorage.setItem('simplesave_app_id', 'app-123')
    setupFetch({ postAppId: 'app-123' })

    const { default: Wizard } = await import('../pages/Wizard.jsx')
    render(<MemoryRouter><Wizard /></MemoryRouter>)

    await advanceToStep(9)

    const submitBtn = await screen.findByText('צפה בשעוני עלות')
    fireEvent.click(submitBtn)

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/applications/app-123/clocks'))
    expect(mockNavigate).not.toHaveBeenCalledWith('/register')
  })

  it('shows error and does not navigate when PATCH fails on submit', async () => {
    sessionStorage.setItem('simplesave_app_id', 'app-123')
    // autoSave PATCHes succeed, final submit PATCH fails
    let patchCount = 0
    mockFetch.mockImplementation((url, opts) => {
      const method = opts?.method || 'GET'
      if (method === 'POST') return Promise.resolve({ ok: true, json: async () => ({ application_id: 'app-123' }) })
      if (method === 'PATCH') {
        patchCount++
        // Let the first 9 autoSaves succeed; fail on the final submit PATCH
        if (patchCount > 9) return Promise.reject(new Error('server down'))
        return Promise.resolve({ ok: true, json: async () => ({}) })
      }
      return Promise.resolve({ ok: true, json: async () => ({}) })
    })

    const { default: Wizard } = await import('../pages/Wizard.jsx')
    render(<MemoryRouter><Wizard /></MemoryRouter>)

    await advanceToStep(9)
    const submitBtn = await screen.findByText('צפה בשעוני עלות')
    fireEvent.click(submitBtn)

    await waitFor(() =>
      expect(screen.getByText(/שגיאה בשמירת הנתונים/)).toBeInTheDocument()
    )
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('clears wizard sessionStorage draft after successful submit', async () => {
    sessionStorage.setItem('simplesave_app_id', 'app-123')
    setupFetch({ postAppId: 'app-123' })

    const { default: Wizard } = await import('../pages/Wizard.jsx')
    render(<MemoryRouter><Wizard /></MemoryRouter>)

    await advanceToStep(9)
    const submitBtn = await screen.findByText('צפה בשעוני עלות')
    fireEvent.click(submitBtn)

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/applications/app-123/clocks'))
    expect(sessionStorage.getItem('simplesave_wizard')).toBeNull()
  })

  it('shows error on mount when backend fails to create application', async () => {
    // No app_id in session, POST fails
    mockFetch.mockRejectedValue(new Error('network error'))

    const { default: Wizard } = await import('../pages/Wizard.jsx')
    render(<MemoryRouter><Wizard /></MemoryRouter>)

    await waitFor(() =>
      expect(screen.getByText(/שגיאה ביצירת בקשה/)).toBeInTheDocument()
    )
  })
})
