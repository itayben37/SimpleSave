"""
Mortgage Calculation Engine — spec: docs/specs/calculations/09-mortgage-calculation-engine.md

All monetary arithmetic uses Python Decimal for precision.
No hardcoded rates — all parameters injected by the caller.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, getcontext

# 28-digit precision to avoid accumulation error over 360 months
getcontext().prec = 28

ZERO = Decimal("0")
ONE = Decimal("1")
TWO_PLACES = Decimal("0.01")


def _d(v) -> Decimal:
    """Convert any numeric to Decimal."""
    return Decimal(str(v))


# ── Output types ─────────────────────────────────────────────────────────────

@dataclass
class AmortizationRow:
    month: int
    monthly_payment: Decimal
    principal_payment: Decimal
    interest_payment: Decimal
    cpi_adjustment: Decimal      # non-zero only at 12-month boundaries when cpi_linked
    balance_remaining: Decimal


@dataclass
class TrackResult:
    monthly_payment_initial: Decimal
    monthly_payment_final: Decimal
    total_payment_over_term: Decimal
    total_interest_paid: Decimal
    total_cpi_adjustment: Decimal
    risk_level: str              # 'low' | 'medium' | 'high'
    risk_score_percentage: Decimal
    rate_assumption_note_he: str | None
    amortization_schedule: list[AmortizationRow] = field(default_factory=list)
    term_not_feasible: bool = False


# ── Single-track engine ───────────────────────────────────────────────────────

def _spitzer_payment(balance: Decimal, r: Decimal, n_remaining: int) -> Decimal:
    """Monthly Spitzer payment for given balance, monthly rate, remaining months."""
    if n_remaining <= 0:
        return ZERO
    if r < Decimal("0.0000001"):
        # Near-zero rate: limit → balance / n
        return balance / _d(n_remaining)
    factor = (ONE + r) ** n_remaining
    return balance * r * factor / (factor - ONE)


def calculate_track(
    loan_amount: Decimal,
    period_years: int,
    amortization_type: str,     # 'spitzer' | 'equal_principal'
    track_type: str,            # 'fixed' | 'variable' | 'prime'
    annual_rate: Decimal,       # e.g. Decimal("0.035")
    cpi_annual_forecast: Decimal,
    cpi_linked: bool,
    rate_change_interval_months: int | None = None,
) -> TrackResult:
    """
    Calculate a full amortization schedule for one mortgage track.
    Returns TrackResult with per-month amortization_schedule.
    """
    if period_years < 4:
        return TrackResult(
            monthly_payment_initial=ZERO, monthly_payment_final=ZERO,
            total_payment_over_term=ZERO, total_interest_paid=ZERO,
            total_cpi_adjustment=ZERO, risk_level="low",
            risk_score_percentage=ZERO, rate_assumption_note_he=None,
            term_not_feasible=True,
        )

    P = loan_amount
    n_total = period_years * 12
    r = annual_rate / _d(12)

    note_he = None
    if track_type == "variable":
        note_he = (
            "חישוב מבוסס על הריבית הנוכחית לכל תקופת ההלוואה. "
            "שינויי ריבית עתידיים עשויים לשנות את התשלום."
        )

    schedule: list[AmortizationRow] = []
    balance = P
    total_payment = ZERO
    total_interest = ZERO
    total_cpi = ZERO
    month_global = 0

    if amortization_type == "spitzer":
        if cpi_linked:
            # Spitzer + CPI: recompute payment each year on inflated balance
            for year in range(1, period_years + 1):
                n_remaining = (period_years - (year - 1)) * 12
                mp = _spitzer_payment(balance, r, n_remaining)

                for m in range(1, 13):
                    month_global += 1
                    if month_global > n_total:
                        break
                    interest = (balance * r).quantize(TWO_PLACES, ROUND_HALF_UP)
                    principal = mp - interest
                    # Final month correction
                    if month_global == n_total:
                        principal = balance
                        mp = principal + interest
                    balance = balance - principal
                    cpi_adj = ZERO

                    # Apply CPI at year boundary (after last month of each year)
                    if m == 12 and year < period_years and balance > ZERO:
                        cpi_adj = (balance * cpi_annual_forecast).quantize(TWO_PLACES, ROUND_HALF_UP)
                        balance = balance + cpi_adj

                    total_payment += mp
                    total_interest += interest
                    total_cpi += cpi_adj
                    schedule.append(AmortizationRow(
                        month=month_global,
                        monthly_payment=mp.quantize(TWO_PLACES, ROUND_HALF_UP),
                        principal_payment=principal.quantize(TWO_PLACES, ROUND_HALF_UP),
                        interest_payment=interest,
                        cpi_adjustment=cpi_adj,
                        balance_remaining=max(balance, ZERO).quantize(TWO_PLACES, ROUND_HALF_UP),
                    ))
        else:
            # Spitzer without CPI: single payment for the whole term
            mp = _spitzer_payment(P, r, n_total)
            balance = P
            for k in range(1, n_total + 1):
                interest = (balance * r).quantize(TWO_PLACES, ROUND_HALF_UP)
                principal = mp - interest
                if k == n_total:
                    principal = balance
                    mp = principal + interest
                balance = balance - principal
                total_payment += mp
                total_interest += interest
                schedule.append(AmortizationRow(
                    month=k,
                    monthly_payment=mp.quantize(TWO_PLACES, ROUND_HALF_UP),
                    principal_payment=principal.quantize(TWO_PLACES, ROUND_HALF_UP),
                    interest_payment=interest,
                    cpi_adjustment=ZERO,
                    balance_remaining=max(balance, ZERO).quantize(TWO_PLACES, ROUND_HALF_UP),
                ))

    else:  # equal_principal
        principal_per_month = (P / _d(n_total)).quantize(TWO_PLACES, ROUND_HALF_UP)
        balance = P

        if cpi_linked:
            for year in range(1, period_years + 1):
                n_remaining = (period_years - (year - 1)) * 12
                pp = (balance / _d(n_remaining)).quantize(TWO_PLACES, ROUND_HALF_UP)

                for m in range(1, 13):
                    month_global += 1
                    if month_global > n_total:
                        break
                    if month_global == n_total:
                        pp = balance
                    interest = (balance * r).quantize(TWO_PLACES, ROUND_HALF_UP)
                    mp = pp + interest
                    balance = balance - pp
                    cpi_adj = ZERO

                    if m == 12 and year < period_years and balance > ZERO:
                        cpi_adj = (balance * cpi_annual_forecast).quantize(TWO_PLACES, ROUND_HALF_UP)
                        balance = balance + cpi_adj

                    total_payment += mp
                    total_interest += interest
                    total_cpi += cpi_adj
                    schedule.append(AmortizationRow(
                        month=month_global,
                        monthly_payment=mp.quantize(TWO_PLACES, ROUND_HALF_UP),
                        principal_payment=pp,
                        interest_payment=interest,
                        cpi_adjustment=cpi_adj,
                        balance_remaining=max(balance, ZERO).quantize(TWO_PLACES, ROUND_HALF_UP),
                    ))
        else:
            for k in range(1, n_total + 1):
                pp = principal_per_month if k < n_total else balance
                interest = (balance * r).quantize(TWO_PLACES, ROUND_HALF_UP)
                mp = pp + interest
                balance = balance - pp
                total_payment += mp
                total_interest += interest
                schedule.append(AmortizationRow(
                    month=k,
                    monthly_payment=mp.quantize(TWO_PLACES, ROUND_HALF_UP),
                    principal_payment=pp,
                    interest_payment=interest,
                    cpi_adjustment=ZERO,
                    balance_remaining=max(balance, ZERO).quantize(TWO_PLACES, ROUND_HALF_UP),
                ))

    return TrackResult(
        monthly_payment_initial=schedule[0].monthly_payment if schedule else ZERO,
        monthly_payment_final=schedule[-1].monthly_payment if schedule else ZERO,
        total_payment_over_term=total_payment.quantize(TWO_PLACES, ROUND_HALF_UP),
        total_interest_paid=total_interest.quantize(TWO_PLACES, ROUND_HALF_UP),
        total_cpi_adjustment=total_cpi.quantize(TWO_PLACES, ROUND_HALF_UP),
        risk_level="low",          # set by mix-level risk calc, not track-level
        risk_score_percentage=ZERO,
        rate_assumption_note_he=note_he,
        amortization_schedule=schedule,
    )


# ── Risk score calculation ────────────────────────────────────────────────────

def calculate_risk_score(tracks: list[dict]) -> tuple[Decimal, str]:
    """
    tracks: list of dicts with keys: track_type, cpi_linked, percentage
    Returns (risk_score_percentage 0-100, risk_level 'low'|'medium'|'high')
    """
    prime_pct = sum(_d(t["percentage"]) for t in tracks if t["track_type"] == "prime")
    variable_pct = sum(_d(t["percentage"]) for t in tracks if t["track_type"] == "variable")
    cpi_fixed_pct = sum(
        _d(t["percentage"]) for t in tracks
        if t["track_type"] == "fixed" and t["cpi_linked"]
    )
    score = min(prime_pct + variable_pct + cpi_fixed_pct, _d("100"))

    if score < _d("33"):
        level = "low"
    elif score <= _d("66"):
        level = "medium"
    else:
        level = "high"

    return score, level


# ── Multi-track mix aggregation ───────────────────────────────────────────────

@dataclass
class MixResult:
    monthly_payment_initial: Decimal
    total_payment: Decimal
    total_interest: Decimal
    total_cpi: Decimal
    risk_score_percentage: Decimal
    risk_level: str
    rate_assumption_notes: list[str]
    per_track_results: list[TrackResult]
    amortization_schedule: list[dict]  # aggregated month rows
    stacked_bar_data: list[dict]       # per year for Chart.js
    cumulative_totals_data: list[dict]


def aggregate_mix(
    loan_amount: Decimal,
    max_loan_term_years: int,
    tracks: list[dict],       # list of mix_track dicts
    prime_rate: Decimal,
    cpi_annual_forecast: Decimal,
    interest_rate_lookup: dict,  # {(track_type, cpi_linked, period_years): anchor_rate}
) -> MixResult | None:
    """
    Run the calculation engine for each track, then sum month-by-month.
    Returns None if any rate is missing (clock skipped).
    """
    track_results: list[TrackResult] = []
    risk_track_inputs: list[dict] = []
    notes: list[str] = []

    for t in tracks:
        track_type = t["track_type"]
        cpi_linked = bool(t["cpi_linked"])
        period_years = min(int(t["period_years"]), max_loan_term_years)
        percentage = _d(str(t["percentage_of_mix"]))
        spread = _d(str(t.get("spread") or 0))

        if track_type == "prime":
            annual_rate = prime_rate + spread
            cpi_linked = False
        else:
            key = (track_type, cpi_linked, period_years)
            if key not in interest_rate_lookup:
                return None  # rate not configured → skip entire clock
            anchor = interest_rate_lookup[key]
            annual_rate = anchor + spread

        track_loan = loan_amount * percentage / _d("100")

        result = calculate_track(
            loan_amount=track_loan,
            period_years=period_years,
            amortization_type=t["amortization_type"],
            track_type=track_type,
            annual_rate=annual_rate,
            cpi_annual_forecast=cpi_annual_forecast,
            cpi_linked=cpi_linked,
            rate_change_interval_months=t.get("rate_change_interval_months"),
        )
        track_results.append(result)
        risk_track_inputs.append({"track_type": track_type, "cpi_linked": cpi_linked, "percentage": percentage})
        if result.rate_assumption_note_he:
            notes.append(result.rate_assumption_note_he)

    # Find max schedule length across all tracks
    max_months = max((len(r.amortization_schedule) for r in track_results), default=0)

    # Sum month-by-month
    agg_schedule: list[dict] = []
    for m in range(max_months):
        row = {"month": m + 1, "monthly_payment": ZERO, "principal_payment": ZERO,
               "interest_payment": ZERO, "cpi_adjustment": ZERO, "balance_remaining": ZERO}
        for tr in track_results:
            if m < len(tr.amortization_schedule):
                s = tr.amortization_schedule[m]
                row["monthly_payment"] += s.monthly_payment
                row["principal_payment"] += s.principal_payment
                row["interest_payment"] += s.interest_payment
                row["cpi_adjustment"] += s.cpi_adjustment
                row["balance_remaining"] += s.balance_remaining
        for k in ("monthly_payment", "principal_payment", "interest_payment", "cpi_adjustment", "balance_remaining"):
            row[k] = row[k].quantize(TWO_PLACES, ROUND_HALF_UP)
        agg_schedule.append(row)

    # Stacked bar data (per year)
    stacked: list[dict] = []
    for year in range(1, max_months // 12 + 2):
        months = agg_schedule[(year - 1) * 12: year * 12]
        if not months:
            break
        stacked.append({
            "year": year,
            "principal": sum(r["principal_payment"] for r in months),
            "interest": sum(r["interest_payment"] for r in months),
            "cpi": sum(r["cpi_adjustment"] for r in months),
        })

    # Cumulative totals
    cum_paid = ZERO
    cum: list[dict] = []
    for row in agg_schedule:
        cum_paid += row["monthly_payment"]
        cum.append({
            "month": row["month"],
            "total_paid_to_date": cum_paid.quantize(TWO_PLACES, ROUND_HALF_UP),
            "balance_remaining": row["balance_remaining"],
        })

    risk_score, risk_level = calculate_risk_score(risk_track_inputs)

    total_pay = sum(r.total_payment_over_term for r in track_results)
    total_int = sum(r.total_interest_paid for r in track_results)
    total_cpi = sum(r.total_cpi_adjustment for r in track_results)
    initial_mp = sum(r.monthly_payment_initial for r in track_results)

    return MixResult(
        monthly_payment_initial=initial_mp.quantize(TWO_PLACES, ROUND_HALF_UP),
        total_payment=total_pay.quantize(TWO_PLACES, ROUND_HALF_UP),
        total_interest=total_int.quantize(TWO_PLACES, ROUND_HALF_UP),
        total_cpi=total_cpi.quantize(TWO_PLACES, ROUND_HALF_UP),
        risk_score_percentage=risk_score,
        risk_level=risk_level,
        rate_assumption_notes=list(dict.fromkeys(notes)),  # deduplicate
        per_track_results=track_results,
        amortization_schedule=agg_schedule,
        stacked_bar_data=stacked,
        cumulative_totals_data=cum,
    )
