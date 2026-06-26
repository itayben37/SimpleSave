import { describe, it, expect } from 'vitest'
import {
  defaultTrack, fromApiTrack, toApiTrack, normalizeForType,
  effectiveRate, samplePayment, mixTotal, mixBalanced, validateTrack,
} from '../mixLogic'

describe('mixLogic conversions', () => {
  it('round-trips a track through API units (percent <-> fraction)', () => {
    const api = {
      track_type: 'variable', cpi_linked: true, period_years: 10,
      rate_change_interval_months: 60, amortization_type: 'spitzer',
      percentage_of_mix: 30, anchor_rate: 0.04, spread: 0.01,
    }
    const display = fromApiTrack(api)
    expect(display.anchor_rate).toBeCloseTo(4)   // 0.04 -> 4%
    expect(display.spread).toBeCloseTo(1)        // 0.01 -> 1%
    const back = toApiTrack(display)
    expect(back.anchor_rate).toBeCloseTo(0.04)
    expect(back.spread).toBeCloseTo(0.01)
    expect(back.rate_change_interval_months).toBe(60)
  })

  it('forces prime to be non-linked with no margin reset, and fixed to zero margin', () => {
    const fixed = toApiTrack({ ...defaultTrack(), track_type: 'fixed', spread: 5 })
    expect(fixed.spread).toBe(0)
    const prime = toApiTrack({ ...defaultTrack(), track_type: 'prime', cpi_linked: true })
    expect(prime.cpi_linked).toBe(false)
    expect(prime.rate_change_interval_months).toBe(null)
  })
})

describe('normalizeForType', () => {
  it('sources the prime anchor from the system prime rate and drops cpi/interval', () => {
    const t = normalizeForType({ ...defaultTrack(), cpi_linked: true }, 6.25)
    const p = normalizeForType({ ...t, track_type: 'prime' }, 6.25)
    expect(p.cpi_linked).toBe(false)
    expect(p.anchor_rate).toBe(6.25)
    expect(p.rate_change_interval_months).toBe(null)
  })
  it('bumps a variable track to a valid minimum term + default interval', () => {
    const v = normalizeForType({ ...defaultTrack(), period_years: 4 }, 6.25)
    const out = normalizeForType({ ...v, track_type: 'variable' }, 6.25)
    expect(out.period_years).toBeGreaterThanOrEqual(6)
    expect(out.rate_change_interval_months).toBe(60)
  })
})

describe('effective rate + mix totals', () => {
  it('fixed ignores margin; variable adds margin', () => {
    expect(effectiveRate({ track_type: 'fixed', anchor_rate: 4.5, spread: 2 })).toBe(4.5)
    expect(effectiveRate({ track_type: 'variable', anchor_rate: 4, spread: 1 })).toBe(5)
  })
  it('detects a balanced (100%) mix', () => {
    const tracks = [{ percentage_of_mix: 60 }, { percentage_of_mix: 40 }]
    expect(mixTotal(tracks)).toBe(100)
    expect(mixBalanced(tracks)).toBe(true)
    expect(mixBalanced([{ percentage_of_mix: 60 }, { percentage_of_mix: 30 }])).toBe(false)
  })
})

describe('samplePayment', () => {
  it('computes a sane Spitzer payment on the 1M reference loan', () => {
    // 5% / 20y Spitzer on 1,000,000 ≈ ₪6,600/mo
    const pay = samplePayment({ track_type: 'fixed', anchor_rate: 5, spread: 0, period_years: 20, amortization_type: 'spitzer' })
    expect(pay).toBeGreaterThan(6400)
    expect(pay).toBeLessThan(6800)
  })
  it('equal-principal first month is higher than spitzer for the same inputs', () => {
    const base = { track_type: 'fixed', anchor_rate: 5, spread: 0, period_years: 20 }
    const sp = samplePayment({ ...base, amortization_type: 'spitzer' })
    const ks = samplePayment({ ...base, amortization_type: 'equal_principal' })
    expect(ks).toBeGreaterThan(sp)
  })
})

describe('validateTrack', () => {
  it('passes a valid fixed track', () => {
    expect(validateTrack({ track_type: 'fixed', period_years: 20, percentage_of_mix: 100, anchor_rate: 4.5 })).toEqual({})
  })
  it('flags a variable term that is not a multiple of the interval', () => {
    const errs = validateTrack({ track_type: 'variable', period_years: 10, rate_change_interval_months: 36, percentage_of_mix: 50, anchor_rate: 4 })
    expect(errs.period_years).toBeTruthy() // 10 is not a multiple of 3
  })
  it('flags an out-of-range term and a zero percentage', () => {
    const errs = validateTrack({ track_type: 'fixed', period_years: 2, percentage_of_mix: 0, anchor_rate: 4 })
    expect(errs.period_years).toBeTruthy()
    expect(errs.percentage_of_mix).toBeTruthy()
  })
})
