# PROJECT_MASTER.md

> **Authoritative development memory for ZENITH BUSINESS (Zenith Soft).**
> This document is the single source of truth for architecture decisions, module
> status, locked contracts, and change history. Consult it at the start of every
> development task. Do **not** silently rewrite previous decisions — propose an
> update and wait for approval.

---

## 0. Document Control

| Field | Value |
|-------|-------|
| Project | Zenith Business |
| Brand | Zenith Soft |
| Master Spec Version | 1.0 |
| PROJECT_MASTER.md Version | 0.1 |
| Current Stage | **00 — MASTER (constitution ratified; implementation NOT authorized)** |
| Database Schema Version | none (no schema yet) |
| Last Updated | 2026-08-11 |

**Stage gate:** Per Master Spec §45, this Master stage does not authorize
implementation. No production code, no database tables, no full project tree.
Next authorized step is **PROMPT 01 — PROJECT FOUNDATION**.

---

## 1. Project Purpose (Spec §1)

A general-purpose, **offline** Windows desktop business-management and accounting
application. **One application, one installation, one core system** — configurable
per business rather than shipped as per-industry editions. Flexibility comes from
configurable master data (accounts, persons, products, categories, units,
warehouses, currencies, cash/bank/income/expense accounts, financial settings).

---

## 2. Technology Stack (Spec §2)

| Concern | Decision | Notes |
|---------|----------|-------|
| Platform | Windows Desktop (primary) | |
| Language | Python | |
| UI framework | PyQt6 | |
| Initial database | SQLite | Business logic kept DB-agnostic to allow future PostgreSQL |
| Connectivity | Fully offline | Internet must not be required for normal operations |
| Money math | `decimal.Decimal` only | Never binary floating point for authoritative values (§20) |

---

## 3. Layered Architecture (Spec §3)

```
UI (PyQt6)
  ↓
Application / Service Layer
  ↓
Domain / Business Logic
  ↓
Accounting Engine · Inventory Engine · Currency Engine
  ↓
Repository / Data Access Layer
  ↓
Database (SQLite → future PostgreSQL)
```

**Strict rule:** UI never directly manipulates accounting balances, stock
balances, ledgers, or financial totals. UI only displays data, collects input,
performs presentation-level validation, calls services, and shows results/errors.
All financial/inventory effects flow through the relevant engines/services.

---

## 4. Core Principles (the constitution — always in force)

These are permanent invariants distilled from the Master Spec. Every module must
uphold them.

1. **Integration over isolation (§5, §44).** Modules are not independent apps.
   Related effects of one business event stay synchronized.
2. **Atomic transactions (§6).** Multi-step financial/inventory operations succeed
   together or roll back together. No partially-posted business transactions.
3. **Double-entry, always balanced (§7).** `TOTAL DEBIT = TOTAL CREDIT`, validated
   programmatically before posting. Posting rules are centralized, never in UI.
4. **Source traceability (§8).** Every auto-generated journal carries
   `source_type`, `source_id`, and a reference number. Navigation must work both
   ways: ledger → journal → source, and source → generated entries.
5. **Flexible Person/Party concept (§9).** No rigidly separated Customer/Supplier
   databases. A Person may buy, sell, owe, or be owed. Financial position derives
   from valid accounting transactions.
6. **Centralized Inventory Engine (§10).** All stock changes create traceable
   movements with product, warehouse, quantity, type, source doc/ID, datetime,
   user, and cost. UI never directly mutates stock.
7. **Weighted Average Cost (§11).** Single, centralized, testable costing engine.
   Sales use the correct cost basis for COGS/gross profit. No duplicated cost logic.
8. **Multi-currency with historical fidelity (§12).** Configurable base currency.
   Transactions preserve currency, foreign amount, rate, and base-currency
   equivalent. Changing today's rate never rewrites historical postings.
9. **Single financial truth (§13).** No independent duplicate versions of a
   balance. Balances derive from authoritative ledger/transaction data (or a
   carefully controlled, reconcilable mechanism). Same for inventory quantities.
