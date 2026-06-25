"""
Firebase Auth middleware for FastAPI.
Every protected endpoint uses `get_current_user` as a dependency.
Role guards are thin wrappers that call `get_current_user` then check the role.
"""

from typing import Annotated

from fastapi import Depends, Header, Request
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_handlers import ForbiddenError, UnauthorizedError
from app.common.models import RoleEnum, User
from app.config.database import get_db


async def _verify_firebase_token(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded
    except firebase_auth.ExpiredIdTokenError:
        raise UnauthorizedError("Token expired")
    except firebase_auth.InvalidIdTokenError:
        raise UnauthorizedError("Invalid token")
    except Exception:
        raise UnauthorizedError("Token verification failed")


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    decoded = await _verify_firebase_token(authorization)
    firebase_uid = decoded.get("uid")
    if not firebase_uid:
        raise UnauthorizedError("Token missing uid")

    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found in system")
    if not user.is_active:
        raise ForbiddenError("Account is disabled")

    # Slide last_login_at is handled on login; here we just attach user to request state
    request.state.current_user = user
    return user


def require_role(*roles: RoleEnum):
    """Factory that returns a FastAPI dependency enforcing one of the given roles."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError(f"Role '{user.role}' is not permitted for this action")
        return user

    return _guard


# Convenience aliases
require_admin = require_role(RoleEnum.admin)
require_advisor = require_role(RoleEnum.advisor)
require_client = require_role(RoleEnum.client)
require_admin_or_advisor = require_role(RoleEnum.admin, RoleEnum.advisor)
