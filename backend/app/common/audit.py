"""
Audit log helpers.
Usage in any service:
    await write_audit(db, actor_id, "application.status_changed", "Application", app.id,
                      before={"status": old}, after={"status": new}, ip=request.client.host)
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models import AuditLog


async def write_audit(
    db: AsyncSession,
    actor_id: str,
    action_type: str,
    entity_type: str,
    entity_id: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    log = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before,
        after_value=after,
        ip_address=ip_address,
    )
    db.add(log)
    # The caller's transaction commits the log together with the business operation.
    # Do NOT call db.commit() here — let the service layer own the transaction boundary.
