"""
Calculations API endpoints.
spec: docs/specs/calculations/
"""

import json
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import require_admin_or_advisor, get_current_user
from app.config.database import get_db
from app.common.models import User, ClockResult
from app.modules.calculations.clocks import generate_clocks
from app.modules.calculations.eligibility import calculate_eligibility

router = APIRouter(prefix="/api/calculations", tags=["calculations"])


# ── POST /api/calculations/clocks ────────────────────────────────────────────

class ClocksRequest(BaseModel):
    application_id: str
    mix_id: str


@router.post("/clocks")
async def run_clocks(
    body: ClocksRequest,
    current_user: User = Depends(require_admin_or_advisor),
    db: AsyncSession = Depends(get_db),
):
    results = await generate_clocks(body.application_id, body.mix_id, db)
    await db.commit()

    cards = []
    for r in results:
        notes = json.loads(r.rate_assumption_notes) if r.rate_assumption_notes else []
        cards.append({
            "clock_result_id": r.id,
            "mix_id": r.mix_id,
            "monthly_payment_initial": float(r.monthly_payment_initial),
            "total_payment": float(r.total_payment),
            "total_interest": float(r.total_interest),
            "total_cpi_adjustment": float(r.total_cpi_adjustment),
            "risk_score_percentage": float(r.risk_score_percentage),
            "risk_level": r.risk_level,
            "rate_assumption_notes": notes,
        })
    return {"clocks": cards}


# ── GET /api/calculations/clocks/{application_id} ────────────────────────────

@router.get("/clocks/{application_id}")
async def get_clocks(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(ClockResult).where(ClockResult.application_id == application_id)
    )
    results = rows.scalars().all()
    cards = []
    for r in results:
        notes = json.loads(r.rate_assumption_notes) if r.rate_assumption_notes else []
        stacked = json.loads(r.stacked_bar_data) if r.stacked_bar_data else []
        cumulative = json.loads(r.cumulative_totals_data) if r.cumulative_totals_data else []
        cards.append({
            "clock_result_id": r.id,
            "mix_id": r.mix_id,
            "monthly_payment_initial": float(r.monthly_payment_initial),
            "total_payment": float(r.total_payment),
            "total_interest": float(r.total_interest),
            "total_cpi_adjustment": float(r.total_cpi_adjustment),
            "risk_score_percentage": float(r.risk_score_percentage),
            "risk_level": r.risk_level,
            "rate_assumption_notes": notes,
            "stacked_bar_data": stacked,
            "cumulative_totals_data": cumulative,
        })
    return {"clocks": cards}


# ── POST /api/calculations/eligibility ───────────────────────────────────────

class EligibilityRequest(BaseModel):
    marital_status: str
    number_of_children: int
    military_service_type: str
    eligible_siblings_count: int
    wedding_duration_years: int
    applicant_birth_date: date


@router.post("/eligibility")
async def check_eligibility(
    body: EligibilityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = calculate_eligibility(
        marital_status=body.marital_status,
        number_of_children=body.number_of_children,
        military_service_type=body.military_service_type,
        eligible_siblings_count=body.eligible_siblings_count,
        wedding_duration_years=body.wedding_duration_years,
        applicant_birth_date=body.applicant_birth_date,
    )
    return {
        "eligibility_score": result.eligibility_score,
        "is_eligible": result.is_eligible,
        "score_breakdown": result.score_breakdown,
        "threshold": 51,
    }
