"""System repositories: audit log, document numbering, app settings
(Stage 02 §32, §33, §36, §47).

The sequence allocator is written to be transaction-safe: it must run inside a
service-opened transaction so that reading ``next_number`` and incrementing it
happen atomically and two concurrent documents can never receive the same number.
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def record(
        self,
        *,
        action: str,
        user_id: int | None = None,
        username: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        document_no: str | None = None,
        details: str | None = None,
    ) -> int:
        return self._insert(
            "INSERT INTO audit_log (user_id, username, action, entity_type, entity_id,"
            " document_no, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, action, entity_type, entity_id, document_no, details, now_iso()))

    def recent(self, limit: int = 100) -> list[dict]:
        return self._all(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))

    def for_entity(self, entity_type: str, entity_id: int) -> list[dict]:
        return self._all(
            "SELECT * FROM audit_log WHERE entity_type = ? AND entity_id = ? ORDER BY id DESC",
            (entity_type, entity_id))


class DocumentSequenceRepository(BaseRepository):
    """Gap-free, collision-free document numbering (§32).

    ``allocate`` MUST be called inside a transaction. It reads the current
    ``next_number``, formats the document number, then advances the counter — all
    within the caller's transaction, so a rollback also reclaims the number.
    """

    def get(self, doc_type: str) -> dict | None:
        return self._one("SELECT * FROM document_sequences WHERE doc_type = ?", (doc_type,))

    def ensure(self, doc_type: str, prefix: str, padding: int = 6) -> None:
        self._exec(
            "INSERT OR IGNORE INTO document_sequences (doc_type, prefix, next_number, padding,"
            " updated_at) VALUES (?, ?, 1, ?, ?)", (doc_type, prefix, padding, now_iso()))

    def allocate(self, doc_type: str) -> str:
        seq = self.get(doc_type)
        if seq is None:
            raise KeyError(f"Unknown document sequence: {doc_type!r}")
        number = int(seq["next_number"])
        formatted = f"{seq['prefix']}{number:0{int(seq['padding'])}d}"
        self._exec(
            "UPDATE document_sequences SET next_number = ?, updated_at = ? WHERE doc_type = ?",
            (number + 1, now_iso(), doc_type))
        return formatted

    def peek(self, doc_type: str) -> str | None:
        seq = self.get(doc_type)
        if seq is None:
            return None
        return f"{seq['prefix']}{int(seq['next_number']):0{int(seq['padding'])}d}"


class AppSettingsRepository(BaseRepository):
    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._one("SELECT value FROM app_settings WHERE key = ?", (key,))
        return row["value"] if row is not None else default

    def set(self, key: str, value: str | None) -> None:
        self._exec(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
            " updated_at = excluded.updated_at",
            (key, value, now_iso()))

    def all(self) -> dict[str, str | None]:
        return {r["key"]: r["value"] for r in self._all("SELECT key, value FROM app_settings")}