10. **Posted-transaction immutability (§14).** Prefer DRAFT / POSTED /
    CANCELLED / VOIDED / REVERSED states over physical deletes. Corrections use
    reversal, not deletion.
11. **Safe reversal (§15).** Cancelling a posted transaction reverses its
    accounting, inventory, receivable, and cash effects while keeping original
    history traceable. Never cascade-DELETE financial tables.
12. **Audit log (§16).** Record user, action, entity, record ID, datetime,
    old/new values, context for CREATE/UPDATE/POST/VOID/REVERSE/LOGIN/
    BACKUP/RESTORE/PERMISSION-CHANGE. Not editable by normal users.
13. **Role-based permissions enforced in the service layer (§17).** Hiding
    buttons is not sufficient; checks must exist below the UI.
14. **Financial years (§18).** Transactions belong to a financial year; support
    open/close, opening/closing balances, controlled posting into closed periods.
15. **Controlled document numbering (§19).** e.g. `SALE-000001`, not raw row IDs.
    Formats later configurable.
16. **Explicit decimal precision & rounding (§20).** For money, rates, prices,
    costs, discounts, taxes, profit, and quantities.
17. **Machine-safe date/time storage (§21).** Storage separate from display
    (Gregorian / Solar Hijri-Jalali presentation planned).
18. **Database integrity (§22).** PKs, FKs, unique, NOT NULL, checks, indexes.
    Do not rely on UI validation alone.
19. **Reports read authoritative data (§29).** Reports never hold independent
    business truth. P&L from accounting; statements from ledger; Kardex from
    inventory movements.
20. **Reconciliation invariants (§31).** Debit=Credit per journal; stock from
    movements = reported stock; ledger totals reconcile with journal lines;
    statements reconcile with ledger.
21. **Priority order (§43):** correctness → integrity → traceability →
    reliability → security → maintainability → performance → UX → appearance.

---

## 5. Accounting Posting Rules (Spec §7 — reference)

Centralized in the Accounting Engine; never hard-coded in UI.

| Event | Debit | Credit |
|-------|-------|--------|
| Credit sale | Accounts Receivable / Customer | Sales Revenue |
| Credit sale (inventory) | Cost of Goods Sold | Inventory |
| Cash receipt from customer | Cash | Accounts Receivable / Customer |
| Credit purchase | Inventory | Accounts Payable / Supplier |
| Expense payment | Expense | Cash / Bank |

**Journal source types (§8):** SALE, SALE_RETURN, PURCHASE, PURCHASE_RETURN,
RECEIPT, PAYMENT, EXPENSE, INCOME, TRANSFER, CURRENCY_EXCHANGE, MANUAL_JOURNAL,
OPENING_BALANCE.

**Inventory movement types (§10):** PURCHASE, PURCHASE_RETURN, SALE, SALE_RETURN,
TRANSFER_IN, TRANSFER_OUT, ADJUSTMENT_IN, ADJUSTMENT_OUT, OPENING_STOCK.

---

## 6. Planned Service Boundaries (Spec §23 — names may be refined)

`AccountingService` · `InventoryService` · `SalesService` · `PurchaseService` ·
`PaymentService` · `CurrencyService` · `ReportingService` · `AuditService`.

No unnecessary abstraction layers. Professional but understandable and maintainable.

---

## 7. Module Status

Development proceeds through numbered module prompts (§32). Only the explicitly
requested module is implemented.

| # | Module | Status |
|---|--------|--------|
| 00 | MASTER (constitution) | ✅ Ratified |
| 01 | Project Foundation | ⏳ Awaiting prompt |
| 02 | Database | ⛔ Not started |
| 03 | Company & Financial Year | ⛔ Not started |
| 04 | Chart of Accounts | ⛔ Not started |
| 05 | Persons | ⛔ Not started |
| 06 | Currencies | ⛔ Not started |
| 07 | Accounting Engine | ⛔ Not started |
| 08 | Products | ⛔ Not started |
| 09 | Warehouses | ⛔ Not started |
| 10 | Inventory Engine | ⛔ Not started |
| … | (Sales, Purchases, Cash/Bank, Reporting, System Mgmt) | ⛔ Not started |

