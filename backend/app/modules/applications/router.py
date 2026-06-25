"""
Applications API endpoints — wizard auto-save, status reads.
spec: docs/specs/frontend/06-wizard-flow.md, docs/specs/frontend/07-wizard-screen.md
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import write_audit
from app.common.auth import get_current_user, require_admin_or_advisor
from app.config.database import get_db
from app.common.error_handlers import NotFoundError, ForbiddenError
from app.common.models import (
    Application, User, RoleEnum, ApplicationStatusEnum,
    Mix, MixTrack, Borrower,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])

VALID_TRANSITIONS = {
    ApplicationStatusEnum.questionnaire_in_progress: ApplicationStatusEnum.questionnaire_complete,
    ApplicationStatusEnum.questionnaire_complete: ApplicationStatusEnum.registered,
    ApplicationStatusEnum.registered: ApplicationStatusEnum.tier_selected,
    ApplicationStatusEnum.tier_selected: ApplicationStatusEnum.personal_details_complete,
    ApplicationStatusEnum.personal_details_complete: ApplicationStatusEnum.authorization_signed,
    ApplicationStatusEnum.authorization_signed: ApplicationStatusEnum.documents_submitted,
    ApplicationStatusEnum.documents_submitted: ApplicationStatusEnum.documents_approved,
    ApplicationStatusEnum.documents_approved: ApplicationStatusEnum.principal_approval_requested,
    ApplicationStatusEnum.principal_approval_requested: ApplicationStatusEnum.principal_approval_received,
    ApplicationStatusEnum.principal_approval_received: ApplicationStatusEnum.bank_selected,
    ApplicationStatusEnum.bank_selected: ApplicationStatusEnum.mortgage_signed,
    ApplicationStatusEnum.mortgage_signed: ApplicationStatusEnum.collaterals_pending,
    ApplicationStatusEnum.collaterals_pending: ApplicationStatusEnum.collaterals_complete,
    ApplicationStatusEnum.collaterals_complete: ApplicationStatusEnum.active_mortgage,
}


# ── POST /api/applications — create new application (client) ─────────────────

class CreateApplicationRequest(BaseModel):
    loan_purpose: str | None = None
    property_value: float | None = None
    loan_amount: float | None = None


@router.post("", status_code=201)
async def create_application(
    body: CreateApplicationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in (RoleEnum.client, RoleEnum.admin, RoleEnum.advisor):
        raise ForbiddenError()

    app_id = str(uuid.uuid4())
    application = Application(
        id=app_id,
        client_user_id=current_user.id,
        status=ApplicationStatusEnum.questionnaire_in_progress,
        loan_purpose=body.loan_purpose,
        property_value=body.property_value,
        loan_amount=body.loan_amount,
    )
    db.add(application)
    await write_audit(
        db, actor_id=current_user.id,
        action_type="create", entity_type="application", entity_id=app_id,
        after={"status": "QUESTIONNAIRE_IN_PROGRESS"},
    )
    await db.commit()
    return {"application_id": app_id, "status": "QUESTIONNAIRE_IN_PROGRESS"}


# ── GET /api/applications/{id}/wizard-state ───────────────────────────────────

@router.get("/{application_id}/wizard-state")
async def get_wizard_state(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")

    _assert_access(current_user, app)

    # Load primary borrower for wizard pre-fill
    borrower_row = await db.execute(
        select(Borrower).where(
            Borrower.application_id == application_id,
            Borrower.is_primary == True,
        )
    )
    borrower = borrower_row.scalars().first()

    return {
        "application_id": application_id,
        "status": app.status.value,
        "wizard_data": {
            "loan_purpose": app.loan_purpose,
            "property_value": float(app.property_value) if app.property_value else None,
            "loan_amount": float(app.loan_amount) if app.loan_amount else None,
            "num_borrowers": app.num_borrowers,
            "first_home": app.first_home,
            "vatikei_interest": app.vatikei_interest,
            "marital_status": app.marital_status,
            "num_children": app.num_children,
            "military_service_type": app.military_service_type,
            "eligible_siblings_count": app.eligible_siblings_count,
            "wedding_duration_years": app.wedding_duration_years,
            "primary_borrower_birth_date": (
                borrower.birth_date.isoformat() if borrower and borrower.birth_date else None
            ),
        },
    }


# ── PATCH /api/applications/{id} — wizard auto-save ──────────────────────────

class WizardPatchRequest(BaseModel):
    wizard_data: dict[str, Any]
    advance_status: bool = False


@router.patch("/{application_id}")
async def patch_application(
    application_id: str,
    body: WizardPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")

    _assert_access(current_user, app)

    before = {"status": app.status.value}
    data = body.wizard_data

    # Apply wizard fields that map to Application columns
    _apply_wizard_fields(app, data)

    if body.advance_status:
        next_status = VALID_TRANSITIONS.get(app.status)
        if next_status:
            app.status = next_status

    after = {"status": app.status.value}
    await write_audit(
        db, actor_id=current_user.id,
        action_type="update", entity_type="application", entity_id=application_id,
        before=before, after=after,
    )
    await db.commit()
    return {"application_id": application_id, "status": app.status.value}


# ── GET /api/applications (advisor/admin list) ────────────────────────────────

@router.get("")
async def list_applications(
    current_user: User = Depends(require_admin_or_advisor),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(Application))
    apps = rows.scalars().all()
    return {
        "applications": [
            {
                "application_id": a.id,
                "status": a.status.value,
                "client_user_id": a.client_user_id,
                "loan_amount": float(a.loan_amount) if a.loan_amount else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in apps
        ]
    }


# ── GET /api/applications/{id} ────────────────────────────────────────────────

@router.get("/{application_id}")
async def get_application(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)
    return {
        "application_id": app.id,
        "status": app.status.value,
        "client_user_id": app.client_user_id,
        "loan_purpose": app.loan_purpose,
        "property_value": float(app.property_value) if app.property_value else None,
        "loan_amount": float(app.loan_amount) if app.loan_amount else None,
        "tier": app.tier.value if app.tier else None,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_access(current_user: User, app: Application):
    if current_user.role in (RoleEnum.admin, RoleEnum.advisor):
        return
    if app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")


_WIZARD_FIELD_MAP = {
    "loan_purpose": "loan_purpose",
    "property_value": "property_value",
    "loan_amount": "loan_amount",
    "num_borrowers": "num_borrowers",
    "first_home": "first_home",
    "vatikei_interest": "vatikei_interest",
    "marital_status": "marital_status",
    "num_children": "num_children",
    "military_service_type": "military_service_type",
    "eligible_siblings_count": "eligible_siblings_count",
    "wedding_duration_years": "wedding_duration_years",
    "loan_type": "loan_type",
    "total_monthly_income": "total_monthly_income",
    "total_monthly_obligations": "total_monthly_obligations",
    "existing_mortgage_balance": "existing_mortgage_balance",
}


def _apply_wizard_fields(app: Application, data: dict):
    for wizard_key, model_attr in _WIZARD_FIELD_MAP.items():
        if wizard_key in data:
            setattr(app, model_attr, data[wizard_key])
