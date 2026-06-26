// ─────────────────────────────────────────────────────────────────────────────
// CENTRALIZED TEST-MODE GATE
//
// Every place that BLOCKS navigation or REJECTS input must route through one of
// these helpers instead of deciding on its own. That way the single env flag
// VITE_TEST_MODE (see config/env.js) flips the whole app between:
//
//   TEST_MODE = true   → unrestricted: no locked tabs, validation always passes
//   TEST_MODE = false  → production: real lifecycle/tier locks + real validation
//
// To return to strict production behavior you change ONE variable; you never
// touch the call sites. New tabs/forms just call tabLocked()/validateField()
// and inherit the toggle automatically.
// ─────────────────────────────────────────────────────────────────────────────

import { TEST_MODE } from '../config/env'

export { TEST_MODE }

/**
 * Gate a tab-lock decision.
 * @param {boolean} realLocked - what the production rule says (true = locked)
 * @returns {boolean} false in test mode, otherwise the real decision
 */
export function tabLocked(realLocked) {
  return TEST_MODE ? false : Boolean(realLocked)
}

/**
 * Gate a single-field validator.
 * @param {(value:any)=>(string|null)} validator - returns an error string or null
 * @returns {(value:any)=>(string|null)} in test mode always returns null (valid)
 */
export function validateField(validator) {
  return (value) => (TEST_MODE ? null : validator(value))
}

/**
 * Gate a whole-form validation result.
 * @param {() => Record<string,string>} runValidation - returns {field: error}
 * @returns {Record<string,string>} empty object in test mode
 */
export function validateForm(runValidation) {
  return TEST_MODE ? {} : runValidation()
}

/**
 * Gate a "can advance to next step / submit" decision.
 * @param {boolean} realCanProceed
 * @returns {boolean} true in test mode, otherwise the real decision
 */
export function canProceed(realCanProceed) {
  return TEST_MODE ? true : Boolean(realCanProceed)
}
