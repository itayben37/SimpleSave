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
    AdditionalIncome, FixedExpense, AdditionalProperty,
    AdditionalIncomeTypeEnum, FixedExpenseTypeEnum, ExpenseSourceEnum,
    PropertyTypeEnum, PurchaseStatusEnum, MoneyNeededByEnum, PropertySourceEnum,
    PropertyRegistrationEnum, WillingToTransferEnum, ValuationSourceEnum,
    RefinancePurposeEnum,
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
        .options(
            selectinload(Application.borrowers).selectinload(Borrower.additional_incomes),
            selectinload(Application.borrowers).selectinload(Borrower.fixed_expenses),
            selectinload(Application.borrowers).selectinload(Borrower.additional_properties),
            selectinload(Application.advisor),
        )
        .order_by(Application.created_at.desc())
    )
    app = rows.scalars().first()
    if not app:
        return {"application": None}
    return {"application": _serialize_application(app, include_nested=True)}


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


# Mortgage-data columns the Personal Area persists directly on Application.
# name -> kind: 'str' | 'int' | 'bool' | 'decimal' | 'date' | 'json' | <EnumClass>
APPLICATION_FIELDS: dict[str, Any] = {
    "property_value": "decimal", "loan_amount": "decimal", "equity_amount": "decimal",
    "equity_sources": "json", "max_loan_term_years": "int",
    "desired_monthly_min": "decimal", "desired_monthly_max": "decimal",
    "property_source": PropertySourceEnum,
    "property_registration_type": PropertyRegistrationEnum,
    "property_type": PropertyTypeEnum,
    "property_address_city": "str", "property_address_street": "str",
    "property_address_number": "str", "property_address_apartment": "str",
    "property_floor": "int", "property_total_floors": "int",
    "property_area_sqm": "decimal", "property_age_years": "int",
    "purchase_status": PurchaseStatusEnum, "contract_signed_date": "date",
    "money_needed_by": MoneyNeededByEnum,
    "previously_applied_to_banks": "bool", "previously_applied_bank_ids": "json",
    "willing_to_transfer_account": WillingToTransferEnum,
    "has_prior_mortgage_application": "bool",
    "valuation_source": ValuationSourceEnum, "previously_owned_property": "bool",
    "refinance_purpose": RefinancePurposeEnum, "refinance_inject_amount": "decimal",
}


def _apply_known_columns(app: Application, data: dict):
    """Promote wizard / Personal-Area answers that have dedicated Application columns.

    Everything else stays only in wizard_data (the JSONB blob).
    """
    # Aliases used by the wizard / mortgage tab
    if "loan_purpose" in data:
        lt = _coerce_loan_type(data["loan_purpose"])
        if lt is not None:
            app.loan_type = lt
    if "loan_type" in data:
        lt = _coerce_loan_type(data["loan_type"])
        if lt is not None:
            app.loan_type = lt
    if "equity" in data and "equity_amount" not in data:
        app.equity_amount = _to_decimal(data["equity"])
    if "tier" in data:
        tier = _coerce_tier(data["tier"])
        if tier is not None:
            app.tier = tier

    for name, kind in APPLICATION_FIELDS.items():
        if name not in data:
            continue
        try:
            setattr(app, name, _coerce_field(data[name], kind))
        except (ValueError, InvalidOperation):
            continue

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
    "children_shared": "bool",
    "prev_employer_name": "str", "prev_employment_start_date": "date",
    "prev_employment_end_date": "date",
    "address_city": "str", "address_street": "str",
    "address_number": "str", "address_apartment": "str",
    "has_checking_account": "bool", "checking_accounts": "json",
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
    if kind == "json":
        return value  # pass lists/dicts straight through to a JSONB column
    # Enum class
    return kind(value)


# ── Nested per-borrower table metadata (income / expense / property) ──────────

INCOME_FIELDS: dict[str, Any] = {
    "income_type": AdditionalIncomeTypeEnum, "income_type_detail": "str",
    "monthly_amount": "decimal",
}
EXPENSE_FIELDS: dict[str, Any] = {
    "expense_type": FixedExpenseTypeEnum, "expense_type_detail": "str",
    "monthly_amount": "decimal", "remaining_balance": "decimal",
    "end_date": "date", "interest_rate": "decimal", "source": ExpenseSourceEnum,
}
PROPERTY_FIELDS: dict[str, Any] = {
    "property_type": PropertyTypeEnum, "city": "str", "street": "str",
    "number": "str", "floor": "int", "apartment_number": "str",
    "area_sqm": "decimal", "estimated_value": "decimal", "existing_mortgage": "decimal",
}


def _serialize_row(row, fields: dict) -> dict:
    out = {"id": row.id}
    for name, kind in fields.items():
        val = getattr(row, name)
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


