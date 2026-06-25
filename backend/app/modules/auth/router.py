"""
Auth router — handles post-OTP user sync.
Firebase Auth owns the OTP flow. After client completes Firebase OTP, it calls
POST /api/auth/sync to ensure a User DB row exists and returns the user's role + profile.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from firebase_admin import auth as firebase_auth
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import write_audit
from app.common.error_handlers import UnauthorizedError
from app.common.models import RoleEnum, User
from app.config.database import get_db

router = APIRouter()


class SyncResponse(BaseModel):
    user_id: str
    role: str
    is_new_user: bool
    full_name: str | None


@router.post("/sync", response_model=SyncResponse)
async def sync_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the frontend immediately after Firebase OTP succeeds.
    - If a User row exists for this firebase_uid → return it (returning user).
    - If not → create a Client row (self-registration path).
    Advisors/Admins are pre-created by admin and will always hit the returning-user path.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError()

    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception:
        raise UnauthorizedError("Invalid token")

    firebase_uid = decoded["uid"]
    firebase_user = firebase_auth.get_user(firebase_uid)

    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()
    is_new = False

    if user is None:
        # New client self-registration
        user = User(
            id=str(uuid.uuid4()),
            firebase_uid=firebase_uid,
            phone=firebase_user.phone_number,
            email=firebase_user.email,
            role=RoleEnum.client,
            full_name=firebase_user.display_name,
            is_active=True,
        )
        db.add(user)
        is_new = True

        # Set role claim on Firebase so subsequent tokens carry it
        firebase_auth.set_custom_user_claims(firebase_uid, {"role": RoleEnum.client.value})

        await write_audit(
            db, user.id, "auth.client_registered", "User", user.id,
            after={"role": "client", "firebase_uid": firebase_uid},
            ip_address=request.client.host if request.client else None,
        )
    else:
        from sqlalchemy.sql import func as sqlfunc
        user.last_login_at = sqlfunc.now()

    await db.commit()
    await db.refresh(user)

    return SyncResponse(
        user_id=user.id,
        role=user.role.value,
        is_new_user=is_new,
        full_name=user.full_name,
    )