---

## 8. Locked Modules (Spec §33)

_None yet._ When a module is declared **LOCKED**, its public architecture becomes
stable: no renaming of tables/public service methods, no changed accounting
behavior, no removed fields, no changed relationships, no refactored public
interfaces — without explicit authorization. A later module needing such a change
must **STOP** and present: (1) change, (2) necessity, (3) affected components,
(4) migration/compatibility risk, (5) alternatives — then wait for approval.

---

## 9. Public Service Contracts

_None yet._ Populated as services are implemented and locked.

---

## 10. Database Version & Migrations (Spec §35)

Current schema version: **none**. After the initial schema exists, every change is
a migration documented with: old schema, new schema, migration requirement, data
risk, rollback considerations. No casual schema edits.

---

## 11. Open Architecture Questions / Reconciliation Items

No hard internal contradictions were found in Master Spec v1.0. The following are
**design decisions to resolve in the relevant upcoming modules** (recorded here so
they are not forgotten), not conflicts:

1. **Person ledger vs. AR/AP control accounts (§7, §9, §13).**
   §9 mandates a flexible Person concept (no rigid Customer/Supplier split), while
   §7's examples name "AR / Customer" and "AP / Supplier". These reconcile cleanly
   if the Chart of Accounts holds AR and AP **control accounts** and each Person is
   a **subsidiary-ledger dimension** that can simultaneously hold a receivable and
   a payable position. → Decide in **Chart of Accounts (04)** / **Persons (05)**.

2. **Balance strategy: derived vs. maintained (§13).**
   §13 permits either deriving balances from the ledger or maintaining them via a
   controlled mechanism. A single strategy must be chosen and locked.
   **Recommendation:** ledger is the sole source of truth; any running balances are
   a *derived, rebuildable cache* validated by the §31 reconciliation checks.
   → Decide in **Accounting Engine (07)**.

3. **Weighted-average cost under reversal + foreign currency (§11, §12, §15).**
   Reversing a historical purchase or posting foreign-currency purchases affects
   the moving average. An explicit, testable recalculation/adjustment policy is
   required (e.g. how a reversal treats layers already consumed by later sales).
   → Decide in **Inventory Engine (10)**.

4. **Period close vs. immutability (§14, §18).**
   Financial-year close and opening/closing balances need a defined closing-entry
   mechanism that respects posted-transaction immutability.
   → Decide in **Company & Financial Year (03)** / **Accounting Engine (07)**.

These are recommendations only. Per §34, no feature outside the approved
specification will be implemented without prior explanation and approval.

---

## 12. Testing Charter (Spec §30, §31)

Core financial logic must have automated tests covering **normal and failure/edge
cases**, independent of the GUI. Priority areas: debit=credit, sales/purchase
posting, receipts, payments, sales/purchase returns, reversal, inventory movement,
weighted average cost, COGS, multi-currency, account balances, transaction
rollback. Plus the §31 reconciliation invariants. A module is not "complete" if its
required tests fail (§41).

---

## 13. Change Log

| Date | PROJECT_MASTER version | Change |
|------|------------------------|--------|
| 2026-08-11 | 0.1 | Initial constitution captured from Master Spec v1.0 at Stage 00. No production code or schema created. Awaiting Prompt 01 — Project Foundation. |

---

## 14. Module Completion Template (Spec §41)

Every completed module reports:

```
MODULE:
STATUS:
FILES CREATED:
FILES MODIFIED:
DATABASE CHANGES:
PUBLIC SERVICES / METHODS:
ACCOUNTING IMPACT:
INVENTORY IMPACT:
TESTS CREATED:
TEST RESULTS:
KNOWN ISSUES:
DEPENDENCIES FOR NEXT MODULE:
PROJECT_MASTER.md UPDATE REQUIRED:
```

A module is not declared complete if required tests fail.
