import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// ── Firebase mocks ────────────────────────────────────────────────────────────
const mockSendSignInLinkToEmail = vi.fn()
const mockSignInWithEmailLink = vi.fn()
const mockIsSignInWithEmailLink = vi.fn()

vi.mock('firebase/auth', () => ({
  RecaptchaVerifier: vi.fn(),
  signInWithPhoneNumber: vi.fn(),
  sendSignInLinkToEmail: (...args) => mockSendSignInLinkToEmail(...args),
  signInWithEmailLink: (...args) => mockSignInWithEmailLink(...args),
  isSignInWithEmailLink: (...args) => mockIsSignInWithEmailLink(...args),
}))

vi.mock('../config/firebase', () => ({ auth: {} }))

// ── Router mock ───────────────────────────────────────────────────────────────
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => mockNavigate }
})

// ── AuthContext mock (not logged in) ──────────────────────────────────────────
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false }),
}))

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('Login — email magic-link', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    localStorage.clear()
    mockIsSignInWithEmailLink.mockReturnValue(false)
    mockSendSignInLinkToEmail.mockResolvedValue(undefined)
    mockSignInWithEmailLink.mockResolvedValue({ user: { uid: 'u1' } })
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost:5173/login', origin: 'http://localhost:5173' },
      writable: true,
      configurable: true,
    })
  })

  it('uses VITE_APP_URL (not window.location.origin) as continueUrl', async () => {
    vi.stubEnv('VITE_APP_URL', 'https://simplesave-72258.web.app')

    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    fireEvent.click(screen.getByText('מייל'))
    fireEvent.change(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'test@example.com' },
    })
    fireEvent.click(screen.getByText('שלח קוד אימות'))

    await waitFor(() => expect(mockSendSignInLinkToEmail).toHaveBeenCalled())

    const [, , actionCodeSettings] = mockSendSignInLinkToEmail.mock.calls[0]
    expect(actionCodeSettings.url).toBe('https://simplesave-72258.web.app/login')
    expect(actionCodeSettings.url).not.toContain('localhost')

    vi.unstubAllEnvs()
  })

  it('falls back to window.location.origin when VITE_APP_URL is not set', async () => {
    vi.stubEnv('VITE_APP_URL', '')
    Object.defineProperty(window, 'location', {
      value: { href: 'https://simplesave-72258.web.app/login', origin: 'https://simplesave-72258.web.app' },
      writable: true,
      configurable: true,
    })

    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    fireEvent.click(screen.getByText('מייל'))
    fireEvent.change(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'test@example.com' },
    })
    fireEvent.click(screen.getByText('שלח קוד אימות'))

    await waitFor(() => expect(mockSendSignInLinkToEmail).toHaveBeenCalled())

    const [, , actionCodeSettings] = mockSendSignInLinkToEmail.mock.calls[0]
    expect(actionCodeSettings.url).toBe('https://simplesave-72258.web.app/login')

    vi.unstubAllEnvs()
  })

  it('stores email in localStorage after sending link', async () => {
    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    fireEvent.click(screen.getByText('מייל'))
    fireEvent.change(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'gilad@example.com' },
    })
    fireEvent.click(screen.getByText('שלח קוד אימות'))

    await waitFor(() => expect(mockSendSignInLinkToEmail).toHaveBeenCalled())
    expect(localStorage.getItem('simplesave_email_for_signin')).toBe('gilad@example.com')
  })

  it('shows confirmation message after link is sent', async () => {
    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    fireEvent.click(screen.getByText('מייל'))
    fireEvent.change(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'gilad@example.com' },
    })
    fireEvent.click(screen.getByText('שלח קוד אימות'))

    await waitFor(() => screen.getByText(/קישור אימות נשלח/))
  })
})

describe('Login — email link callback (regression: double sign-in)', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    localStorage.clear()
    localStorage.setItem('simplesave_email_for_signin', 'gilad@example.com')
    mockSignInWithEmailLink.mockResolvedValue({ user: { uid: 'u1' } })
    Object.defineProperty(window, 'location', {
      value: {
        href: 'http://localhost:5173/login?apiKey=key&oobCode=abc&mode=signIn&lang=en',
        origin: 'http://localhost:5173',
      },
      writable: true,
      configurable: true,
    })
    mockIsSignInWithEmailLink.mockReturnValue(true)
  })

  it('calls signInWithEmailLink exactly once even when the component re-renders', async () => {
    const { default: Login } = await import('../pages/Login.jsx')
    const { rerender } = render(<MemoryRouter><Login /></MemoryRouter>)

    // Simulate a re-render triggered by AuthContext updating (loading: true → false)
    rerender(<MemoryRouter><Login /></MemoryRouter>)

    await waitFor(() => expect(mockSignInWithEmailLink).toHaveBeenCalledTimes(1))
  })

  it('navigates to / after successful email link sign-in', async () => {
    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }))
  })

  it('shows error when sign-in link is invalid or expired', async () => {
    mockSignInWithEmailLink.mockRejectedValue(new Error('invalid-action-code'))
    const { default: Login } = await import('../pages/Login.jsx')
    render(<MemoryRouter><Login /></MemoryRouter>)

    await waitFor(() => screen.getByText(/אימות הקישור נכשל/))
  })
})