def _serialize_borrower(b: Borrower, include_nested: bool = False) -> dict:
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
    if include_nested:
        out["additional_incomes"] = [_serialize_row(r, INCOME_FIELDS) for r in b.additional_incomes]
        out["fixed_expenses"] = [_serialize_row(r, EXPENSE_FIELDS) for r in b.fixed_expenses]
        out["additional_properties"] = [_serialize_row(r, PROPERTY_FIELDS) for r in b.additional_properties]
    return out


def _serialize_application(app: Application, include_nested: bool = False) -> dict:
    advisor_name = app.advisor.full_name if app.advisor else None
    out = {
        "application_id": app.id,
        "status": app.status.value,
        "tier": app.tier.value if app.tier else None,
        "advisor_id": app.advisor_id,
        "advisor_name": advisor_name,
        "loan_purpose": app.loan_type.value if app.loan_type else None,
        "financing_ratio": float(app.financing_ratio) if app.financing_ratio is not None else None,
        "wizard_data": app.wizard_data or {},
        "borrowers": [
            _serialize_borrower(b, include_nested=include_nested)
            for b in sorted(app.borrowers, key=lambda x: x.sequence_number)
        ],
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }
    # Surface every dedicated mortgage-data column (coerced to JSON-safe values)
    for name, kind in APPLICATION_FIELDS.items():
        val = getattr(app, name)
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


# ── Nested per-borrower tables: incomes / expenses / properties ───────────────
# spec: MD "Additional income", "Fixed expenses"/"Loans", "Additional properties"

_RESOURCE_CONFIG: dict[str, dict] = {
    "incomes": {
        "model": AdditionalIncome, "fields": INCOME_FIELDS,
        "defaults": lambda: {"income_type": AdditionalIncomeTypeEnum.other, "monthly_amount": Decimal("0")},
    },
    "expenses": {
        "model": FixedExpense, "fields": EXPENSE_FIELDS,
        "defaults": lambda: {"expense_type": FixedExpenseTypeEnum.other, "monthly_amount": Decimal("0")},
    },
    "properties": {
        "model": AdditionalProperty, "fields": PROPERTY_FIELDS,
        "defaults": lambda: {"property_type": PropertyTypeEnum.apartment_building, "city": "", "street": "", "number": ""},
    },
}


class RowRequest(BaseModel):
    fields: dict[str, Any]


async def _load_borrower_for_write(application_id, borrower_id, current_user, db) -> Borrower:
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)
    borrower = await db.get(Borrower, borrower_id)
    if not borrower or borrower.application_id != application_id:
        raise NotFoundError("Borrower")
    return borrower


def _build_row_kwargs(fields_spec: dict, payload: dict, defaults: dict) -> dict:
    kwargs = dict(defaults)
    for name, kind in fields_spec.items():
        if name in payload and payload[name] not in (None, ""):
            try:
                kwargs[name] = _coerce_field(payload[name], kind)
            except (ValueError, InvalidOperation):
                pass
    return kwargs


