import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// The tab schedules a debounced auto-save that calls apiFetch — mock it so the
// render/input test never touches the network.
vi.mock('../../utils/api', () => ({ apiFetch: vi.fn().mockResolvedValue({}) }))

import { PersonalDetailsTab } from '../PersonalArea'

// Minimal application shape as returned by GET /api/applications/me.
function makeApp(overrides = {}) {
  return {
    application_id: 'app-test-1',
    status: 'PERSONAL_DETAILS_COMPLETE',
    tier: 'online_guidance',
    borrowers: [
      {
        id: 'borrower-1',
        sequence_number: 1,
        first_name: 'יוסי',
        last_name: 'כהן',
        gender: 'male',
        marital_status: 'married',
        education: 'bachelor',
        employment_status: 'employee',
        num_children: 2,
        net_income: 22000,
        phone: '050-1234567',
        email: 'yossi@example.com',
        ...overrides,
      },
    ],
  }
}

describe('PersonalDetailsTab (אזור אישי — נתונים אישיים)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders every PRD section heading', () => {
    render(<PersonalDetailsTab app={makeApp()} token="dev-client" onSaved={() => {}} />)
    for (const heading of [
      'פרטים בסיסיים',
      'פרטי קשר וכתובת',
      'תעסוקה והכנסה',
      'רגולציה ובריאות',
      'זכאות דירה ראשונה',
    ]) {
      expect(screen.getByText(heading)).toBeInTheDocument()
    }
  })

  it('shows the existing borrower values from the server', () => {
    render(<PersonalDetailsTab app={makeApp()} token="dev-client" onSaved={() => {}} />)
    expect(screen.getByDisplayValue('יוסי')).toBeInTheDocument()
    expect(screen.getByDisplayValue('כהן')).toBeInTheDocument()
    expect(screen.getByDisplayValue('yossi@example.com')).toBeInTheDocument()
  })

  it('renders dropdowns (select) for choice fields like מין', () => {
    render(<PersonalDetailsTab app={makeApp()} token="dev-client" onSaved={() => {}} />)
    // gender select is pre-set to "male" → option "זכר" is selected
    expect(screen.getByDisplayValue('זכר')).toBeInTheDocument()
  })

  it('accepts text input without crashing', async () => {
    const user = userEvent.setup()
    render(<PersonalDetailsTab app={makeApp()} token="dev-client" onSaved={() => {}} />)
    const firstName = screen.getByDisplayValue('יוסי')
    await user.clear(firstName)
    await user.type(firstName, 'דוד')
    expect(screen.getByDisplayValue('דוד')).toBeInTheDocument()
  })

  it('renders a friendly message when there is no borrower yet', () => {
    render(<PersonalDetailsTab app={{ application_id: 'x', borrowers: [] }} token="dev-client" onSaved={() => {}} />)
    expect(screen.getByText('לא נמצאו פרטי לווה.')).toBeInTheDocument()
  })
})
