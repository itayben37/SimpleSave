from fastapi import APIRouter, Depends
from app.common.models import User
from app.common.auth import get_current_user
from datetime import datetime, timezone

router = APIRouter()

@router.get("/")
async def get_notifications(current_user: User = Depends(get_current_user)):
    return {"notifications": [
        {"id": "1", "type": "info", "message": "ברוכים הבאים ל-SimpleSave!", "read": False, "created_at": datetime.now(timezone.utc).isoformat()}
    ]}
