from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.config.database import get_db
from app.common.models import Message, Application, User, RoleEnum
from app.common.auth import get_current_user
from app.common.error_handlers import NotFoundError, ForbiddenError
from datetime import datetime, timezone

router = APIRouter()

class SendMessageRequest(BaseModel):
    body: str
    stage_tag: str | None = None

@router.get("/{application_id}")
async def get_messages(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    if current_user.role not in (RoleEnum.admin, RoleEnum.advisor) and app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")

    from sqlalchemy.orm import selectinload
    rows = await db.execute(
        select(Message)
        .where(Message.application_id == application_id)
        .options(selectinload(Message.sender))
        .order_by(Message.sent_at)
    )
    messages = rows.scalars().all()
    return {
        "messages": [
            {
                "id": m.id,
                "body": m.body,
                "stage_tag": m.stage_tag,
                "sender_id": m.sender_id,
                "sender_name": m.sender.full_name if m.sender else None,
                "sender_role": m.sender.role.value if m.sender else None,
                "is_mine": m.sender_id == current_user.id,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            }
            for m in messages
        ]
    }

@router.post("/{application_id}")
async def send_message(
    application_id: str,
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application")
    if current_user.role not in (RoleEnum.admin, RoleEnum.advisor) and app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")

    msg = Message(
        application_id=application_id,
        sender_id=current_user.id,
        body=req.body,
        stage_tag=req.stage_tag,
        sent_at=datetime.now(timezone.utc)
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {
        "id": msg.id,
        "body": msg.body,
        "stage_tag": msg.stage_tag,
        "sender_id": msg.sender_id,
        "sender_name": current_user.full_name,
        "sender_role": current_user.role.value,
        "is_mine": True,
        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
    }
