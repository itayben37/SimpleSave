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
from app.common.models import RoleEnum, User
from app.config.database import get_db

router = APIRouter()


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
