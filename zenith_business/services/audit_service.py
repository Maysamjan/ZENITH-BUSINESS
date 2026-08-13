"""Audit trail service (Stage 02 §36).

Records who did what, when. Callers pass an explicit acting user (or the service
reads it from the session) so every business-significant action is attributable.
No passwords, hashes, or secrets are ever written to the audit log.
"""

from __future__ import annotations

from zenith_business.repositories.system import AuditRepository
from zenith_business.services.session import SessionContext


class AuditService:
    def __init__(self, audit_repo: AuditRepository, session: SessionContext) -> None:
        self._audit = audit_repo
        self._session = session

    def record(
        self,
        action: str,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        document_no: str | None = None,
        details: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
    ) -> None:
        """Write an audit row. Falls back to the session user when not overridden.

        Must be called inside the caller's transaction when it accompanies a
        business write, so the audit entry commits or rolls back with the action.
        """
        uid = user_id if user_id is not None else self._session.user_id
        uname = username if username is not None else self._session.username
        self._audit.record(
            action=action,
            user_id=uid,
            username=uname,
            entity_type=entity_type,
            entity_id=entity_id,
            document_no=document_no,
            details=details,
        )

    def recent(self, limit: int = 100) -> list[dict]:
        return self._audit.recent(limit)
