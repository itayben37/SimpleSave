"""
Calculations API endpoints.
spec: docs/specs/calculations/
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import get_current_user
from app.common.error_handlers import NotFoundError, ForbiddenError
from app.config.database import get_db
from app.common.models import User, RoleEnum, ClockResult, Application
from app.modules.calculations.clocks import generate_clocks
from app.modules.calculations.eligibility import calculate_eligibility

router = APIRouter(prefix="/api/calculations", tags=["calculations"])


async def _load_application(application_id: str, current_user: User, db: AsyncSession) -> Application:
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    if current_user.role not in (RoleEnum.admin, RoleEnum.advisor) and app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")
    return app


def _card(r: ClockResult) -> dict:
    """Build the frontend clock card from the stored result_data payload."""
    data = r.result_data or {}
    return {
        "clock_result_id": r.id,
        "mix_id": r.mix_id,
        "clock_number": r.clock_number,
        "monthly_payment_initial": data.get("monthly_payment_initial", 0),
        "total_payment": data.get("total_payment", 0),
        "total_interest": data.get("total_interest", 0),
        "total_cpi_adjustment": data.get("total_cpi_adjustment", 0),
        "risk_score_percentage": data.get("risk_score_percentage", float(r.risk_score)),
        "risk_level": data.get("risk_level", "medium"),
        "rate_assumption_notes": data.get("rate_assumption_notes", []),
        "stacked_bar_data": data.get("stacked_bar_data", []),
        "cumulative_totals_data": data.get("cumulative_totals_data", []),
    }


# ── POST /api/calculations/clocks ────────────────────────────────────────────

class ClocksRequest(BaseModel):
    application_id: str


@router.post("/clocks")
async def run_clocks(
    body: ClocksRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force (re)generation of the 5 clocks for an application across all active mixes."""
    await _load_application(body.application_id, current_user, db)
    results = await generate_clocks(body.application_id, db)
    await db.commit()
    return {"clocks": sorted([_card(r) for r in results], key=lambda c: c["clock_number"])}


# ── GET /api/calculations/clocks/{application_id} ────────────────────────────

@router.get("/clocks/{application_id}")
async def get_clocks(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _load_application(application_id, current_user, db)

    rows = await db.execute(
        select(ClockResult).where(ClockResult.application_id == application_id).order_by(ClockResult.clock_number)
    )
    results = list(rows.scalars())

    # Lazy generation: if no clocks have been computed yet, compute them now.
    if not results:
        results = await generate_clocks(application_id, db)
        await db.commit()

    return {"clocks": sorted([_card(r) for r in results], key=lambda c: c["clock_number"])}


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
