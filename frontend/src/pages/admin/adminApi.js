// Admin API layer — thin wrappers over apiFetch for every /api/admin endpoint
// the manager area uses. Keeps network concerns out of the .jsx components.
import { apiFetch } from '../../utils/api'

export const getMixes = (token) => apiFetch('/api/admin/mixes', { token })

export const saveMix = (token, mixId, body) =>
  apiFetch(`/api/admin/mixes/${mixId}`, { token, method: 'PUT', body })

export const getSystemParameters = (token) =>
  apiFetch('/api/admin/system-parameters', { token })

export const getRecalcAffectedCount = (token) =>
  apiFetch('/api/admin/recalculate/affected-count', { token })

export const triggerRecalculation = (token) =>
  apiFetch('/api/admin/recalculate', { token, method: 'POST', body: {} })
