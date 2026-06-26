"""
Local-disk document storage.

Files live under backend/uploads/{application_id}/{document_id}/{version}_{name}.
The DB stores only the relative path (file_url) + original file_name; the bytes
are served back through an authenticated download route (NOT a public mount),
because mortgage documents are private.
"""

import os
import shutil
from pathlib import Path

# backend/app/modules/documents/storage.py -> parents[3] == backend/
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads"


def save_upload(upload_file, application_id: str, document_id: str, version: int) -> tuple[str, str]:
    """Persist an UploadFile to disk; return (relative_file_url, original_file_name)."""
    safe_name = os.path.basename(upload_file.filename or "file") or "file"
    dest_dir = UPLOAD_ROOT / application_id / document_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{version}_{safe_name}"
    with dest.open("wb") as out:
        shutil.copyfileobj(upload_file.file, out)
    rel = dest.relative_to(UPLOAD_ROOT).as_posix()
    return rel, safe_name


def resolve_path(file_url: str) -> Path | None:
    """Resolve a stored file_url back to an on-disk path, guarding against
    path traversal outside UPLOAD_ROOT. Returns None if missing/escaping."""
    if not file_url:
        return None
    root = UPLOAD_ROOT.resolve()
    p = (UPLOAD_ROOT / file_url).resolve()
    if os.path.commonpath([str(root), str(p)]) != str(root):
        return None
    return p if p.exists() else None
