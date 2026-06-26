"""
Clocks (mix) generation orchestrator.
spec: docs/specs/calculations/10-clocks-mix-generation.md

For a given application, runs the calculation engine over every active Mix
(the "clocks"), pulling system parameters and interest rates from the DB.
Persists one ClockResult per mix (result payload lives in result_data JSONB).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models import (
    Mix, MixTrack, SystemParameter, InterestRateTable,
    ClockResult, Application,
)
from app.modules.calculations.engine import aggregate_mix


# ── DB readers (use the real column names) ───────────────────────────────────

async def _get_system_params(db: AsyncSession) -> dict:
    rows = await db.execute(select(SystemParameter))
    return {r.key: Decimal(str(r.value)) for r in rows.scalars()}


async def _get_rate_rows(db: AsyncSession) -> list[InterestRateTable]:
    rows = await db.execute(select(InterestRateTable))
    return list(rows.scalars())


def _loan_purpose_for(app: Application) -> str:
    """Map the application loan_type onto the rate table's loan_purpose."""
    if app.loan_type is not None and app.loan_type.value == "all_purpose":
        return "all_purpose"
    return "housing"


def _find_rate(
    rate_rows: list[InterestRateTable],
    track_type: str,
    cpi_linked: bool,
    loan_purpose: str,
    period_years: int,
) -> Decimal | None:
    """Find the rate whose period range contains period_years (exact purpose/type/cpi)."""
    candidates = [
        r for r in rate_rows
        if r.track_type.value == track_type
        and bool(r.cpi_linked) == cpi_linked
        and r.loan_purpose.value == loan_purpose
        and r.period_years_min <= period_years <= r.period_years_max
    ]
    if candidates:
        return Decimal(str(candidates[0].rate))
    # Fall back to housing if an all_purpose-specific row is missing
    if loan_purpose != "housing":
        return _find_rate(rate_rows, track_type, cpi_linked, "housing", period_years)
    return None


def _max_loan_term(app: Application, default: int = 30) -> int:
    """Derive the cap on track length. Prefer the stored value, else 85 - age, else default."""
    if app.max_loan_term_years:
        return max(4, min(int(app.max_loan_term_years), 30))
    birth = (app.wizard_data or {}).get("primary_borrower_birth_date")
    if birth:
        try:
            y, m, d = (int(x) for x in str(birth)[:10].split("-"))
            age = (date.today() - date(y, m, d)).days // 365
            return max(4, min(85 - age, 30))
        except (ValueError, TypeError):
            pass
    return default


def _to_jsonable(obj):
    """Recursively convert Decimals to float so the payload is JSON/JSONB-serializable."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


async def generate_clocks(application_id: str, db: AsyncSession) -> list[ClockResult]:
    """
    Run the engine for every active mix against this application's loan amount.
    Replaces any prior clock_results for the application. Caller commits.
    """
    app = await db.get(Application, application_id)
    if not app or app.loan_amount is None:
        return []

    loan_amount = Decimal(str(app.loan_amount))
    loan_purpose = _loan_purpose_for(app)
    max_term = _max_loan_term(app)

    params = await _get_system_params(db)
    prime_rate = params.get("prime_rate", Decimal("0.0625"))
    cpi_forecast = params.get("cpi_annual_forecast", Decimal("0.03"))
    rate_rows = await _get_rate_rows(db)

    mixes_result = await db.execute(
        select(Mix).where(Mix.is_active == True).order_by(Mix.clock_number)
    )
    mixes = list(mixes_result.scalars())

    # Clear prior results for this application
    existing = await db.execute(
        select(ClockResult).where(ClockResult.application_id == application_id)
    )
    for old in existing.scalars():
        await db.delete(old)
    await db.flush()

    created: list[ClockResult] = []
    for mix in mixes:
        tracks_result = await db.execute(
            select(MixTrack).where(MixTrack.mix_id == mix.id).order_by(MixTrack.sequence)
        )
        tracks = list(tracks_result.scalars())
        if not tracks:
            continue

        track_dicts = []
        rate_lookup: dict = {}
        for t in tracks:
            period = min(int(t.period_years), max_term)
            track_dicts.append({
                "track_type": t.track_type.value,
                "cpi_linked": bool(t.cpi_linked),
                "period_years": period,
                "percentage_of_mix": t.percentage_of_mix,
                "amortization_type": t.amortization_type.value,
                "spread": t.spread or Decimal("0"),
                "rate_change_interval_months": t.rate_change_interval_months,
            })
            if t.track_type.value != "prime":
                rate = _find_rate(
                    rate_rows, t.track_type.value, bool(t.cpi_linked), loan_purpose, period
                )
                if rate is not None:
                    rate_lookup[(t.track_type.value, bool(t.cpi_linked), period)] = rate

        result = aggregate_mix(
            loan_amount=loan_amount,
            max_loan_term_years=max_term,
            tracks=track_dicts,
            prime_rate=prime_rate,
            cpi_annual_forecast=cpi_forecast,
            interest_rate_lookup=rate_lookup,
        )
        if result is None:
            continue  # a required rate was missing → skip this clock

        payload = _to_jsonable({
            "mix_name": mix.name,
            "clock_number": mix.clock_number,
            "monthly_payment_initial": result.monthly_payment_initial,
            "total_payment": result.total_payment,
            "total_interest": result.total_interest,
            "total_cpi_adjustment": result.total_cpi,
            "risk_score_percentage": result.risk_score_percentage,
            "risk_level": result.risk_level,
            "rate_assumption_notes": result.rate_assumption_notes,
            "stacked_bar_data": result.stacked_bar_data,
            "cumulative_totals_data": result.cumulative_totals_data,
        })

        clock = ClockResult(
            id=str(uuid.uuid4()),
            application_id=application_id,
            mix_id=mix.id,
            clock_number=mix.clock_number,
            result_data=payload,
            risk_score=result.risk_score_percentage,
        )
        db.add(clock)
        created.append(clock)

    await db.flush()
    return created
