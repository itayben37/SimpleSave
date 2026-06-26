"""
Applications API endpoints — wizard auto-save, status reads.
spec: docs/specs/frontend/06-wizard-flow.md, docs/specs/frontend/07-wizard-screen.md
"""

import uuid
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import write_audit
from app.common.auth import get_current_user, require_admin_or_advisor
from app.config.database import get_db
from app.common.error_handlers import NotFoundError, ForbiddenError
from app.common.models import (
    Application, Borrower, User, RoleEnum, ApplicationStatusEnum,
    LoanTypeEnum, TierEnum, GenderEnum, MaritalStatusEnum, EducationEnum,
    EmploymentStatusEnum,
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
        loan_type=_coerce_loan_type(body.loan_purpose),
        property_value=_to_decimal(body.property_value),
        loan_amount=_to_decimal(body.loan_amount),
        wizard_data={},
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

    # wizard_data holds the raw answers; merge in the values that were promoted
    # to dedicated columns so the client always gets a complete picture.
    data = dict(app.wizard_data or {})
    data.setdefault("loan_purpose", app.loan_type.value if app.loan_type else None)
    data.setdefault("property_value", float(app.property_value) if app.property_value is not None else None)
    data.setdefault("loan_amount", float(app.loan_amount) if app.loan_amount is not None else None)

    return {
        "application_id": application_id,
        "status": app.status.value,
        "wizard_data": data,
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
    data = body.wizard_data or {}

    # Merge raw answers into the JSONB blob (new dict so SQLAlchemy detects the change)
    merged = dict(app.wizard_data or {})
    merged.update(data)
    app.wizard_data = merged

    # Promote the answers that have dedicated columns
    _apply_known_columns(app, data)

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


# ── GET /api/applications/me — current client's latest application (full) ──────
# NOTE: must be declared BEFORE GET /{application_id} or "me" matches that route.

@router.get("/me")
async def get_my_application(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Application)
        .where(Application.client_user_id == current_user.id)
        .options(selectinload(Application.borrowers), selectinload(Application.advisor))
        .order_by(Application.created_at.desc())
    )
    app = rows.scalars().first()
    if not app:
        return {"application": None}
    return {"application": _serialize_application(app)}


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
        "loan_purpose": app.loan_type.value if app.loan_type else None,
        "property_value": float(app.property_value) if app.property_value is not None else None,
        "loan_amount": float(app.loan_amount) if app.loan_amount is not None else None,
        "tier": app.tier.value if app.tier else None,
        "wizard_data": app.wizard_data or {},
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_access(current_user: User, app: Application):
    if current_user.role in (RoleEnum.admin, RoleEnum.advisor):
        return
    if app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")


def _to_decimal(value: Any) -> Decimal | None:
    """Coerce a wizard numeric (str/float/int) to Decimal; None/'' → None."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _coerce_loan_type(value: Any) -> LoanTypeEnum | None:
    """Map the wizard's loan_purpose string onto the LoanTypeEnum, ignoring junk."""
    if not value:
        return None
    try:
        return LoanTypeEnum(value)
    except ValueError:
        return None


def _coerce_tier(value: Any) -> TierEnum | None:
    if not value:
        return None
    try:
        return TierEnum(value)
    except ValueError:
        return None


def _apply_known_columns(app: Application, data: dict):
    """Promote wizard answers that have dedicated Application columns.

    Everything else stays only in wizard_data (the JSONB blob).
    """
    if "loan_purpose" in data:
        lt = _coerce_loan_type(data["loan_purpose"])
        if lt is not None:
            app.loan_type = lt
    if "property_value" in data:
        app.property_value = _to_decimal(data["property_value"])
    if "loan_amount" in data:
        app.loan_amount = _to_decimal(data["loan_amount"])
    if "equity" in data:
        app.equity_amount = _to_decimal(data["equity"])
    if "tier" in data:
        tier = _coerce_tier(data["tier"])
        if tier is not None:
            app.tier = tier

    # Derive financing ratio when we have both numbers
    if app.property_value and app.loan_amount and app.property_value > 0:
        app.financing_ratio = (app.loan_amount / app.property_value).quantize(Decimal("0.0001"))


# ── Borrower field metadata (single source for serialize + patch coercion) ────

# name -> kind: 'str' | 'int' | 'bool' | 'decimal' | 'date' | <EnumClass>
BORROWER_FIELDS: dict[str, Any] = {
    "first_name": "str", "last_name": "str", "gender": GenderEnum,
    "birth_date": "date", "marital_status": MaritalStatusEnum,
    "num_children": "int", "education": EducationEnum,
    "phone": "str", "email": "str",
    "employment_status": EmploymentStatusEnum, "occupation": "str",
    "employer_name": "str", "employer_city": "str", "employment_start_date": "date",
    "has_additional_citizenship": "bool", "has_foreign_tax_obligation": "bool",
    "is_politically_exposed": "bool", "has_health_issues": "bool",
    "has_credit_issues": "bool", "credit_issues_detail": "str",
    "net_income": "decimal", "military_service_months": "int",
    "num_siblings_in_country": "int", "is_smoker": "bool",
    "wedding_date": "date", "children_under_18": "int",
    "address_city": "str", "address_street": "str",
    "address_number": "str", "address_apartment": "str",
    "has_savings_fund": "bool", "savings_fund_amount": "decimal",
    "savings_fund_available_date": "date",
    "has_rental_payment": "bool", "rental_payment_amount": "decimal",
}

_TRUE_STRINGS = {"true", "1", "yes", "כן", "on"}


def _coerce_field(value: Any, kind: Any):
    if value is None or value == "":
        return None
    if kind == "str":
        return str(value)
    if kind == "int":
        return int(value)
    if kind == "bool":
        return value if isinstance(value, bool) else str(value).strip().lower() in _TRUE_STRINGS
    if kind == "decimal":
        return _to_decimal(value)
    if kind == "date":
        return _date.fromisoformat(str(value)[:10])
    # Enum class
    return kind(value)


def _serialize_borrower(b: Borrower) -> dict:
    out = {"id": b.id, "sequence_number": b.sequence_number, "is_property_owner": b.is_property_owner}
    for name, kind in BORROWER_FIELDS.items():
        val = getattr(b, name)
        if val is None:
            out[name] = None
        elif kind == "date":
            out[name] = val.isoformat()
        elif kind == "decimal":
            out[name] = float(val)
        elif isinstance(kind, type) and hasattr(val, "value"):
            out[name] = val.value
        else:
            out[name] = val
    return out


def _serialize_application(app: Application) -> dict:
    advisor_name = app.advisor.full_name if app.advisor else None
    return {
        "application_id": app.id,
        "status": app.status.value,
        "tier": app.tier.value if app.tier else None,
        "advisor_id": app.advisor_id,
        "advisor_name": advisor_name,
        "loan_purpose": app.loan_type.value if app.loan_type else None,
        "property_value": float(app.property_value) if app.property_value is not None else None,
        "loan_amount": float(app.loan_amount) if app.loan_amount is not None else None,
        "equity_amount": float(app.equity_amount) if app.equity_amount is not None else None,
        "financing_ratio": float(app.financing_ratio) if app.financing_ratio is not None else None,
        "wizard_data": app.wizard_data or {},
        "borrowers": [_serialize_borrower(b) for b in sorted(app.borrowers, key=lambda x: x.sequence_number)],
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


async def _load_full_application(application_id: str, db: AsyncSession) -> Application | None:
    rows = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.borrowers), selectinload(Application.advisor))
    )
    return rows.scalars().first()


