"""
Documents API — dynamic required-document list + upload/review.
spec: docs/specs/system/05-document-management.md, screens/33

The list is generated from DocumentType.required_condition evaluated against the
application + its borrowers. (No real file storage in this slice — "upload" just
records a file name/status so the UI flow is testable.)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import write_audit
from app.common.auth import get_current_user
from app.common.error_handlers import NotFoundError, ForbiddenError
from app.config.database import get_db
from app.common.models import (
    Application, Borrower, Document, DocumentType, User, RoleEnum, DocumentStatusEnum,
)
from app.modules.documents import storage

router = APIRouter()

# Which condition keys are evaluated per-borrower vs. per-application.
_BORROWER_KEYS = {
    "employment_status", "has_savings_fund", "has_additional_citizenship",
    "is_smoker", "has_health_issues", "has_credit_issues", "has_rental_payment",
}


def _assert_access(current_user: User, app: Application):
    if current_user.role in (RoleEnum.admin, RoleEnum.advisor):
        return
    if app.client_user_id != current_user.id:
        raise ForbiddenError("Not your application")


def _value_matches(required, actual) -> bool:
    if actual is None:
        return False
    if isinstance(required, bool):
        return bool(actual) == required
    if isinstance(required, list):
        actual_val = actual.value if hasattr(actual, "value") else actual
        return actual_val in required
    return False


def _app_matches(condition: dict, app: Application) -> bool:
    for key, required in condition.items():
        if key in _BORROWER_KEYS:
            continue
        if not _value_matches(required, getattr(app, key, None)):
            return False
    return True


def _borrower_matches(condition: dict, borrower: Borrower) -> bool:
    for key, required in condition.items():
        if key not in _BORROWER_KEYS:
            continue
        if not _value_matches(required, getattr(borrower, key, None)):
            return False
    return True


def _new_document(app_id, dt: DocumentType, borrower_id):
    return Document(
        id=str(uuid.uuid4()),
        application_id=app_id,
        borrower_id=borrower_id,
        document_type_id=dt.id,
        is_required=True,
        required_for_principal_approval=dt.required_for_principal_approval,
        is_required_for_approval=dt.required_for_principal_approval,
        status=DocumentStatusEnum.required,
        version=1,
    )


def _expected_pairs(app: Application, doc_types: list[DocumentType]) -> list[tuple[DocumentType, str | None]]:
    """The (document_type, borrower_id) rows this application's data currently requires."""
    borrowers = sorted(app.borrowers, key=lambda b: b.sequence_number)
    primary_id = borrowers[0].id if borrowers else None

    pairs: list[tuple[DocumentType, str | None]] = []
    for dt in doc_types:
        cond = dt.required_condition or {}
        has_borrower_key = any(k in _BORROWER_KEYS for k in cond)
        if not _app_matches(cond, app):
            continue
        if has_borrower_key:
            for b in borrowers:
                if _borrower_matches(cond, b):
                    pairs.append((dt, b.id))
        else:
            pairs.append((dt, primary_id))
    return pairs


async def _sync_documents(app: Application, existing: list[Document], db: AsyncSession) -> list[Document]:
    """Add Document rows for any newly-required (type, borrower) pair without
    touching existing rows (which may already be uploaded/approved). Returns the
    full up-to-date list."""
    dt_rows = await db.execute(select(DocumentType))
    doc_types = list(dt_rows.scalars())
    have = {(d.document_type_id, d.borrower_id) for d in existing if d.document_type_id}

    created: list[Document] = []
    for dt, bid in _expected_pairs(app, doc_types):
        if (dt.id, bid) in have:
            continue
        created.append(_new_document(app.id, dt, bid))
        have.add((dt.id, bid))

    for d in created:
        db.add(d)
    if created:
        await db.flush()
    return existing + created


def _serialize(doc: Document, dt_map: dict) -> dict:
    dt = dt_map.get(doc.document_type_id)
    return {
        "id": doc.id,
        "name": doc.manual_label or (dt.name_he if dt else "מסמך"),
        "description": dt.description_he if dt else None,
        "status": doc.status.value,
        "file_name": doc.file_name,
        "has_file": bool(doc.file_url),
        "version": doc.version,
        "borrower_id": doc.borrower_id,
        "required_for_principal_approval": doc.required_for_principal_approval,
        "rejection_reason": doc.rejection_reason,
    }


# ── GET /api/documents/application/{application_id} ────────────────────────────

