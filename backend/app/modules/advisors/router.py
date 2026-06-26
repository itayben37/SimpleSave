"""
Advisor dashboard API — clients assigned to the advisor, client detail, tasks.
spec: QA §13 (Advisor dashboard: Tasks tab, My Clients tab, client detail).
"""

from datetime import date as _date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.auth import require_advisor, get_current_user
from app.common.error_handlers import NotFoundError, ForbiddenError, ConflictError
from app.config.database import get_db
from app.common.models import (
    Application, Borrower, User, Task, Document, RoleEnum,
    DocumentStatusEnum,
)
from app.modules.applications.router import _serialize_application

router = APIRouter()


def _primary_name(app: Application) -> str:
    """Best-effort display name for an application's client."""
    if app.borrowers:
        b = sorted(app.borrowers, key=lambda x: x.sequence_number)[0]
        full = " ".join(filter(None, [b.first_name, b.last_name])).strip()
        if full:
            return full
    if app.client and app.client.full_name:
        return app.client.full_name
    return "לקוח ללא שם"


# ── GET /api/advisors/clients — applications assigned to this advisor ──────────

@router.get("/clients")
async def list_my_clients(
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Application)
        .where(Application.advisor_id == advisor.id)
        .options(
            selectinload(Application.borrowers),
            selectinload(Application.client),
            selectinload(Application.documents),
        )
        .order_by(Application.updated_at.desc())
    )
    apps = rows.scalars().all()

    clients = []
    for a in apps:
        docs = a.documents or []
        approved = sum(1 for d in docs if d.status == DocumentStatusEnum.approved)
        clients.append({
            "application_id": a.id,
            "client_name": _primary_name(a),
            "status": a.status.value,
            "tier": a.tier.value if a.tier else None,
            "loan_amount": float(a.loan_amount) if a.loan_amount is not None else None,
            "property_value": float(a.property_value) if a.property_value is not None else None,
            "documents_total": len(docs),
            "documents_approved": approved,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return {"clients": clients, "total": len(clients)}


# ── GET /api/advisors/clients/{id} — full client detail ───────────────────────

@router.get("/clients/{application_id}")
async def get_client_detail(
    application_id: str,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.borrowers),
            selectinload(Application.advisor),
            selectinload(Application.client),
            selectinload(Application.documents).selectinload(Document.document_type),
        )
    )
    app = rows.scalars().first()
    if not app:
        raise NotFoundError("Application")
    if app.advisor_id != advisor.id:
        raise ForbiddenError("Not your client")

    detail = _serialize_application(app)
    detail["client_name"] = _primary_name(app)
    detail["documents"] = [
        {
            "id": d.id,
            "name": (d.document_type.name_he if d.document_type else d.manual_label) or "מסמך",
            "status": d.status.value,
            "file_name": d.file_name,
            "required_for_principal_approval": d.required_for_principal_approval,
        }
        for d in (app.documents or [])
    ]
    return {"application": detail}


# ── GET /api/advisors/tasks — advisor's task list ─────────────────────────────

@router.get("/tasks")
async def list_my_tasks(
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Task)
        .where(Task.advisor_id == advisor.id)
        .order_by(Task.is_complete, Task.due_date.nulls_last())
    )
    tasks = rows.scalars().all()
    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "is_complete": t.is_complete,
                "application_id": t.application_id,
                "overdue": bool(t.due_date and not t.is_complete and t.due_date < _date.today()),
            }
            for t in tasks
        ]
    }


class TaskPatchRequest(BaseModel):
    is_complete: bool


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    body: TaskPatchRequest,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(Task, task_id)
    if not task or task.advisor_id != advisor.id:
        raise NotFoundError("Task")
    task.is_complete = body.is_complete
    await db.commit()
    return {"id": task.id, "is_complete": task.is_complete}

from datetime import datetime, timezone
import uuid
from typing import Optional
from app.common.models import Collateral, CollateralStatusEnum

class CreateTaskRequest(BaseModel):
    title: str
    due_date: Optional[_date] = None
    application_id: Optional[str] = None

@router.post("/tasks")
async def create_task(
    req: CreateTaskRequest,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db)
):
    task = Task(
        id=str(uuid.uuid4()),
        advisor_id=advisor.id,
        application_id=req.application_id,
        title=req.title,
        due_date=req.due_date,
        is_complete=False
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id}

class ReviewDocumentRequest(BaseModel):
    action: str
    rejection_reason: Optional[str] = None

@router.patch("/clients/{application_id}/documents/{document_id}")
async def review_document(
    application_id: str,
    document_id: str,
    req: ReviewDocumentRequest,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app or app.advisor_id != advisor.id:
        raise ForbiddenError("Not your client")
        
    doc = await db.get(Document, document_id)
    if not doc or doc.application_id != application_id:
        raise NotFoundError("Document")
        
    if req.action == "approve":
        doc.status = DocumentStatusEnum.approved
        doc.rejection_reason = None
    elif req.action == "reject":
        doc.status = DocumentStatusEnum.rejected
        doc.rejection_reason = req.rejection_reason
    else:
        raise ConflictError("Invalid action")
        
    doc.reviewed_at = datetime.now(timezone.utc)
    doc.reviewed_by = advisor.id
    
    await db.commit()
    return {"id": doc.id, "status": doc.status.value}

@router.get("/clients/{application_id}/collaterals")
async def list_collaterals(
    application_id: str,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app or app.advisor_id != advisor.id:
        raise ForbiddenError("Not your client")
        
    rows = await db.execute(
        select(Collateral).where(Collateral.application_id == application_id)
    )
    collaterals = rows.scalars().all()
    return {"collaterals": [{"id": c.id, "description_he": c.description_he, "status": c.status.value} for c in collaterals]}

class CreateCollateralRequest(BaseModel):
    description_he: str

@router.post("/clients/{application_id}/collaterals")
async def create_collateral(
    application_id: str,
    req: CreateCollateralRequest,
    advisor: User = Depends(require_advisor),
    db: AsyncSession = Depends(get_db)
):
    app = await db.get(Application, application_id)
    if not app or app.advisor_id != advisor.id:
        raise ForbiddenError("Not your client")
        
    collateral = Collateral(
        id=str(uuid.uuid4()),
        application_id=application_id,
        description_he=req.description_he,
        status=CollateralStatusEnum.pending,
        added_by_advisor_id=advisor.id
    )
    db.add(collateral)
    await db.commit()
    await db.refresh(collateral)
    return {"id": collateral.id}