# ── POST /api/applications/{id}/borrowers — add a borrower ─────────────────────

@router.post("/{application_id}/borrowers", status_code=201)
async def add_borrower(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await _load_full_application(application_id, db)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)

    next_seq = (max((b.sequence_number for b in app.borrowers), default=0)) + 1
    borrower = Borrower(
        id=str(uuid.uuid4()),
        application_id=application_id,
        sequence_number=next_seq,
        is_property_owner=True,
    )
    db.add(borrower)
    await write_audit(
        db, actor_id=current_user.id, action_type="create",
        entity_type="borrower", entity_id=borrower.id,
        after={"sequence_number": next_seq},
    )
    await db.commit()
    await db.refresh(borrower)
    return _serialize_borrower(borrower)


# ── PATCH /api/applications/{id}/borrowers/{bid} — auto-save personal details ──

class BorrowerPatchRequest(BaseModel):
    fields: dict[str, Any]


@router.patch("/{application_id}/borrowers/{borrower_id}")
async def patch_borrower(
    application_id: str,
    borrower_id: str,
    body: BorrowerPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)

    borrower = await db.get(Borrower, borrower_id)
    if not borrower or borrower.application_id != application_id:
        raise NotFoundError("Borrower")

    applied = {}
    for name, value in body.fields.items():
        if name not in BORROWER_FIELDS:
            continue  # ignore unknown keys
        try:
            setattr(borrower, name, _coerce_field(value, BORROWER_FIELDS[name]))
            applied[name] = value
        except (ValueError, InvalidOperation):
            continue  # skip invalid values, keep auto-save resilient

    await write_audit(
        db, actor_id=current_user.id, action_type="update",
        entity_type="borrower", entity_id=borrower_id, after=applied,
    )
    await db.commit()
    await db.refresh(borrower)
    return _serialize_borrower(borrower)