@router.get("/application/{application_id}")
async def list_documents(
    application_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(Application).where(Application.id == application_id)
        .options(selectinload(Application.borrowers))
    )
    app = rows.scalars().first()
    if not app:
        raise NotFoundError("Application")
    _assert_access(current_user, app)

    doc_rows = await db.execute(select(Document).where(Document.application_id == application_id))
    docs = list(doc_rows.scalars())
    synced = await _sync_documents(app, docs, db)
    if len(synced) != len(docs):
        await db.commit()
    docs = synced

    dt_rows = await db.execute(select(DocumentType))
    dt_map = {dt.id: dt for dt in dt_rows.scalars()}

    blocking_total = sum(1 for d in docs if d.required_for_principal_approval)
    blocking_done = sum(
        1 for d in docs
        if d.required_for_principal_approval and d.status == DocumentStatusEnum.approved
    )
    return {
        "documents": [_serialize(d, dt_map) for d in docs],
        "blocking_total": blocking_total,
        "blocking_approved": blocking_done,
    }


# ── PATCH /api/documents/{document_id} — upload (client) or review (advisor) ───

class DocumentPatchRequest(BaseModel):
    action: str                     # "upload" | "approve" | "reject"
    file_name: str | None = None
    rejection_reason: str | None = None


@router.patch("/{document_id}")
async def patch_document(
    document_id: str,
    body: DocumentPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise NotFoundError("Document")
    app = await db.get(Application, doc.application_id)
    _assert_access(current_user, app)

    now = datetime.now(timezone.utc)
    before = {"status": doc.status.value}

    if body.action == "upload":
        doc.status = DocumentStatusEnum.uploaded
        doc.file_name = body.file_name or "uploaded-file.pdf"
        doc.uploaded_at = now
        doc.rejection_reason = None
    elif body.action == "approve":
        if current_user.role == RoleEnum.client:
            raise ForbiddenError("Only an advisor/admin can approve documents")
        doc.status = DocumentStatusEnum.approved
        doc.reviewed_at = now
        doc.reviewed_by = current_user.id
        doc.rejection_reason = None
    elif body.action == "reject":
        if current_user.role == RoleEnum.client:
            raise ForbiddenError("Only an advisor/admin can reject documents")
        doc.status = DocumentStatusEnum.rejected
        doc.reviewed_at = now
        doc.reviewed_by = current_user.id
        doc.rejection_reason = body.rejection_reason or "נדרש תיקון"
    else:
        raise ForbiddenError(f"Unknown action: {body.action}")

    await write_audit(
        db, actor_id=current_user.id, action_type=f"document.{body.action}",
        entity_type="document", entity_id=document_id,
        before=before, after={"status": doc.status.value},
    )
    await db.commit()
    await db.refresh(doc)

    dt = await db.get(DocumentType, doc.document_type_id) if doc.document_type_id else None
    return _serialize(doc, {doc.document_type_id: dt})


# ── POST /api/documents/{document_id}/file — real file upload (client) ─────────

@router.post("/{document_id}/file")
async def upload_document_file(
    document_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise NotFoundError("Document")
    app = await db.get(Application, doc.application_id)
    _assert_access(current_user, app)

    version = (doc.version or 1) if doc.file_url is None else (doc.version or 1) + 1
    file_url, file_name = storage.save_upload(file, doc.application_id, doc.id, version)

    before = {"status": doc.status.value}
    doc.file_url = file_url
    doc.file_name = file_name
    doc.version = version
    doc.status = DocumentStatusEnum.uploaded
    doc.uploaded_at = datetime.now(timezone.utc)
    doc.rejection_reason = None

    await write_audit(
        db, actor_id=current_user.id, action_type="document.upload_file",
        entity_type="document", entity_id=document_id,
        before=before, after={"status": doc.status.value, "file_name": file_name},
    )
    await db.commit()
    await db.refresh(doc)
    dt = await db.get(DocumentType, doc.document_type_id) if doc.document_type_id else None
    return _serialize(doc, {doc.document_type_id: dt})


# ── GET /api/documents/{document_id}/file — authenticated download/view ────────

@router.get("/{document_id}/file")
async def download_document_file(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise NotFoundError("Document")
    app = await db.get(Application, doc.application_id)
    _assert_access(current_user, app)

    path = storage.resolve_path(doc.file_url) if doc.file_url else None
    if path is None:
        raise NotFoundError("File")
    return FileResponse(path, filename=doc.file_name or "document")
