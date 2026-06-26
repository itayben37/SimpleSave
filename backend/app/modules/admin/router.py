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
