import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '../../context/AuthContext'
import {
  getMixes, saveMix, getSystemParameters,
  getRecalcAffectedCount, triggerRecalculation,
} from './adminApi'
import {
  TRACK_TYPES, AMORT_METHODS, CHANGE_INTERVALS, MAX_TRACKS, HIGH_RATE_WARN,
  defaultTrack, fromApiTrack, toApiTrack, normalizeForType,
  effectiveRate, samplePayment, mixTotal, mixBalanced, validateTrack, formatILS,
} from './mixLogic'

const snapshot = (mix) => JSON.stringify({ name: mix.name, tracks: mix.tracks })

export default function MixManager() {
  const { user } = useAuth()
  const tokenRef = useRef(null)

  const [mixes, setMixes] = useState([])
  const [primeRatePct, setPrimeRatePct] = useState(6.25)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [expanded, setExpanded] = useState({})
  const [confirmDel, setConfirmDel] = useState(null) // { mixId, index }
  const [saving, setSaving] = useState(null)
  const [toast, setToast] = useState(null)

  const [recalcOpen, setRecalcOpen] = useState(false)
  const [recalcCount, setRecalcCount] = useState(null)
  const [recalcBusy, setRecalcBusy] = useState(false)

  const showToast = useCallback((msg, kind = 'ok') => {
    setToast({ msg, kind })
    setTimeout(() => setToast(null), 4000)
  }, [])

  const load = useCallback(async () => {
    if (!user) return
    const token = await user.getToken()
    tokenRef.current = token
    try {
      const [mixData, paramData] = await Promise.all([
        getMixes(token),
        getSystemParameters(token).catch(() => ({ parameters: [] })),
      ])
      const prime = (paramData.parameters || []).find((p) => p.key === 'prime_rate')
      const primePct = prime ? prime.value * 100 : 6.25
      setPrimeRatePct(primePct)
      const loaded = mixData.mixes.map((m) => {
        const tracks = m.tracks.map((t) =>
          t.track_type === 'prime'
            ? { ...fromApiTrack(t), anchor_rate: primePct }
            : fromApiTrack(t),
        )
        const mix = { id: m.id, clock_number: m.clock_number, name: m.name, risk_level: m.risk_level, tracks }
        mix._saved = snapshot(mix)
        return mix
      })
      setMixes(loaded)
      if (loaded.length) setExpanded({ [loaded[0].id]: true })
    } catch (e) {
      setError('שגיאה בטעינת השעונים')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { load() }, [load])

  // ── mutators ────────────────────────────────────────────────────────────
  const patchMix = (mixId, fn) =>
    setMixes((prev) => prev.map((m) => (m.id === mixId ? fn(m) : m)))

  const setTracks = (mixId, tracks) => patchMix(mixId, (m) => ({ ...m, tracks }))

  const updateTrack = (mixId, idx, patch) =>
    patchMix(mixId, (m) => ({
      ...m,
      tracks: m.tracks.map((t, i) => (i === idx ? { ...t, ...patch } : t)),
    }))

  const changeType = (mixId, idx, track_type) =>
    patchMix(mixId, (m) => ({
      ...m,
      tracks: m.tracks.map((t, i) =>
        i === idx ? normalizeForType({ ...t, track_type }, primeRatePct) : t,
      ),
    }))

  const addTrack = (mixId) =>
    patchMix(mixId, (m) =>
      m.tracks.length >= MAX_TRACKS ? m : { ...m, tracks: [...m.tracks, defaultTrack()] },
    )

  const removeTrack = (mixId, idx) => {
    patchMix(mixId, (m) => ({ ...m, tracks: m.tracks.filter((_, i) => i !== idx) }))
    setConfirmDel(null)
  }

  const revertMix = (mixId) =>
    patchMix(mixId, (m) => {
      const saved = JSON.parse(m._saved)
      return { ...m, name: saved.name, tracks: saved.tracks }
    })

  const onSave = async (mix) => {
    setSaving(mix.id)
    try {
      const body = { name: mix.name, tracks: mix.tracks.map(toApiTrack) }
      const res = await saveMix(tokenRef.current, mix.id, body)
      const tracks = res.mix.tracks.map((t) =>
        t.track_type === 'prime' ? { ...fromApiTrack(t), anchor_rate: primeRatePct } : fromApiTrack(t),
      )
      patchMix(mix.id, (m) => {
        const next = { ...m, name: res.mix.name, tracks }
        next._saved = snapshot(next)
        return next
      })
      showToast(`שעון "${mix.name}" נשמר. ניתן לחשב מחדש כדי להחיל על לקוחות פעילים.`)
    } catch (e) {
      showToast('שגיאה בשמירה. נסה שוב.', 'err')
    } finally {
      setSaving(null)
    }
  }

  // ── recalculation ─────────────────────────────────────────────────────────
  const openRecalc = async () => {
    setRecalcOpen(true)
    setRecalcCount(null)
    try {
      const { affected_count } = await getRecalcAffectedCount(tokenRef.current)
      setRecalcCount(affected_count)
    } catch { setRecalcCount(0) }
  }
  const doRecalc = async () => {
    setRecalcBusy(true)
    try {
      const res = await triggerRecalculation(tokenRef.current)
      setRecalcOpen(false)
      showToast(`החישוב מחדש הסתיים. עודכנו ${res.recalculated} בקשות פעילות.`)
    } catch {
      showToast('שגיאה בחישוב מחדש.', 'err')
    } finally {
      setRecalcBusy(false)
    }
  }

  if (loading) return <div className="admin-loading">טוען שעונים...</div>
  if (error) return <div className="admin-error">{error}</div>

  return (
    <div className="mix-page">
      <div className="mix-page-head">
        <div>
          <h1>ניהול תמהיל — שעונים</h1>
          <p className="mix-page-sub">
            הגדרת המסלולים שלפיהם המערכת מחשבת את שעוני העלות. כל שעון הוא תמהיל של עד {MAX_TRACKS} מסלולים שסכומם 100%.
          </p>
        </div>
        <button className="btn btn-danger" onClick={openRecalc}>חשב מחדש לכל הלקוחות</button>
      </div>

      {mixes.map((mix) => {
        const total = mixTotal(mix.tracks)
        const balanced = mixBalanced(mix.tracks)
        const dirty = snapshot(mix) !== mix._saved
        const allErrs = mix.tracks.map(validateTrack)
        const hasErr = allErrs.some((e) => Object.keys(e).length)
        const isOpen = !!expanded[mix.id]
        return (
          <div className="clock-panel" key={mix.id}>
            <div className="clock-head" onClick={() => setExpanded((s) => ({ ...s, [mix.id]: !s[mix.id] }))}>
              <span className="clock-badge">שעון {mix.clock_number}</span>
              <input
                className={`clock-name-input ${mix.name.trim() ? '' : 'invalid'}`}
                value={mix.name}
                maxLength={40}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => patchMix(mix.id, (m) => ({ ...m, name: e.target.value }))}
              />
              <span className="clock-count">{mix.tracks.length} מסלולים</span>
              <span className="clock-spacer" />
              <span className={`mix-total ${balanced ? 'ok' : 'bad'}`}>{total}%</span>
              <span className={`chevron ${isOpen ? 'open' : ''}`}>▼</span>
            </div>

            {isOpen && (
              <div className="clock-body">
                <table className="tracks-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>סוג ריבית</th>
                      <th>צמוד מדד</th>
                      <th>תדירות שינוי</th>
                      <th>תקופה (שנים)</th>
                      <th>% מהתמהיל</th>
                      <th>שיטת פירעון</th>
                      <th>ריבית עוגן %</th>
                      <th>מרווח %</th>
                      <th>ריבית אפקטיבית</th>
                      <th>תשלום חודשי לדוגמה</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {mix.tracks.map((t, idx) => {
                      const errs = allErrs[idx]
                      const isPrime = t.track_type === 'prime'
                      const isFixed = t.track_type === 'fixed'
                      const isVar = t.track_type === 'variable'
                      const eff = effectiveRate(t)
                      return (
                        <tr key={idx}>
                          <td className="cell-seq">{idx + 1}</td>
                          <td>
                            <select className="t-select" value={t.track_type}
                              onChange={(e) => changeType(mix.id, idx, e.target.value)}>
                              {TRACK_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <input type="checkbox" className="t-check"
                              checked={t.cpi_linked} disabled={isPrime}
                              title={isPrime ? 'מסלול פריים אינו צמוד מדד' : ''}
                              onChange={(e) => updateTrack(mix.id, idx, { cpi_linked: e.target.checked })} />
                          </td>
                          <td>
                            {isVar ? (
                              <select className="t-select" value={t.rate_change_interval_months ?? ''}
                                onChange={(e) => updateTrack(mix.id, idx, { rate_change_interval_months: Number(e.target.value) })}>
                                {CHANGE_INTERVALS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                              </select>
                            ) : <span className="cell-computed">—</span>}
                          </td>
                          <td>
                            <input type="number" className={`t-input num ${errs.period_years ? 'invalid' : ''}`}
                              min={4} max={30} value={t.period_years}
                              onChange={(e) => updateTrack(mix.id, idx, { period_years: e.target.value === '' ? '' : Number(e.target.value) })} />
                            {errs.period_years && <span className="field-err">{errs.period_years}</span>}
                          </td>
                          <td>
                            <input type="number" className={`t-input num ${errs.percentage_of_mix ? 'invalid' : ''}`}
                              min={0} max={100} step={0.1} value={t.percentage_of_mix}
                              onChange={(e) => updateTrack(mix.id, idx, { percentage_of_mix: e.target.value === '' ? '' : Number(e.target.value) })} />
                            {errs.percentage_of_mix && <span className="field-err">{errs.percentage_of_mix}</span>}
                          </td>
                          <td>
                            <select className="t-select" value={t.amortization_type}
                              onChange={(e) => updateTrack(mix.id, idx, { amortization_type: e.target.value })}>
                              {AMORT_METHODS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                          </td>
                          <td>
                            <input type="number" className={`t-input num ${errs.anchor_rate ? 'invalid' : ''}`}
                              step={0.01} value={t.anchor_rate} disabled={isPrime}
                              title={isPrime ? 'נגזר מריבית הפריים במערכת' : ''}
                              onChange={(e) => updateTrack(mix.id, idx, { anchor_rate: e.target.value === '' ? '' : Number(e.target.value) })} />
                            {errs.anchor_rate && <span className="field-err">{errs.anchor_rate}</span>}
                          </td>
                          <td>
                            <input type="number" className="t-input num"
                              step={0.01} value={isFixed ? 0 : t.spread} disabled={isFixed}
                              title={isFixed ? 'בקבועה אין מרווח' : ''}
                              onChange={(e) => updateTrack(mix.id, idx, { spread: e.target.value === '' ? '' : Number(e.target.value) })} />
                          </td>
                          <td className={`cell-computed ${eff > HIGH_RATE_WARN ? 'cell-warn' : ''}`}
                            title={eff > HIGH_RATE_WARN ? 'ריבית גבוהה מ-15% — ודא שהנתון נכון' : ''}>
                            {eff.toFixed(2)}%{eff > HIGH_RATE_WARN ? ' ⚠' : ''}
                          </td>
                          <td className="cell-computed">{formatILS(samplePayment(t))}</td>
                          <td>
                            <button className="btn-ghost" title="הסר מסלול"
                              disabled={mix.tracks.length <= 1}
                              onClick={() => setConfirmDel({ mixId: mix.id, index: idx })}>🗑</button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>

                {confirmDel && confirmDel.mixId === mix.id && (
                  <div className="confirm-banner">
                    <span>למחוק מסלול זה? פעולה זו תשפיע על כל הלקוחות המשויכים לשעון.</span>
                    <button className="btn btn-danger" onClick={() => removeTrack(mix.id, confirmDel.index)}>מחק</button>
                    <button className="btn btn-secondary" onClick={() => setConfirmDel(null)}>ביטול</button>
                  </div>
                )}

                <div className="clock-actions">
                  <button className="btn btn-secondary" disabled={mix.tracks.length >= MAX_TRACKS}
                    title={mix.tracks.length >= MAX_TRACKS ? `עד ${MAX_TRACKS} מסלולים לשעון` : ''}
                    onClick={() => addTrack(mix.id)}>+ הוסף מסלול</button>
                  {!balanced && <span className="mix-total bad">סך התמהיל {total}% (נדרש 100%)</span>}
                  <div className="right">
                    <button className="btn btn-secondary" disabled={!dirty} onClick={() => revertMix(mix.id)}>בטל שינויים</button>
                    <button className="btn btn-primary"
                      disabled={!dirty || !balanced || hasErr || !mix.name.trim() || saving === mix.id}
                      onClick={() => onSave(mix)}>
                      {saving === mix.id ? 'שומר...' : 'שמור שעון'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}

      {recalcOpen && (
        <div className="modal-backdrop" onClick={() => !recalcBusy && setRecalcOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>חישוב מחדש לכל הלקוחות</h3>
            <p>
              {recalcCount == null
                ? 'טוען מספר בקשות מושפעות...'
                : `חישוב מחדש יופעל עבור ${recalcCount} בקשות פעילות. פעולה זו עלולה לארוך מספר רגעים. האם להמשיך?`}
            </p>
            <div className="modal-actions">
              <button className="btn btn-primary" disabled={recalcBusy || recalcCount == null} onClick={doRecalc}>
                {recalcBusy ? 'מחשב...' : 'כן, חשב מחדש'}
              </button>
              <button className="btn btn-secondary" disabled={recalcBusy} onClick={() => setRecalcOpen(false)}>ביטול</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className={`admin-toast ${toast.kind === 'err' ? 'err' : ''}`}>{toast.msg}</div>}
    </div>
  )
}
