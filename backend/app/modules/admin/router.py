import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, field_validator
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import require_admin
from app.common.audit import write_audit
from app.common.error_handlers import ConflictError
from app.common.models import (
    RoleEnum, User, Application, Borrower, Bank,
    SystemParameter, InterestRateTable,
    Mix, MixTrack, TrackTypeEnum, AmortizationTypeEnum, RiskLevelEnum,
    ApplicationStatusEnum,
)
from app.config.database import get_db
from sqlalchemy import func
from sqlalchemy.orm import selectinload

router = APIRouter()


# ── GET /api/admin/overview — dashboard headline counts ───────────────────────

@router.get("/overview")
async def admin_overview(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    async def _count(model) -> int:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    # Applications grouped by status
    rows = await db.execute(
        select(Application.status, func.count()).group_by(Application.status)
    )
    by_status = {status.value: cnt for status, cnt in rows.all()}

    # Users grouped by role
    rrows = await db.execute(select(User.role, func.count()).group_by(User.role))
    by_role = {role.value: cnt for role, cnt in rrows.all()}

    return {
        "total_applications": await _count(Application),
        "total_users": await _count(User),
        "total_banks": await _count(Bank),
        "applications_by_status": by_status,
        "users_by_role": by_role,
    }


# ── GET /api/admin/users — list all users ─────────────────────────────────────

@router.get("/users")
async def list_users(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(User).order_by(User.created_at.desc()))
    users = rows.scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


# ── GET /api/admin/applications — all applications w/ client + advisor names ───

@router.get("/applications")
async def list_all_applications(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Application)
        .options(
            selectinload(Application.borrowers),
            selectinload(Application.client),
            selectinload(Application.advisor),
        )
        .order_by(Application.created_at.desc())
    )
    apps = rows.scalars().all()

    def _name(a: Application) -> str:
        if a.borrowers:
            b = sorted(a.borrowers, key=lambda x: x.sequence_number)[0]
            full = " ".join(filter(None, [b.first_name, b.last_name])).strip()
            if full:
                return full
        return (a.client.full_name if a.client else None) or "לקוח ללא שם"

    return {
        "applications": [
            {
                "application_id": a.id,
                "client_name": _name(a),
                "advisor_name": a.advisor.full_name if a.advisor else None,
                "status": a.status.value,
                "tier": a.tier.value if a.tier else None,
                "loan_amount": float(a.loan_amount) if a.loan_amount is not None else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in apps
        ]
    }


# ── GET /api/admin/system-parameters ──────────────────────────────────────────

@router.get("/system-parameters")
async def list_system_parameters(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(SystemParameter).order_by(SystemParameter.key))
    params = rows.scalars().all()
    return {
        "parameters": [
            {
                "id": p.id,
                "key": p.key,
                "value": float(p.value),
                "previous_value": float(p.previous_value) if p.previous_value is not None else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in params
        ]
    }


# ── GET /api/admin/interest-rates ─────────────────────────────────────────────

@router.get("/interest-rates")
async def list_interest_rates(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(InterestRateTable).order_by(
            InterestRateTable.track_type, InterestRateTable.period_years_min
        )
    )
    rates = rows.scalars().all()
    return {
        "rates": [
            {
                "id": r.id,
                "track_type": r.track_type.value,
                "cpi_linked": r.cpi_linked,
                "loan_purpose": r.loan_purpose.value,
                "period_years_min": r.period_years_min,
                "period_years_max": r.period_years_max,
                "rate": float(r.rate),
                "effective_from": r.effective_from.isoformat() if r.effective_from else None,
            }
            for r in rates
        ]
    }


# ── GET /api/admin/banks ──────────────────────────────────────────────────────

@router.get("/banks")
async def list_banks(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(Bank).order_by(Bank.name_he))
    banks = rows.scalars().all()
    return {
        "banks": [
            {
                "id": b.id,
                "name_he": b.name_he,
                "mortgage_hotline": b.mortgage_hotline,
                "is_active": b.is_active,
            }
            for b in banks
        ]
    }


class CreateUserRequest(BaseModel):
    role: RoleEnum
    full_name: str
    phone: str | None = None
    email: EmailStr | None = None

    @field_validator("role")
    @classmethod
    def role_not_client(cls, v: RoleEnum) -> RoleEnum:
        if v == RoleEnum.client:
            raise ValueError("Use client self-registration; admin cannot create client accounts")
        return v

    @field_validator("phone", "email")
    @classmethod
    def at_least_one_contact(cls, v, info):
        # Validated at model level below
        return v

    def model_post_init(self, __context) -> None:
        if not self.phone and not self.email:
            raise ValueError("At least one of phone or email is required")


class UserResponse(BaseModel):
    id: str
    firebase_uid: str | None
    phone: str | None
    email: str | None
    role: str
    full_name: str | None
    is_active: bool


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_admin_or_advisor(
    body: CreateUserRequest,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """
    Admin provisions a new Admin or Advisor account.
    1. Creates Firebase Auth user
    2. Sets role custom claim on the Firebase user
    3. Inserts User row in DB
    """
    # Conflict check
    if body.email:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise ConflictError(f"Email {body.email} is already registered")
    if body.phone:
        existing = await db.execute(select(User).where(User.phone == body.phone))
        if existing.scalar_one_or_none():
            raise ConflictError(f"Phone {body.phone} is already registered")

    # Create Firebase Auth user
    firebase_kwargs: dict = {"display_name": body.full_name}
    if body.email:
        firebase_kwargs["email"] = body.email
    if body.phone:
        firebase_kwargs["phone_number"] = body.phone

    firebase_user = firebase_auth.create_user(**firebase_kwargs)

    # Set role as custom claim so backend can read it from the ID token
    firebase_auth.set_custom_user_claims(firebase_user.uid, {"role": body.role.value})

    # Insert DB row
    user = User(
        id=str(uuid.uuid4()),
        firebase_uid=firebase_user.uid,
        phone=body.phone,
        email=body.email,
        role=body.role,
        full_name=body.full_name,
        is_active=True,
    )
    db.add(user)

    await write_audit(
        db, admin.id, "admin.user_created", "User", user.id,
        after={"role": body.role.value, "email": body.email, "phone": body.phone},
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}/deactivate", status_code=200)
async def deactivate_user(
    user_id: str,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    from app.common.error_handlers import NotFoundError
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")

    user.is_active = False
    if user.firebase_uid:
        firebase_auth.update_user(user.firebase_uid, disabled=True)

    await write_audit(db, admin.id, "admin.user_deactivated", "User", user.id,
                      before={"is_active": True}, after={"is_active": False},
                      ip_address=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}


@router.patch("/users/{user_id}/reactivate", status_code=200)
async def reactivate_user(
    user_id: str,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    from app.common.error_handlers import NotFoundError
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User")

    user.is_active = True
    if user.firebase_uid:
        firebase_auth.update_user(user.firebase_uid, disabled=False)

    await write_audit(db, admin.id, "admin.user_reactivated", "User", user.id,
                      before={"is_active": False}, after={"is_active": True},
                      ip_address=request.client.host if request.client else None)
    await db.commit()
    return {"ok": True}

from app.common.error_handlers import NotFoundError
from datetime import datetime, timezone
import uuid
from typing import Optional

class UpdateSystemParameterRequest(BaseModel):
    value: float

@router.put("/system-parameters/{param_id}")
async def update_system_parameter(
    param_id: str,
    req: UpdateSystemParameterRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db)
):
    param = await db.get(SystemParameter, param_id)
    if not param:
        raise NotFoundError("SystemParameter")
    
    param.previous_value = param.value
    param.value = req.value
    param.updated_by_admin_id = admin.id
    param.updated_at = datetime.now(timezone.utc)
    
    await write_audit(db, admin.id, "admin.parameter_updated", "SystemParameter", param.id,
                      before={"value": float(param.previous_value) if param.previous_value else None}, 
                      after={"value": float(param.value)})
    await db.commit()
    return param

class UpdateInterestRateRequest(BaseModel):
    rate: float

@router.put("/interest-rates/{rate_id}")
async def update_interest_rate(
    rate_id: str,
    req: UpdateInterestRateRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db)
):
    rate_entry = await db.get(InterestRateTable, rate_id)
    if not rate_entry:
        raise NotFoundError("InterestRateTable")
    
    old_rate = rate_entry.rate
    rate_entry.rate = req.rate
    
    await write_audit(db, admin.id, "admin.interest_rate_updated", "InterestRateTable", rate_entry.id,
                      before={"rate": float(old_rate)}, after={"rate": float(rate_entry.rate)})
    await db.commit()
    return rate_entry

class CreateInterestRateRequest(BaseModel):
    track_type: str
    cpi_linked: bool
    loan_purpose: str
    period_years_min: int
    period_years_max: int
    rate: float
    effective_from: Optional[datetime] = None

@router.post("/interest-rates")
async def create_interest_rate(
    req: CreateInterestRateRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db)
):
    rate_entry = InterestRateTable(
        id=str(uuid.uuid4()),
        track_type=req.track_type,
        cpi_linked=req.cpi_linked,
        loan_purpose=req.loan_purpose,
        period_years_min=req.period_years_min,
        period_years_max=req.period_years_max,
        rate=req.rate,
        effective_from=req.effective_from,
        created_by_admin_id=admin.id
    )
    db.add(rate_entry)
    
    await write_audit(db, admin.id, "admin.interest_rate_created", "InterestRateTable", rate_entry.id,
                      after={"rate": float(rate_entry.rate)})
    await db.commit()
    return rate_entry

class AssignAdvisorRequest(BaseModel):
    advisor_id: str

@router.patch("/applications/{application_id}/assign-advisor")
async def assign_advisor(
    application_id: str,
    req: AssignAdvisorRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
        
    advisor = await db.get(User, req.advisor_id)
    if not advisor or advisor.role != RoleEnum.advisor:
        raise ConflictError("User is not an advisor or does not exist")
        
    old_advisor_id = app.advisor_id
    app.advisor_id = advisor.id
    
    await write_audit(db, admin.id, "admin.advisor_assigned", "Application", app.id,
                      before={"advisor_id": old_advisor_id}, after={"advisor_id": app.advisor_id})
    await db.commit()
    return {"ok": True, "advisor_id": app.advisor_id}


# ──────────────────────────────────────────────────────────────────────────────
# Mix / Tracks Manager  (screen 39 — "ניהול תמהיל" / שעונים)
# ──────────────────────────────────────────────────────────────────────────────

# Active applications eligible for recalculation: everything except a not-yet-
# registered draft and an already-signed (locked-rate) active mortgage.
_RECALC_EXCLUDED_STATUSES = (
    ApplicationStatusEnum.questionnaire_in_progress,
    ApplicationStatusEnum.active_mortgage,
)


def _serialize_mix(mix: Mix) -> dict:
    tracks = sorted(mix.tracks, key=lambda t: t.sequence)
    return {
        "id": mix.id,
        "clock_number": mix.clock_number,
        "name": mix.name,
        "risk_level": mix.risk_level.value,
        "is_active": mix.is_active,
        "tracks": [
            {
                "id": t.id,
                "sequence": t.sequence,
                "track_type": t.track_type.value,
                "cpi_linked": t.cpi_linked,
                "period_years": t.period_years,
                "rate_change_interval_months": t.rate_change_interval_months,
                "amortization_type": t.amortization_type.value,
                "percentage_of_mix": float(t.percentage_of_mix),
                "anchor_rate": float(t.anchor_rate) if t.anchor_rate is not None else None,
                "spread": float(t.spread) if t.spread is not None else None,
                "total_rate": float(t.total_rate) if t.total_rate is not None else None,
            }
            for t in tracks
        ],
    }


@router.get("/mixes")
async def list_mixes(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Mix).options(selectinload(Mix.tracks)).order_by(Mix.clock_number)
    )
    mixes = rows.scalars().all()
    return {"mixes": [_serialize_mix(m) for m in mixes]}


class TrackInput(BaseModel):
    track_type: TrackTypeEnum
    cpi_linked: bool = False
    period_years: int
    rate_change_interval_months: Optional[int] = None
    amortization_type: AmortizationTypeEnum = AmortizationTypeEnum.spitzer
    percentage_of_mix: float
    anchor_rate: Optional[float] = None
    spread: Optional[float] = None


class SaveMixRequest(BaseModel):
    name: Optional[str] = None
    risk_level: Optional[RiskLevelEnum] = None
    tracks: list[TrackInput]


@router.put("/mixes/{mix_id}")
async def save_mix(
    mix_id: str,
    req: SaveMixRequest,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Replace a clock's track list in one shot. Validates 1–10 tracks summing to 100%."""
    rows = await db.execute(
        select(Mix).options(selectinload(Mix.tracks)).where(Mix.id == mix_id)
    )
    mix = rows.scalars().first()
    if not mix:
        raise NotFoundError("Mix")

    if not (1 <= len(req.tracks) <= 10):
        raise ConflictError("שעון חייב לכלול בין מסלול אחד ל-10 מסלולים")

    total_pct = round(sum(t.percentage_of_mix for t in req.tracks), 2)
    if total_pct != 100.0:
        raise ConflictError(f"סך אחוזי המסלולים חייב להיות 100% (כעת {total_pct}%)")

    for t in req.tracks:
        if not (4 <= t.period_years <= 30):
            raise ConflictError("תקופת מסלול חייבת להיות בין 4 ל-30 שנים")
        if t.track_type == TrackTypeEnum.variable:
            if t.rate_change_interval_months not in (36, 60):
                raise ConflictError("מסלול משתנה דורש תדירות שינוי של 3 או 5 שנים")
            if t.period_years < 6:
                raise ConflictError("מסלול משתנה דורש תקופה של לפחות 6 שנים")
            interval_years = t.rate_change_interval_months // 12
            if t.period_years % interval_years != 0:
                raise ConflictError("תקופת מסלול משתנה חייבת להיות כפולה של תדירות השינוי")

    before = _serialize_mix(mix)

    # Replace tracks wholesale.
    for old in list(mix.tracks):
        await db.delete(old)
    await db.flush()

    for seq, t in enumerate(req.tracks, start=1):
        is_prime = t.track_type == TrackTypeEnum.prime
        is_fixed = t.track_type == TrackTypeEnum.fixed
        # פריים אינו צמוד מדד; בקבועה אין מרווח.
        cpi_linked = False if is_prime else t.cpi_linked
        spread = 0.0 if is_fixed else (t.spread or 0.0)
        anchor = t.anchor_rate
        total_rate = (anchor + spread) if anchor is not None else None
        db.add(MixTrack(
            id=str(uuid.uuid4()),
            mix_id=mix.id,
            sequence=seq,
            track_type=t.track_type,
            cpi_linked=cpi_linked,
            period_years=t.period_years,
            rate_change_interval_months=(t.rate_change_interval_months if t.track_type == TrackTypeEnum.variable else None),
            amortization_type=t.amortization_type,
            percentage_of_mix=t.percentage_of_mix,
            anchor_rate=anchor,
            spread=spread,
            total_rate=total_rate,
        ))

    if req.name is not None:
        mix.name = req.name
    if req.risk_level is not None:
        mix.risk_level = req.risk_level

    await db.flush()
    await write_audit(
        db, admin.id, "admin.mix_saved", "Mix", mix.id,
        before=before, after={"track_count": len(req.tracks)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    # expire_on_commit=False keeps the stale tracks collection in the identity
    # map, so force a fresh load (populate_existing) for the read-back.
    rows = await db.execute(
        select(Mix)
        .options(selectinload(Mix.tracks))
        .where(Mix.id == mix_id)
        .execution_options(populate_existing=True)
    )
    return {"mix": _serialize_mix(rows.scalars().first())}


@router.get("/recalculate/affected-count")
async def recalculate_affected_count(
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    cnt = (await db.execute(
        select(func.count()).select_from(Application).where(
            Application.status.notin_(_RECALC_EXCLUDED_STATUSES)
        )
    )).scalar_one()
    return {"affected_count": cnt}


@router.post("/recalculate")
async def recalculate_all(
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Regenerate the clocks (ClockResults) for every active application."""
    from app.modules.calculations.clocks import generate_clocks

    rows = await db.execute(
        select(Application.id).where(
            Application.status.notin_(_RECALC_EXCLUDED_STATUSES)
        )
    )
    app_ids = [r[0] for r in rows.all()]

    recalculated = 0
    for app_id in app_ids:
        try:
            # Savepoint per application so one failure rolls back only its own
            # work and leaves the session usable for the rest of the batch.
            async with db.begin_nested():
                await generate_clocks(app_id, db)
            recalculated += 1
        except Exception:
            continue
    await db.flush()

    # entity_id is a non-null UUID column; a system-wide action has no single
    # entity, so reference the admin who triggered it.
    await write_audit(
        db, admin.id, "admin.recalculation_triggered", "System", admin.id,
        after={"affected_count": len(app_ids), "recalculated": recalculated},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"affected_count": len(app_ids), "recalculated": recalculated}