@router.post("/{application_id}/borrowers/{borrower_id}/{resource}", status_code=201)
async def create_nested_row(
    application_id: str, borrower_id: str, resource: str, body: RowRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    cfg = _RESOURCE_CONFIG.get(resource)
    if not cfg:
        raise NotFoundError("Resource")
    await _load_borrower_for_write(application_id, borrower_id, current_user, db)
    kwargs = _build_row_kwargs(cfg["fields"], body.fields, cfg["defaults"]())
    row = cfg["model"](id=str(uuid.uuid4()), borrower_id=borrower_id, **kwargs)
    db.add(row)
    await write_audit(db, actor_id=current_user.id, action_type="create",
                      entity_type=resource, entity_id=row.id, after=body.fields)
    await db.commit()
    await db.refresh(row)
    return _serialize_row(row, cfg["fields"])


@router.patch("/{application_id}/borrowers/{borrower_id}/{resource}/{row_id}")
async def update_nested_row(
    application_id: str, borrower_id: str, resource: str, row_id: str, body: RowRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    cfg = _RESOURCE_CONFIG.get(resource)
    if not cfg:
        raise NotFoundError("Resource")
    await _load_borrower_for_write(application_id, borrower_id, current_user, db)
    row = await db.get(cfg["model"], row_id)
    if not row or row.borrower_id != borrower_id:
        raise NotFoundError("Row")
    for name, value in body.fields.items():
        if name not in cfg["fields"]:
            continue
        try:
            setattr(row, name, _coerce_field(value, cfg["fields"][name]))
        except (ValueError, InvalidOperation):
            continue
    await write_audit(db, actor_id=current_user.id, action_type="update",
                      entity_type=resource, entity_id=row_id, after=body.fields)
    await db.commit()
    await db.refresh(row)
    return _serialize_row(row, cfg["fields"])


@router.delete("/{application_id}/borrowers/{borrower_id}/{resource}/{row_id}", status_code=204)
async def delete_nested_row(
    application_id: str, borrower_id: str, resource: str, row_id: str,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    cfg = _RESOURCE_CONFIG.get(resource)
    if not cfg:
        raise NotFoundError("Resource")
    await _load_borrower_for_write(application_id, borrower_id, current_user, db)
    row = await db.get(cfg["model"], row_id)
    if not row or row.borrower_id != borrower_id:
        raise NotFoundError("Row")
    await db.delete(row)
    await write_audit(db, actor_id=current_user.id, action_type="delete",
                      entity_type=resource, entity_id=row_id)
    await db.commit()
    return None


from app.common.models import PrincipalApproval

@router.get("/{application_id}/principal-approvals")
async def list_principal_approvals(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    if current_user.role not in (RoleEnum.admin, RoleEnum.advisor) and app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")
        
    rows = await db.execute(
        select(PrincipalApproval)
        .where(PrincipalApproval.application_id == application_id)
        .options(selectinload(PrincipalApproval.bank))
    )
    approvals = rows.scalars().all()
    
    return {
        "principal_approvals": [
            {
                "id": a.id,
                "bank_id": a.bank_id,
                "bank_name": a.bank.name_he if a.bank else None,
                "bank_logo": a.bank.logo_url if a.bank else None,
                "status": a.status.value,
                "approved_amount": float(a.approved_amount) if a.approved_amount else None,
                "is_best_offer": a.is_best_offer,
                "approved_mix_details": a.approved_mix_details
            }
            for a in approvals
        ]
    }


# ── Authorization letters (the MD "sign letters of authorization" prompt) ─────

@router.post("/{application_id}/sign-authorization")
async def sign_authorization(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)
    app.authorization_signed_at = datetime.now(timezone.utc)
    if app.status == ApplicationStatusEnum.personal_details_complete:
        app.status = ApplicationStatusEnum.authorization_signed
    await write_audit(db, actor_id=current_user.id, action_type="sign_authorization",
                      entity_type="application", entity_id=application_id)
    await db.commit()
    return {
        "application_id": application_id,
        "status": app.status.value,
        "authorization_signed_at": app.authorization_signed_at.isoformat(),
    }


# ── Collaterals (advisor-entered list the client sees post-signing) ───────────

from app.common.models import Collateral, CollateralStatusEnum


@router.get("/{application_id}/collaterals")
async def list_collaterals(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)
    rows = await db.execute(
        select(Collateral).where(Collateral.application_id == application_id).order_by(Collateral.created_at)
    )
    return {
        "collaterals": [
            {
                "id": c.id,
                "description": c.description_he,
                "status": c.status.value,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows.scalars()
        ]
    }


class CollateralRequest(BaseModel):
    description: str
    status: str | None = None


@router.post("/{application_id}/collaterals", status_code=201)
async def add_collateral(
    application_id: str,
    body: CollateralRequest,
    current_user: User = Depends(require_admin_or_advisor),
    db: AsyncSession = Depends(get_db),
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    try:
        status = CollateralStatusEnum(body.status) if body.status else CollateralStatusEnum.pending
    except ValueError:
        status = CollateralStatusEnum.pending
    col = Collateral(
        id=str(uuid.uuid4()), application_id=application_id,
        description_he=body.description, status=status,
        added_by_advisor_id=current_user.id,
    )
    db.add(col)
    await write_audit(db, actor_id=current_user.id, action_type="create",
                      entity_type="collateral", entity_id=col.id, after={"description": body.description})
    await db.commit()
    await db.refresh(col)
    return {"id": col.id, "description": col.description_he, "status": col.status.value}


# ── Eligibility (Ministry-of-Housing "Price for Residents" score) ─────────────

from app.modules.calculations.eligibility import calculate_eligibility


@router.get("/{application_id}/eligibility")
async def application_eligibility(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Derive the eligibility score from the primary borrower's answers.
    Only meaningful for a first-home buyer with no previously-owned property —
    the frontend decides when to show it."""
    app = await _load_full_application(application_id, db)
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)

    borrowers = sorted(app.borrowers, key=lambda b: b.sequence_number)
    if not borrowers or not borrowers[0].birth_date:
        return {"available": False, "reason": "missing_birth_date"}
    b = borrowers[0]

    military_type = "regular" if (b.military_service_months or 0) >= 36 else "none"
    wedding_years = 0
    if b.wedding_date:
        today = _date.today()
        wedding_years = today.year - b.wedding_date.year - (
            (today.month, today.day) < (b.wedding_date.month, b.wedding_date.day)
        )
    num_children = b.num_children if b.num_children is not None else (b.children_under_18 or 0)

    result = calculate_eligibility(
        marital_status=b.marital_status.value if b.marital_status else "single",
        number_of_children=num_children or 0,
        military_service_type=military_type,
        eligible_siblings_count=b.num_siblings_in_country or 0,
        wedding_duration_years=max(0, wedding_years),
        applicant_birth_date=b.birth_date,
    )
    return {
        "available": True,
        "eligibility_score": result.eligibility_score,
        "is_eligible": result.is_eligible,
        "score_breakdown": result.score_breakdown,
        "threshold": 51,
    }
