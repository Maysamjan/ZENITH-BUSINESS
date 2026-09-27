"""Forward migration 0010 — Stage 08 costing & inventory valuation (additive).

Stock has always been the signed sum of ``inventory_movements``. Stage 08 gives
the same rows a second fact — what the stock that moved was **worth** — so value
is derived from exactly the ledger quantity is derived from, and the two can
never tell different stories.

* ``inventory_movements.unit_cost`` — the weighted-average (or acquisition) unit
  cost applied to this movement, at costing precision.
* ``inventory_movements.total_cost`` — quantity × unit_cost, carrying the SAME
  sign as the quantity, so summing the column over any slice gives the value of
  that slice and summing it over sales gives COGS.

Both are nullable so the migration is additive, and both are TEXT for the same
reason every other money column is: exact Decimal arithmetic, never a float.

**Existing databases are back-filled.** A live database already holds purchases
and sales; leaving those movements uncosted would make the first valuation report
tell the owner their stock is worth nothing. The backfill replays each
(item, warehouse) in ledger order through the SAME engine that costs new
movements — there is no second costing path to disagree with.

Nothing is renamed or dropped, and no quantity is touched.
"""

from __future__ import annotations

import sqlite3


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_stage08(conn: sqlite3.Connection) -> None:
    """Migration 0010 — cost columns on the movement ledger, then backfill."""
    columns = _columns(conn, "inventory_movements")
    if "unit_cost" not in columns:
        conn.execute("ALTER TABLE inventory_movements ADD COLUMN unit_cost TEXT")
    if "total_cost" not in columns:
        conn.execute("ALTER TABLE inventory_movements ADD COLUMN total_cost TEXT")

    # Valuation reads slice the ledger by item+warehouse and by date; the
    # movement-type index Stage 06 added already covers the COGS read.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_inv_item_wh_id"
        " ON inventory_movements(item_id, warehouse_id, id)")

    backfill_costs(conn)


def backfill_costs(conn: sqlite3.Connection) -> int:
    """Cost every movement that has none, oldest first. Returns rows costed.

    Idempotent: a movement that already carries a cost is left exactly as it is,
    so re-running the migration never re-values history. Replaying in ``id``
    order matters — a weighted average only means anything in the order the
    stock actually moved.
    """
    # Imported here rather than at module scope: the migration module is loaded
    # by the schema registry at import time, and the engine lives in services.
    from zenith_business.services.costing import MovementCoster

    coster = MovementCoster(conn)
    rows = conn.execute(
        "SELECT id, item_id, warehouse_id, movement_type, quantity, reference_type,"
        " reference_id, reference_line_id FROM inventory_movements"
        " WHERE unit_cost IS NULL OR total_cost IS NULL"
        " ORDER BY id").fetchall()
    costed = 0
    for (mid, item_id, warehouse_id, movement_type, quantity,
         reference_type, reference_id, reference_line_id) in rows:
        unit_cost, total_cost = coster.cost_movement(
            item_id=item_id, warehouse_id=warehouse_id, movement_type=movement_type,
            quantity=quantity, reference_type=reference_type,
            reference_id=reference_id, reference_line_id=reference_line_id,
            # The row already exists during a replay, so exclude it and
            # everything after it: a movement must not be in the average it is
            # about to be priced from.
            before_id=mid)
        conn.execute(
            "UPDATE inventory_movements SET unit_cost = ?, total_cost = ? WHERE id = ?",
            (unit_cost, total_cost, mid))
        costed += 1
    return costed
