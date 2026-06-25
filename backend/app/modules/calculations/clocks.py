"""
Clocks (mix) generation orchestrator.
spec: docs/specs/calculations/10-clocks-generation.md

Generates up to 5 clock results for a given mix by pulling system parameters
and interest rates from the DB, then calls the calculation engine.
Persists results to clock_results table.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models import (
    Mix, MixTrack, SystemParameter, InterestRateTable,
    ClockResult, Application,
)
from app.modules.calculations.engine import aggregate_mix


async def _get_system_params(db: AsyncSession) -> dict:
    rows = await db.execute(select(SystemParameter))
    return {r.parameter_key: Decimal(str(r.parameter_value)) for r in rows.scalars()}


async def _build_rate_lookup(db: AsyncSession) -> dict:
    """
    Returns dict keyed by (track_type, cpi_linked, period_years) → rate as Decimal.
    period_years key is approximate: we use closest available term bucket.
    """
    rows = await db.execute(select(InterestRateTable))
    lookup: dict = {}
    for r in rows.scalars():
        lookup[(r.track_type.value, bool(r.cpi_linked), r.period_years)] = Decimal(str(r.interest_rate))
    return lookup


def _closest_rate(
    lookup: dict,
    track_type: str,
    cpi_linked: bool,
    period_years: int,
) -> Decimal | None:
    """
    Find the interest rate for the closest available term bucket.
    Falls back to adjacent terms (±5 years) before giving up.
    """
    for delta in range(0, 31):
        for sign in (0, 1, -1):
            candidate = period_years + sign * delta
            key = (track_type, cpi_linked, candidate)
            if key in lookup:
                return lookup[key]
    return None


async def generate_clocks(
    application_id: str,
    mix_id: str,
    db: AsyncSession,
) -> list[ClockResult]:
    """
    Run calculation engine for each mix, persist results, return list of ClockResult rows.
    Replaces any prior clock_results for the same mix.
    """
    # Load mix and its tracks
    mix_row = await db.get(Mix, mix_id)
    if not mix_row:
        return []

    tracks_result = await db.execute(
        select(MixTrack).where(MixTrack.mix_id == mix_id)
    )
    tracks = tracks_result.scalars().all()

    params = await _get_system_params(db)
    rate_lookup_raw = await _build_rate_lookup(db)

    prime_rate = params.get("prime_rate", Decimal("0.0625"))
    cpi_annual_forecast = params.get("cpi_annual_forecast", Decimal("0.03"))
    max_loan_term = int(params.get("max_borrower_age_at_end", Decimal("85")))

    # Build enhanced lookup with closest-term fallback
    def rate_lookup_fn(key):
        return rate_lookup_raw.get(key)

    track_dicts = [
        {
            "track_type": t.track_type.value,
            "cpi_linked": t.cpi_linked,
            "period_years": t.period_years,
            "percentage_of_mix": t.percentage_of_mix,
            "amortization_type": t.amortization_type.value,
            "spread": t.spread or Decimal("0"),
            "rate_change_interval_months": t.rate_change_interval_months,
        }
        for t in tracks
    ]

    # Prepare the enhanced rate lookup with fallback
    enhanced_lookup: dict = {}
    for td in track_dicts:
        if td["track_type"] == "prime":
            continue
        rate = _closest_rate(
            rate_lookup_raw,
            td["track_type"],
            bool(td["cpi_linked"]),
            int(td["period_years"]),
        )
        if rate is not None:
            enhanced_lookup[(td["track_type"], bool(td["cpi_linked"]), int(td["period_years"]))] = rate

    loan_amount = Decimal(str(mix_row.loan_amount))

    result = aggregate_mix(
        loan_amount=loan_amount,
        max_loan_term_years=max_loan_term,
        tracks=track_dicts,
        prime_rate=prime_rate,
        cpi_annual_forecast=cpi_annual_forecast,
        interest_rate_lookup=enhanced_lookup,
    )

    # Delete prior results
    existing = await db.execute(
        select(ClockResult).where(ClockResult.mix_id == mix_id)
    )
    for old in existing.scalars():
        await db.delete(old)

    if result is None:
        await db.flush()
        return []

    # Persist single clock result (one per mix)
    import json

    def _dec_serial(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    clock = ClockResult(
        id=str(uuid.uuid4()),
        application_id=application_id,
        mix_id=mix_id,
        monthly_payment_initial=result.monthly_payment_initial,
        total_payment=result.total_payment,
        total_interest=result.total_interest,
        total_cpi_adjustment=result.total_cpi,
        risk_score_percentage=result.risk_score_percentage,
        risk_level=result.risk_level,
        rate_assumption_notes=json.dumps(result.rate_assumption_notes, ensure_ascii=False),
        amortization_schedule=json.dumps(result.amortization_schedule, default=_dec_serial),
        stacked_bar_data=json.dumps(result.stacked_bar_data, default=_dec_serial),
        cumulative_totals_data=json.dumps(result.cumulative_totals_data, default=_dec_serial),
    )
    db.add(clock)
    await db.flush()
    return [clock]
