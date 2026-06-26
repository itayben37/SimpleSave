// Mix / Tracks Manager — pure domain logic (no JSX, no DOM).
// Track state in this module is held in *display units*: rates as percentages
// (e.g. 3.5 means 3.5%). Conversion to the API's fractional units (0.035)
// happens only at the API boundary (fromApiTrack / toApiTrack).

export const TRACK_TYPES = [
  { value: 'fixed', label: 'קבועה' },
  { value: 'variable', label: 'משתנה' },
  { value: 'prime', label: 'פריים' },
]

export const AMORT_METHODS = [
  { value: 'spitzer', label: 'שפיצר' },
  { value: 'equal_principal', label: 'קרן שווה' },
]

// Variable-rate change frequency, stored on the model as months.
export const CHANGE_INTERVALS = [
  { value: 36, label: 'כל 3 שנים' },
  { value: 60, label: 'כל 5 שנים' },
]

export const SAMPLE_PRINCIPAL = 1_000_000
export const MIN_TERM = 4
export const MAX_TERM = 30
export const MAX_TRACKS = 10
export const HIGH_RATE_WARN = 15 // percent

export const trackTypeLabel = (v) => TRACK_TYPES.find((t) => t.value === v)?.label || v

// ── Defaults ────────────────────────────────────────────────────────────────
export function defaultTrack() {
  return {
    track_type: 'fixed',
    cpi_linked: false,
    period_years: 20,
    rate_change_interval_months: null,
    amortization_type: 'spitzer',
    percentage_of_mix: 0,
    anchor_rate: 3.5, // percent
    spread: 0, // percent
  }
}

// ── API <-> display conversion ───────────────────────────────────────────────
const pct = (frac) => (frac == null ? null : Math.round(frac * 1000000) / 10000) // 0.035 -> 3.5
const frac = (p) => (p == null || p === '' ? null : Number(p) / 100) // 3.5 -> 0.035

export function fromApiTrack(t) {
  return {
    track_type: t.track_type,
    cpi_linked: !!t.cpi_linked,
    period_years: t.period_years,
    rate_change_interval_months: t.rate_change_interval_months ?? null,
    amortization_type: t.amortization_type,
    percentage_of_mix: Number(t.percentage_of_mix),
    anchor_rate: pct(t.anchor_rate) ?? 0,
    spread: pct(t.spread) ?? 0,
  }
}

export function toApiTrack(t) {
  return {
    track_type: t.track_type,
    cpi_linked: t.track_type === 'prime' ? false : !!t.cpi_linked,
    period_years: Number(t.period_years),
    rate_change_interval_months:
      t.track_type === 'variable' ? Number(t.rate_change_interval_months) : null,
    amortization_type: t.amortization_type,
    percentage_of_mix: Number(t.percentage_of_mix),
    anchor_rate: frac(t.anchor_rate),
    spread: t.track_type === 'fixed' ? 0 : frac(t.spread),
  }
}

// ── Type-driven normalization (run whenever interest_type changes) ────────────
export function normalizeForType(track, primeRatePct) {
  const t = { ...track }
  if (t.track_type === 'prime') {
    t.cpi_linked = false
    t.rate_change_interval_months = null
    t.anchor_rate = primeRatePct // read-only, sourced from the prime parameter
  } else if (t.track_type === 'fixed') {
    t.rate_change_interval_months = null
    t.spread = 0
  } else if (t.track_type === 'variable') {
    if (t.rate_change_interval_months == null) t.rate_change_interval_months = 60
    if (t.period_years < 6) t.period_years = 6
  }
  return t
}

// ── Computed values ───────────────────────────────────────────────────────────
export function effectiveRate(track) {
  const anchor = Number(track.anchor_rate) || 0
  const spread = track.track_type === 'fixed' ? 0 : Number(track.spread) || 0
  return anchor + spread // percent
}

// Monthly payment on a reference loan. Spitzer = constant payment;
// Keren Shava (equal principal) = highest (first-month) payment.
export function samplePayment(track, principal = SAMPLE_PRINCIPAL) {
  const years = Number(track.period_years)
  const annual = effectiveRate(track) / 100
  const n = years * 12
  if (!n || n <= 0 || !Number.isFinite(annual)) return null
  const r = annual / 12
  if (track.amortization_type === 'equal_principal') {
    return principal / n + principal * r // first month
  }
  if (r < 1e-9) return principal / n
  const f = Math.pow(1 + r, n)
  return (principal * r * f) / (f - 1)
}

export function mixTotal(tracks) {
  return Math.round(tracks.reduce((s, t) => s + (Number(t.percentage_of_mix) || 0), 0) * 100) / 100
}

export const mixBalanced = (tracks) => mixTotal(tracks) === 100

// ── Validation ────────────────────────────────────────────────────────────────
// Returns a map { fieldName: messageHe } for one track (empty when valid).
export function validateTrack(track) {
  const errs = {}
  const term = Number(track.period_years)
  if (!Number.isInteger(term) || term < MIN_TERM || term > MAX_TERM) {
    errs.period_years = `תקופה ${MIN_TERM}–${MAX_TERM} שנים`
  }
  const p = Number(track.percentage_of_mix)
  if (!(p > 0) || p > 100) errs.percentage_of_mix = 'אחוז 0.1–100'

  if (track.track_type === 'variable') {
    const interval = Number(track.rate_change_interval_months)
    if (![36, 60].includes(interval)) {
      errs.rate_change_interval_months = 'בחר תדירות'
    } else {
      const iy = interval / 12
      if (term < 6) errs.period_years = 'משתנה: לפחות 6 שנים'
      else if (term % iy !== 0) errs.period_years = `חייב כפולה של ${iy}`
    }
  }
  if (track.track_type !== 'prime') {
    const a = Number(track.anchor_rate)
    if (!(a > 0) || a > 25) errs.anchor_rate = 'עוגן 0.01–25%'
  }
  return errs
}

export function formatILS(n) {
  if (n == null || !Number.isFinite(n)) return '—'
  return '₪' + Math.round(n).toLocaleString('he-IL')
}
