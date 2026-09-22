"""What was issued, to whom, and when (Vendor Manager §9).

A vendor who cannot answer "what did I send that customer in March?" has to
guess, and guessing about licences means reissuing one that already exists or
telling somebody their key is wrong when it is not. So every issue is written
down, with the key itself, and nothing is ever silently replaced.

**Append-only by construction.** There is no update and no delete. Reissuing for
the same machine writes a *new* row; the old one stays, because "we sent them a
14-day demo first, then a full licence in May" is exactly the history that
matters. A serial number that has already been used is reported rather than
overwritten.

**This file is vendor-side and contains customer contact details.** It lives
beside the keys, outside the repository, and is never packaged.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from vendor.zenith_license_manager.issuing import IssuedLicense
from vendor.zenith_license_manager.keystore import default_key_dir


def default_history_path() -> Path:
    return default_key_dir().parent / "license-history.json"


def default_license_dir() -> Path:
    return default_key_dir().parent / "licenses"


@dataclass
class Record:
    """One issued licence, as it is written down."""

    created_at: str
    product_id: str
    license_id: str
    license_type: str
    serial: int
    machine_short: str
    machine_fingerprint: str
    issued_to: str
    phone: str
    city: str
    notes: str
    issued_at: str
    expires_at: str | None
    demo_days: int | None
    product_key: str
    zlic_path: str = ""
    status: str = "issued"

    @property
    def search_text(self) -> str:
        return " ".join(str(v) for v in (
            self.license_id, self.license_type, self.machine_short,
            self.issued_to, self.phone, self.city, self.notes,
            self.issued_at, self.expires_at or "", self.product_id)).lower()


class History:
    """The vendor's local record of every licence issued."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_history_path()

    # ---- reading ---------------------------------------------------------

    def load(self) -> list[Record]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        rows = []
        for item in raw if isinstance(raw, list) else []:
            try:
                rows.append(Record(**{k: item.get(k) for k in
                                      Record.__dataclass_fields__}))
            except TypeError:
                continue
        return rows

    def search(self, term: str) -> list[Record]:
        """Newest first, filtered by any field a vendor would remember."""
        rows = sorted(self.load(), key=lambda r: r.created_at or "", reverse=True)
        needle = (term or "").strip().lower()
        if not needle:
            return rows
        return [r for r in rows if needle in r.search_text]

    def next_serial(self, product_id: str, license_type: str) -> int:
        """The next unused number for this product and type."""
        used = [r.serial for r in self.load()
                if r.product_id == product_id and r.license_type == license_type
                and isinstance(r.serial, int)]
        return (max(used) + 1) if used else 1

    def serial_in_use(self, product_id: str, license_type: str,
                      serial: int) -> Record | None:
        for record in self.load():
            if (record.product_id == product_id
                    and record.license_type == license_type
                    and record.serial == serial):
                return record
        return None

    # ---- writing ---------------------------------------------------------

    def append(self, issued: IssuedLicense, *, zlic_path: str = "") -> Record:
        """Write one issue down. Never replaces an existing row."""
        record = Record(
            created_at=issued.created_at, product_id=issued.product_id,
            license_id=issued.license_id, license_type=issued.license_type,
            serial=issued.serial, machine_short=issued.machine_short,
            machine_fingerprint=issued.machine_fingerprint,
            issued_to=issued.issued_to, phone=issued.phone, city=issued.city,
            notes=issued.notes, issued_at=issued.issued_at,
            expires_at=issued.expires_at, demo_days=issued.demo_days,
            product_key=issued.product_key, zlic_path=zlic_path)
        rows = self.load()
        rows.append(record)
        self._write(rows)
        return record

    def set_zlic_path(self, license_id: str, path: str) -> None:
        """Record where a re-exported ``.zlic`` was written."""
        rows = self.load()
        for row in rows:
            if row.license_id == license_id:
                row.zlic_path = path
        self._write(rows)

    def _write(self, rows: list[Record]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        staged = self.path.with_name(self.path.name + ".writing")
        staged.write_text(
            json.dumps([asdict(r) for r in rows], indent=2, ensure_ascii=False)
            + "\n", encoding="utf-8")
        os.replace(staged, self.path)
