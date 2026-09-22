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
| PROJECT_MASTER.md Version | 6.2 |
| Current Stage | **09 — ACCOUNTING REPORTS & FINANCIAL STATEMENTS — 🧪 READY FOR OWNER REVIEW (NOT locked, NOT merged). Stages 01–08 LOCKED. PR #4 NOT merged. Stage 10 not started.** |
| Database Schema Version | **11** (0001 initial_schema, 0002 baseline_seed, 0003 stage03_master_data, 0004 stage04_sales_purchases_returns, 0005 stage05_receipts_payments_expenses, 0006 owner_fixes_walkin_ledger_void, 0007 round2_sales_correction, 0008 stage06_inventory, 0009 stage07_purchases_parity, 0010 stage08_costing_valuation, 0011 stage09_accounting_reports) |
| Last Updated | 2026-09-17 |

**Stage gate:** Stage 00 (constitution) and **Stage 01 (foundation, incl.
01B–01G refinements + typography)** are owner-approved and **LOCKED** (Master
Spec §33): their public architecture/contracts (see §8) are stable and must not
be renamed/removed/refactored without explicit owner authorization.

**Stage 02** (production database, schema/migrations, repository + service
layers, RBAC, authentication, **Login Page + Initial Administrator setup**,
master data, sales/purchase/inventory/ledger foundations, audit, document
numbering, backup/restore) is **owner-approved and LOCKED** (2026-08-14) after
passing the Final Owner Acceptance Test (**PASS WITH FIXES**), and **merged into
`main`**. Its frozen public contracts are recorded in §8; Stage 03 must respect
them (§33 STOP procedure for any change). Stage 02 extended two locked Stage 01 UI
files **additively only** (optional params / new methods, no existing contract
changed). Full architecture: §13H; acceptance record: §13H.10.

**Stage 03** (master data & business setup — unified `parties`, financial years,
company profile, warehouses, units, categories, items, users/roles, search
providers, master-data UI) is **owner-approved and LOCKED** (2026-08-14) and
**merged into `main`** (schema v3). Its frozen public contracts are recorded in
§8 and §13I.

**Stage 04** (Sales, Purchases, Sales Returns, Purchase Returns — atomic document
posting across header/lines/inventory/double-entry ledger/party balance/document
number/audit; financial-year enforcement at the service layer; the unified
`parties` model via additive party links; keyboard-first bilingual EN/Dari-RTL
entry, list, and from-original return screens; per-document A4/A5 printing; live
dashboard) is **owner-approved and LOCKED** (2026-08-16). Its frozen public
contracts are recorded in §8 and §13J. Stage 04 extended locked Stage 01 UI files
**additively only** (an optional `title_key` on the print engine/preview; new
methods on the dashboard/main window — no existing contract changed) and added
forward migration 0004 (schema v4) without editing any shipped migration.
**Stages 01–04 are all locked baselines.**

**Stage 05** (Receipts, Payments, Expenses & the cash/bank/fund foundation — the
real money-movement / settlement layer) is implemented **READY FOR OWNER REVIEW**
(2026-08-17), **not locked, not merged**. It builds additively on locked Stage 04
via forward migration 0005 (schema v5) — an ``is_fund`` flag on the locked
``accounts``, additive party/method/posting columns on the locked ``receipts``/
``payments``/``expenses`` (locked ``customer_id``/``supplier_id`` untouched), and
an ``account_id`` on ``expense_categories`` — with no shipped migration edited and
no locked contract altered. Atomic posting reuses the LOCKED double-entry ledger
and party-balance derivation. Full architecture: §13K. Stage 05 later gained Sales
Reporting and two owner review rounds (§13L–§13O), and is **owner-approved and
LOCKED** (2026-09-04). Its frozen public contracts are in §8 — and the locked
state is Stage 05 **as it stands today**, including the corrections requested
during the Stage 06 verification rounds (in-place `correct_sale`, the derived
`net_view`, the explicit Cash/Credit selector), which supersede parts of §13O.

**Stage 06** (Inventory & Stock Management — the movement ledger made visible:
opening vs current stock, adjustments with a mandatory reason, warehouse
transfers, movement history, low stock, item search, and five A4 reports) is
**owner-approved and LOCKED** (2026-09-04) after manual acceptance testing and
three verification rounds. It builds additively via forward migration 0008
(schema v8) with no shipped migration edited. Its frozen public contracts are in
§8; the architecture and the verification records are in §14A–§14A.3. **PR #4 is
not merged yet.**

**Stage 07** (Purchases Parity — supplier management, the purchase invoice with
Cash/Credit/Partial payment, in-place purchase correction, partial and full
purchase returns, supplier payments and balances, inventory integration, and
purchase print/list consistency) is implemented **READY FOR OWNER REVIEW**
(2026-09-04), **not locked, not merged**, via forward migration 0009 (schema v9).
Stages 05 and 06 are unchanged. Full record: §14B.

Accepted known limitation (owner-approved 2026-08-16): under RTL, space-separated
phone numbers are bidi-reordered inside the LOCKED Stage 01 `SearchSelector`
results panel. This is a cosmetic dropdown-only issue; all persistent data
(document numbers, dates, totals, currency) renders correctly in RTL tables and
fields. The locked `SearchSelector` must **not** be modified to fix it without
explicit owner authorization.

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
| 00 | MASTER (constitution) | ✅ Ratified (on `main`) |
| 01 | Project Foundation (+01B–01G premium UI + typography) | ✅ **LOCKED** (owner-approved) |
| 02 | Database / Auth / RBAC / Service Foundation | ✅ **LOCKED** (owner-approved, merged to main) |
| 03 | Master Data & Business Setup | ✅ **LOCKED** (owner-approved, merged to main) |
| 04 | Sales, Purchases & Returns | ✅ **LOCKED** (owner-approved 2026-08-16) |
| 05 | Receipts, Payments & Expenses (+ Sales Reporting, owner rounds 1–2) | ✅ **LOCKED** (owner-approved 2026-09-04) |
| 06 | Inventory & Stock Management | ✅ **LOCKED** (owner-approved 2026-09-04; PR #4 not merged) |
| 07 | Purchases Parity / Purchase & Supplier Management | ✅ **LOCKED** (owner-approved 2026-09-11; PR #4 not merged) |
| 08 | Costing & Inventory Valuation (weighted average) | ✅ **LOCKED** (owner-approved 2026-09-17; PR #4 not merged) |
| 09 | Accounting Reports & Financial Statements | ✅ **LOCKED** (owner-approved 2026-09-18; PR #4 not merged) |
| 10 | Single-PC Security, Backup & Customer-Side Licensing | 🧪 **READY FOR OWNER REVIEW** (NOT locked, NOT merged) |

---

## 8. Locked Modules (Spec §33)

When a module is declared **LOCKED**, its public architecture becomes stable: no
renaming of tables/public service methods, no changed behavior, no removed
fields, no changed relationships, no refactored public interfaces — without
explicit authorization. A later module needing such a change must **STOP** and
present: (1) change, (2) necessity, (3) affected components, (4) migration/
compatibility risk, (5) alternatives — then wait for approval.

### 🔒 Stage 01 — Project Foundation — LOCKED (2026-08-12, owner-approved)

The following **public contracts are frozen**. Future stages consume them and
must not rename/remove/refactor them without authorization. (Demonstration pages
— `pages/sales_invoice_demo.py`, `pages/dashboard.py`, the mock providers in
`ui/mock/` — are *reference designs*, not frozen business logic; real modules
replace their mock data via the locked provider interfaces.)

**Core (`zenith_business/core/`)**
- `identity`: `IDENTITY`, `AppIdentity`, `COMPANY_NAME/PRODUCT_NAME/APP_VERSION`.
- `paths`: `AppPaths` (config/data/logs/backups/license dirs, `database_file`),
  `resolve_paths()`, `DATA_HOME_ENV`.
- `config`: `AppConfig` (+`LoggingConfig`,`UIConfig`), `load_config()`, language
  constants (`LANG_DARI`,`LANG_ENGLISH`,`SUPPORTED_LANGUAGES`).
- `logging_setup`: `setup_logging()`, `get_logger()`, `ROOT_LOGGER_NAME`.
- `exceptions`: `ZenithError` + `ConfigurationError/DatabaseError/
  TransactionError/SecurityError/LicensingError` (with `user_message`).
- `error_handler`: `install_global_exception_handler()`.
- `i18n`: `Translator`, `Direction`, `resolve_direction()`.
- `numbers`: `amount_in_words(amount, currency, lang)`.
- `fonts`: `load_application_fonts()`, `apply_base_font()`, `FONT_STACK`,
  `FONT_FAMILY` (**Vazirmatn**, bundled). Single typography source of truth.

**Database infrastructure (`zenith_business/database/`)** — no business tables
- `Database`: `connect()`, `connection()`, `close()`, `transaction()` (atomic,
  nested SAVEPOINTs), `foreign_keys_enabled()`, `pragma()`. Pragmas: FK ON,
  busy_timeout, WAL+NORMAL (file DBs). `check_health()` / `DatabaseHealth`.

**Security (`zenith_business/security/`)**
- `passwords`: `hash_password()`, `verify_password()`, `needs_rehash()`
  (PBKDF2-HMAC-SHA256, never plaintext).
- `licensing`: `LicenseProvider` Protocol, `LicenseState`, `LicenseStatus`,
  `DevelopmentLicenseProvider` (dev-only).

**UI design system (`zenith_business/ui/`)**
- `design/tokens`: `Color`, `Spacing`, `Radius`, `ControlSize`, `FieldWidth`
  (XS–XL), `Typography` (`FAMILY` = the font stack). Semantic color roles.
- `design/theme`: `build_stylesheet()`.
- `components`: `Card`, `StatTile`, `LabeledField(compact=)`, `PageHeader`,
  `EmptyState`, `chip`, `eyebrow`, `field_label`, primary/secondary/ghost
  buttons, `standard_icon`, `apply_field_width`, `apply_shadow`, `escape_amp`.
- `widgets/search_selector`: `SearchSelector`, `SearchProvider` Protocol,
  `SearchColumn`, `SearchRow` — the reusable autocomplete architecture.
- `main_window.MainWindow`: top-nav shell (header + primary nav + context bar +
  content stack + status bar).

**Print engine (`zenith_business/ui/print/`)**
- `invoice_document`: `InvoicePrintDocument`, `A4InvoiceDocument`, `PaperSize`,
  `A4`, `A5`, `PAPERS`, `paginate()` (balanced reflow, widow/orphan).

**Locked principles:** single `Typography.FAMILY`/font stack drives app + print;
one `InvoiceData`-style source of truth for screen↔print parity; keyboard-first
+ autocomplete UX pattern (never re-enter known data); cost/profit permission-
gated; genuine RTL. Changing any of the above requires the §33 STOP procedure.

### 🔒 Stage 02 — Database / Auth / RBAC / Service Foundation — LOCKED (2026-08-14, owner-approved)

Owner-approved after Final Acceptance (**PASS WITH FIXES**; acceptance ending
commit `eda3d84`, 212 tests, `integrity_check=ok`, `foreign_key_check=0`, schema
v2). The following **public architecture/contracts are frozen**; Stage 03+ must
respect them and use the §33 STOP procedure to change any of them.

**A. Database foundation** — versioned migration system (`database/migrations.py`:
`Migration`, `MIGRATIONS`, `MigrationRunner.migrate/current_version/pending`),
atomic per-migration application tracked in `schema_migrations`; production schema
(`database/schema.py`, 29 tables, migration 0001) + baseline seed (0002); **schema
version 2**; FK enforcement stays ON; transaction boundaries owned by services via
`Database.transaction()`; canonical UTC ISO-8601 timestamps (`core/clock.py`).

**B. Money / numeric safety** — `core/money.py`: `Decimal` is the financial
standard; **no binary float** for financial calculations; canonical TEXT
persistence (`money`/`quantity`/`rate` = 2/3/4 dp, `ROUND_HALF_UP`); `D()` lenient
for display only; **`parse_decimal`** strict for the write path; business write
paths reject malformed numeric input (`document_math.parse_money_input`).

**C. Repository boundary** (`repositories/`) — repositories own all SQL,
parameterized only; the **UI never executes business SQL**; services consume
repositories. Base helpers `BaseRepository._one/_all/_scalar/_insert/_exec`.

**D. Service layer** (`services/`) — services own business transaction boundaries
and authorization; invalid operations roll back atomically; `ApplicationContext`
(`open_application_context`) is the composition root future modules build on.

**E. Authentication** (`services/authentication.py`, `services/setup.py`) —
PBKDF2 hashing (Stage 01 `security/passwords`); no plaintext credentials; failed-
login lockout (5 → 15 min); inactive/locked-user rejection; Initial-Administrator
setup available only on first run (no default admin); `SessionContext`/`CurrentUser`;
logout clears session.

**F. RBAC** (`services/authorization.py`) — roles→permissions; language-neutral
permission codes; `AuthorizationService.require/can` enforced **below the UI**; UI
visibility is not security; protected actions require authorization on any path.

**G. Financial safety** — double-entry invariant **TOTAL DEBIT == TOTAL CREDIT**;
unbalanced journals prohibited (`document_math.assert_journal_balanced`);
**`FinancialService.post_entry` is the sanctioned guarded journal-posting path**;
future financial modules must preserve atomic posting.

**H. Inventory safety** (`services/inventory.py`) — movement-ledger model; stock =
`SUM(signed movements)`; multi-warehouse isolation; atomic warehouse transfer
(`transfer`); insufficient-stock protection; stockable transactions require
warehouse context (unless a future owner-approved policy changes it); movements
stay transactionally consistent with their source document.

**I. Document posting** (`services/sales.py`, `services/purchases.py`) — atomic
posting of header + lines + inventory + accounting + audit (no partial commit);
transaction-safe document numbering (`services/numbering.py`,
`repositories/system.DocumentSequenceRepository`); rollback reclaims the number.

**J. Audit** (`services/audit_service.py`, `repositories/system.AuditRepository`) —
attributed audit records; **no secrets/passwords/hashes** in audit data; protected
operations integrate with the audit model.

**K. Backup / restore** (`services/backup.py`) — online-backup foundation;
validation (integrity + expected schema) before restore; invalid backups rejected.

**L. Startup / login gate** (`app.py`) — migrations + DB health before the business
workspace; first-run Administrator setup; **authentication gate before MainWindow**
(never straight to dashboard); identity/session passed into the shell.

**M. Stage 02 UI contracts** (`ui/auth/`) — `AuthWindow`, `LoginPage`,
`InitialAdminSetupPage`, `PasswordField`; bilingual EN/Dari, genuine RTL/LTR,
Vazirmatn (inherited from Stage 01); additive `MainWindow`/`HeaderBar` identity +
logout options (backward-compatible — Stage 01 default behavior preserved).

**Not locked by Stage 02 (deferred to Stage 03+):** live Dashboard data, the
production Sales-Invoice UI, and the Sales/Purchase/Receipt/Payment/Expense/
reports/inventory-management/master-data management modules. Stage 02 locks the
**foundation and its contracts**, not these unbuilt modules.

### 🔒 Stage 03 — Master Data & Business Setup — LOCKED (2026-08-14, owner-approved)

Owner-approved after the Final Owner Acceptance Test (**PASS WITH FIXES**;
accepted ending commit `12670e7`, **277 tests**, `integrity_check=ok`,
`foreign_key_check=0`, schema **v3**). Built additively on locked main `b6e633d`;
**no Stage 01/02 locked contract was changed**. The following public
architecture/contracts are **frozen**; Stage 04+ must respect them and use the
§33 STOP procedure to change any of them.

**A. Schema (migration 0003, schema v3) — frozen, additive-only forward.**
`parties` (unified party: party_code UNIQUE, is_customer/is_supplier with DB
`CHECK` requiring ≥1 role, contact/credit/opening/active); `financial_years`
(name UNIQUE, DB `CHECK` start<end, partial unique index = one active year,
status OPEN/CLOSED); additive columns on `companies` (display_name,
registration_number, default_warehouse_id, is_active), `items` (alternate_name),
`units` (decimal_allowed), `warehouses` (notes); indexes for party name/company/
phone/roles and item alternate_name. The locked `customers`/`suppliers` tables
and their FKs remain intact. **Stage 04 consumes `parties` additively** (e.g. new
nullable `party_id` FKs on documents) — it must not repoint or drop locked tables.

**B. Repositories.** `PartyRepository`, `FinancialYearRepository`; the additive
methods added to locked master/user repositories (item alternate_name + broadened
search, unit/warehouse/category update + code_exists, company Stage-03 fields,
user search + `count_active_with_role` + `has_role`).

**C. Services (RBAC + validation + audit + transactions).** `CompanyService`
(single company record; logo stored in the app data dir, never an external path;
default-warehouse reference validated), `FinancialYearService` (valid range,
single active, close/reopen, and the **`is_postable`/`assert_postable` posting
guard** — the sanctioned way future transaction modules enforce open-year
posting), `WarehouseService`, `UnitService`, `CategoryService` (parent supported,
self-parent rejected), `ItemService` (code + optional-unique barcode; strict
non-negative Decimal prices; non-finite/oversized numeric input rejected),
`PartyService` (≥1 role, dup code, non-negative credit), `RoleService` (grouped
human-readable permissions; Administrator keeps all), extended `UserService`
(reset password, set_roles, search) with **last-active-administrator protection**.

**D. Numeric write-path safety.** `document_math.parse_money_input` rejects
malformed, non-finite (NaN/Infinity), and absurdly-large numeric input as
`ValidationError` on every business write path.

**E. Search providers.** `ItemSearchProvider` (name/alternate/code/barcode) and
`PartySearchProvider` (name/company/code/phone, role-filtered) implement the
locked `SearchProvider` Protocol with rich payloads for Stage 04 Sales/Purchases.

**F. RBAC.** The 14 Stage 03 permission codes (company.manage, financialyear.*,
warehouses.*, units.*, categories.*, persons.*, items.create/edit) and their
seeded role grants — enforced below the UI.

**G. UI contracts.** Reusable `ManagementPage` + `FormDialog` framework and the
screens Items, Persons, Warehouses, Categories, Units, Company (incl. logo),
Financial Years, Users, Roles & Permissions; bilingual EN/Dari with genuine RTL;
additive `MainWindow(context=…)` wiring. UI executes no SQL.

**Not locked by Stage 03 (deferred to Stage 04+):** wiring the financial-year
posting guard into transaction posting; the Sales/Purchase/Receipt/Payment/Expense
production modules; live Dashboard data. Stage 03 locks the **master-data
foundation and its contracts**, not these unbuilt modules.

### 🔒 Stage 05 — Receipts, Payments & Expenses (+ Sales Reporting) — LOCKED (2026-09-04, owner-approved)

Owner-approved retrospectively. Stage 05 was treated as locked from the Stage 06
brief onward (*"Stage 05 is LOCKED — do not redesign or expand Sales, Sales Return
or Sales Reports"*) and this record formalises that. **The locked state is Stage
05 as it stands today**, including the corrections the owner explicitly requested
during the Stage 06 verification rounds — not the state described in §13K–§13O,
some of which those rounds superseded. No behaviour is changed by writing this
record. The following are **frozen**; Stage 07+ must use the §33 STOP procedure.

**A. Database (migration 0005, schema v5; plus 0006 and 0007).** `accounts.is_fund`
marking cash/bank/fund accounts; additive `party_id` / `payment_method` / posting
stamps on `receipts` and `payments` (the locked `customer_id` / `supplier_id`
untouched); `payment_method` / `notes` / stamps on `expenses`;
`expense_categories.account_id` so a category maps to a real expense account.
Seeded funds (Cash, Bank, Petty Cash), expense accounts and categories, the RCP /
PAY / EXP sequences, indexes and 10 permissions with role grants. Migration 0006
added the nullable `sales.walkin_name` / `walkin_phone` / `walkin_address`
snapshot columns and the `parties.ledger` permission; migration 0007 added
`sales.corrected_from_id` and the `sales.correct` permission.

**B. Money-movement engine.** `money_s5` repositories and `ReceiptService` /
`PaymentService` / `ExpenseService`, each posting ONE atomic transaction — header
+ metadata + **balanced double-entry journal** + party-balance effect + document
number + audit — reusing the locked `FinancialRepository`, `assert_journal_balanced`
and `PartyBalanceRepository`. Ledger direction is frozen: Receipt Dr fund / Cr AR;
Payment Dr AP / Cr fund; Expense Dr expense account / Cr fund. Financial-year
enforcement, RBAC and strict Decimal validation run before any write. **Balances
are derived from the ledger and are never editable.**

**C. Sale document behaviour (as corrected and accepted).** A walk-in customer is
snapshotted onto the sale and creates no party record and no anonymous receivable.
`void_sale` reverses stock, ledger and balance and stamps VOID, keeping the
original document. **`correct_sale` amends the ORIGINAL invoice in place** — same
row, same document number, difference-only journal, audited line diff. *This
supersedes the void-and-replace description in §13O:* the in-place contract was
adopted at the owner's instruction and is the locked behaviour. **A return never
rewrites the sale**; the current position is derived by `net_view`, which the
Sales List, the reopened invoice, the printed copy, the customer balance and the
reports all read. Sale payment is the operator's explicit **Cash / Credit** choice
with Paid and Remaining derived from the single existing grand-total computation —
never inferred, never typed.

**D. Sales Reporting.** `SalesReportRepository` + `SalesReportService` compute
**Gross / Paid / Credit / Returns / Net** for Today / Week / Month / Year / Custom
plus daily, monthly and yearly breakdowns and per-invoice detail, filtered by date
range, warehouse, customer, payment status and registered/walk-in. Correct by
construction: partial payments split paid vs credit, later receipts are debt
collection and never revenue, a corrected invoice counts once, Gross and Returns
stay separately auditable and Net = Gross − Returns. Money is summed with
`Decimal`, never a SQL aggregate.

**E. Party ledgers.** `PartyLedgerRepository` / `PartyLedgerService` /
`PartyLedgerPage` — running balance and totals for a customer or supplier, derived
from the authoritative ledger; a party that is both customer and supplier is one
identity.

**F. UI and print.** The reusable `MoneyEntryPage` / `MoneyListPage` screens under
Receipts & Payments; the Sales Invoice workspace (registered vs walk-in, dominant
line grid, full pre-post line editing, Cash/Credit selector, Previous / Updated
balance); Account Settings; contextual "View Account". `VoucherPrintDocument`
composes Receipt / Payment / Expense vouchers at **A4 and A5**, EN and Dari RTL,
on the customer's business identity. The **Sales Report prints A4 only** (owner
decision) — A5 remains available for invoices, receipts and vouchers.

**G. RBAC + audit.** 10 service-enforced Stage 05 permissions plus `parties.ledger`
and `sales.correct`; every post, void and correction is audited with actor,
entity, document number and a readable summary, and no secrets. A failed post
rolls back leaving no partial document, balance, journal or audit row.

**Known limitations carried into the lock (intentional).** Documents post directly
to POSTED — there is no DRAFT workflow. The GL is posted in document currency
(original amount and rate are preserved and the base equivalent is derivable);
cross-currency GL consolidation is a later reporting concern. Seeded fund and
expense-account names are English master data the user renames. Under RTL,
space-separated phone numbers are bidi-reordered inside the locked Stage 01
`SearchSelector` dropdown (cosmetic; persisted data is unaffected).

### 🔒 Stage 06 — Inventory & Stock Management — LOCKED (2026-09-04, owner-approved)

Owner-approved after manual acceptance testing of the Stage 06 Windows test build
(commit `a4017ec`, **538 tests**, schema **v8**). Built additively; the only
Stage 05 behaviour changed was what the owner explicitly asked for across three
verification rounds. The following are **frozen**; Stage 07+ must respect them and
use the §33 STOP procedure to change any of them.

**A. Stock is a signed movement ledger — the single source of truth.** On-hand is
the `Decimal` sum of `inventory_movements`; **no table stores a stock figure**, so
no two screens can disagree. Every screen and report reads the same service. The
nine movement types (`OPENING`, `PURCHASE`, `SALE`, `SALE_RETURN`,
`PURCHASE_RETURN`, `ADJUSTMENT_IN`, `ADJUSTMENT_OUT`, `TRANSFER_IN`,
`TRANSFER_OUT`) and the CHECK constraint that enforces them are frozen.

**B. Schema (migration 0008, v8, forward/idempotent).** `inventory_movements.notes`
plus three reporting indexes. No new permission — `inventory.view/adjust/transfer`
already existed.

**C. Opening vs Current are permanently separate.** Opening stock is the `OPENING`
movement recorded once at item creation and never re-recorded on edit; Current is
the running sum. Both are shown side by side in the product list and Inventory.

**D. Engine contracts.** `InventoryReadRepository` (`movements`, `stock_by_item`,
`stock_by_item_and_warehouse`, `warehouse_names_by_item`, `items_with_levels`);
`InventoryService.movement_history / stock_by_warehouse / stock_overview /
low_stock / opening / stock_columns / adjust / transfer / record_opening`;
`InventoryReportService.current_stock / opening_vs_current / stock_by_warehouse /
item_movement / low_stock`. **`adjust()` requires a non-empty reason**, stores it
on the movement, and refuses to remove more than a warehouse holds. Current Stock
is never editable without a movement. A transfer preserves the company total and
blocks over-transfer. A sale validates against CURRENT stock in the selected
warehouse.

**E. Sales-integration contracts (frozen by the owner's three verification rounds).**
`SalesDocumentService.net_view(sale_id)` is the one answer to "what is this
invoice worth now" — per-line `sold` / `returned` / `net_quantity` /
`net_line_total`, `active_lines`, `gross_total`, `returned_total`, `net_total`,
`net_remaining`. The **Sales List, the reopened invoice, the printed copy, the
customer balance and the reports all read it**, and must continue to agree.
`correct_sale` amends the ORIGINAL invoice in place (same row, same document
number, difference-only journal); it refuses only to drop a returned item or go
below the returned quantity. A return never rewrites the sale: sold quantities and
the return document are the historical record. Also frozen: `returned_items`,
`balance_before_sale`, `SalesReturnRepository.returned_lines_for_sale`, the
readable return note, and `InvoiceData.note_key` (an i18n key, never text, so the
sheet follows the language toggle).

**F. UI contracts.** Inventory, Stock Adjustment, Warehouse Transfer and Stock
Movement History screens; five inventory reports printed **A4 only** on the
CUSTOMER's business identity; product list columns Item Code / Name / Unit /
Opening / Current / Warehouse / Low-Stock status; search by code, name or barcode;
the Returned Items panel on a reopened invoice. EN + Dari with genuine RTL.

**Not locked by Stage 06:** the Dashboard's stock widgets, costing/valuation
(FIFO/average), stock-taking sessions, and multi-currency inventory — none are
built. Stage 06 locks the **movement ledger, its reads and the sales-integration
contracts**, not those unbuilt features.

### 🔒 Stage 07 — Purchases Parity / Purchase & Supplier Management — LOCKED (2026-09-11, owner-approved)

Owner-approved after manual acceptance testing of the Stage 07 Windows test build
(tested `5a8ea99`; locked at `c10dfd4`, **600 tests**, schema **v9**). Built
additively on locked Stages 01–06; the only locked-stage behaviour changed is the
one §33 amendment in §13K.2, which the owner approved explicitly. The following
are **frozen**; Stage 08+ must respect them and use the §33 STOP procedure to
change any of them. Full record: §14B.

**A. `PurchaseDocumentService.net_view(purchase_id)` is the one answer to "what is
this bill worth now."** Per line `bought` / `returned` / `net_quantity` /
`net_line_total`; per document `active_lines`, `gross_total`, `returned_total`,
`net_total`, `net_remaining`, `has_returns`. The **Purchase List, the reopened
bill, the printed bill, the supplier balance and the reports all read it** and
must continue to agree. This is the purchase mirror of the frozen sales
`net_view`, and the two must stay symmetric.

**B. A bill is corrected in place, never replaced.** `correct_purchase` amends the
ORIGINAL row — same document number — with surviving line ids preserved so
`purchase_return_lines.purchase_line_id` stays valid, compensating stock
movements, and a **difference-only** journal. It refuses to drop a returned item
or fall below the returned quantity. `void_purchase` reverses stock, ledger and
payable, keeps the document, and is **blocked while a return exists**. A return
never rewrites the bill: bought quantities and the return document are the
historical record. Also frozen: `returned_items`, `balance_before_purchase`,
`PurchaseReturnRepository.returned_lines_for_purchase`.

**C. The purchase payment model (§14B.7).** Cash → Paid = Grand Total,
Remaining 0. Credit → Paid 0, Remaining = Grand Total. **Partial** → the
operator's figure, Remaining = Grand Total − Paid, recalculated live. Paid may
never be negative or exceed the Grand Total. A **later** payment goes through the
existing Supplier Payment module and never touches the bill, so no duplicate
payment or accounting entry is created. Sales keep the strict Cash/Credit model;
Partial is a purchases-only contract.

**D. A purchase with an unpaid balance requires a registered supplier.** A credit
or part-paid bill from an unregistered supplier is refused — an anonymous payable
no ledger can show is an accounting hole. A **fully paid cash** purchase from an
unregistered supplier remains allowed.

**E. Schema (migration 0009, v9, forward/idempotent).**
`purchases.corrected_from_id`, the `purchases.correct` permission with
Admin/Manager/Accountant grants, and an index on
`purchase_returns(purchase_id, status)`.

**F. Suppliers are a VIEW of the shared people, never a second record.**
`SuppliersPage` subclasses `PersonsPage` through its overridable hooks
(`_page_columns`, `_page_config`, `_role_filter_choices`, `_default_role`): one
`parties` master table, one person form, one party ledger. There is **no supplier
table, no supplier form and no second balance**. Every money figure comes from
`party_ledger.supplier_ledger(...)["totals"]`, the same call the Supplier Ledger
screen makes. A dual-role party stays ONE record with both obligations named
rather than netted.

**G. Party ledger totals reconcile (§33 amendment 01, §13K.2).**
`total − paid == balance` holds on **both** the customer and supplier ledgers, for
every party in every state: documents count net of posted returns, and paid /
received includes money settled on the document itself plus the separate
Payment / Receipt documents.

**H. The required consistency chain.** **Purchase List = Purchase Invoice View =
Printed Purchase Invoice = Purchase Return = Supplier Balance = Inventory = Stock
Movement.** Every one reads `net_view` or the movement ledger; none stores its own
copy. Money is summed with `Decimal` in Python, never a SQL aggregate (§24).

**I. Derived-at-render UI contracts.** A line total is **computed** from
qty × price − discount at render time, never read from a stored field. A return
note is **derived in the reader's language** from the return's own lines (Dari
naming the item by its Dari name); a note the operator typed by hand is detected
and preserved verbatim. `InvoiceData.party_kind` selects Bill From / Supplier on a
printed purchase; the sales default is unchanged. Row actions take their size from
the **measured widget**, never from arithmetic over fonts and padding.

**Not locked by Stage 07:** Accounting Reports, costing/valuation, purchase
orders, goods-received notes, landed cost, supplier price history and purchase
approval workflow — none are built. Stage 07 locks the **purchase document engine,
its reads, the payment model and the supplier view**, not those unbuilt features.

### 🔒 Stage 08 — Costing & Inventory Valuation — LOCKED (2026-09-17, owner-approved)

Owner-approved after manual acceptance testing of the Stage 08 Windows test build
(`b0fcd2a`, **644 tests**, schema **v10**). Built additively on locked Stages
01–07; no locked service was modified to obtain costing. The following are
**frozen**; Stage 09+ must respect them and use the §33 STOP procedure to change
any of them. Full record: §14C.

**A. The costing method is WEIGHTED AVERAGE, per (item, warehouse).** One engine,
`services/costing.py`, decides what every movement is worth. No FIFO, no LIFO, no
per-screen cost logic. The average is kept per item **per warehouse**, because
valuation must be reportable per warehouse and a transfer must not change what
the company is worth. A company-level average is always `value / quantity` across
warehouses — never an average of averages.

**B. Cost is captured when the movement happens, and is never re-derived.**
`inventory_movements.unit_cost` and `.total_cost` are historical facts recorded
once, exactly like the quantity. This is not a preference: `correct_purchase`
rewrites its line row **in place**, so after a correction the price a movement was
actually made at is gone, and a cost worked out later would use today's price for
yesterday's receipt. A later edit posts a **new compensating movement**; history
is never rewritten.

**C. The single choke point.** Cost is resolved inside
`InventoryRepository.add_movement`, which every posting path already funnels
through. No route can create stock that nobody costed, and callers pass exactly
what they always passed — cost is derived, never supplied by a caller.

**D. The valuation rules, frozen movement by movement.**

| Movement | Valued at |
|---|---|
| Purchase | the price actually paid — `line total / quantity`, so a discount lowers the cost of the goods |
| Opening stock | the item's purchase price (the only cost figure that exists at that moment) |
| Sale, issue, transfer out | the **current weighted average** of that item in that warehouse |
| Correction / void reversal | the cost the ORIGINAL movement went at — never today's average |
| Purchase return | what was paid for those goods, found through the return's link to the purchase line |
| Sale return | the cost the sale took them out at |
| Transfer in | the **exact value** that left the other warehouse |
| Adjustment in | the current average (so the average is undisturbed); the item's purchase price when there is no stock to average |
| Adjustment out | the current average |

**E. COGS is selected by `reference_type`, not `movement_type`.** The sales side
is `SALE`, `SALES_RETURN`, `SALE_CORRECTION`, `SALE_VOID`. This is a frozen
contract because getting it wrong is invisible: filtering on `movement_type`
counts an original sale **and** its replacement while ignoring the compensating
movement that undoes the first charge, so a corrected invoice reports its goods as
sold twice. COGS is net of sales returns, and `cogs_for_sale(sale_id)` answers for
one invoice.

**F. Gross profit is `net sales − COGS`, and net sales is NOT redefined here.** It
is read from the locked Sales Reporting engine. Margin is reported against net
sales and is left **blank** rather than zero when there are no sales.

**G. Rounding, decided deliberately.** `total_cost` is stored at **money**
precision so every subtotal at every grouping level adds up exactly — sub-cent
storage was tried and rejected because warehouse rows then stopped adding up to
the company total. `unit_cost` keeps finer costing precision as an audit figure.
A transfer moves the **exact paired value** rather than a re-multiplied unit cost,
so company value is unchanged to the cent.

**H. Schema (migration 0010, v10, forward/idempotent).**
`inventory_movements.unit_cost`, `.total_cost`, an `(item_id, warehouse_id, id)`
index, and an **idempotent backfill** that replays an existing ledger through the
same engine. A replay excludes the row being costed (`before_id`) — a movement
must not be inside the average it is about to be priced from.

**I. The report contracts.** `CostingReportService.valuation / cogs /
gross_profit / cogs_for_sale / item_value`, over `CostingReadRepository`. Three
A4-only reports in EN/Dari — Inventory Valuation, Cost of Goods Sold, Gross
Profit — on the Stage 08 print sheet: the customer's business identity (logo,
name, address, phone, email, tax id) from the shared source; **totals rendered
outside the table** so an item count counts items; the count **omitted entirely**
from Gross Profit, whose rows are calculation steps; and Dari pinned to the
bundled **Vazirmatn with no fallback** across title, headers, table, totals and
footer, with English keeping the shared stack. Verified on windows-latest in CI
before every build.

**J. The reconciliation invariants.** Value on hand is the ledger's own
`total_cost` sum; item rows and warehouse rows both add up to the company total; a
transfer never changes company value; every movement carries a cost. Money is
summed with `Decimal` in Python, never a SQL aggregate (§24).

**Not locked by Stage 08:** FIFO/LIFO valuation, a COGS accounting journal, landed
cost, standard costing, revaluation, stock-taking sessions and multi-currency
costing — none are built. Stage 08 locks the **weighted-average engine, the
costed ledger, its reads and the three reports**, not those unbuilt features.

---

### 🔒 Stage 09 — Accounting Reports & Financial Statements — LOCKED (2026-09-18, owner-approved)

Owner-approved after manual acceptance testing of the Stage 09 Windows test build
(`b8a2cfc`, **697 tests**, schema **v12**). Built additively on locked Stages
01–08; **no locked service was modified** and the §33 procedure was not required.
The following are **frozen**; Stage 10+ must respect them and use the §33 STOP
procedure to change any of them. Full record: §14D.

**A. One source, six readings — there is no reporting store.** Every statement
reads `financial_entry_lines` and `financial_entries` directly, so the statements
cannot disagree with each other or with the party ledgers. Money is summed with
`Decimal` in Python, never a SQL aggregate (§24). No statement caches, snapshots
or recomputes a figure another module owns.

**B. The Trial Balance always balances.** Opening / debit / credit / closing per
account, with `closing == opening + debit − credit` per row and **total debits ==
total credits** over the report. `balanced` is a computed assertion, not a label.
A liability or equity account closes **negative** by that formula: it is a credit
balance, and the payable report restates it as the positive amount owed.

**C. Profit & Loss is Net Sales, COGS, Gross Profit, Operating Expenses, Net
Profit.** `Gross Profit = Net Sales − COGS` and `Net Profit = Gross Profit +
Other Income − Operating Expenses`. Net sales is the ledger's revenue account and
is **reconciled against, never replaced by**, the locked Sales Reporting engine.
COGS is account `5000` and sits **above** the gross-profit line; every other
EXPENSE account is operating, so adding an expense account needs no code change.

**D. The Balance Sheet satisfies Assets = Liabilities + Equity.** Because Stage 09
has **no year close** (out of scope by instruction), income and expense balances
are folded into equity as the period's own result (`retained_result`). That is
what makes the identity hold rather than a coincidence: a balance sheet built from
EQUITY accounts alone cannot balance while income and expense accounts are open.

**E. The General Ledger reconciles with the Trial Balance.** For every account,
`general_ledger(account_id).closing == trial_balance` closing for that account,
and `opening + total_debit − total_credit == closing`. Rows carry date, reference
(`entry_no`), description, debit, credit and a **running balance** whose last row
equals the closing. Date and account filtering are supported; with no account
selected, opening and closing are **not** reported, because a running balance
across every account nets to zero and would read as a figure rather than as "not
applicable".

**F. Cash & Bank reconciles with the GL and the Trial Balance.** It reports the
`accounts.is_fund` accounts — opening, money in, money out, closing — and each
fund's closing equals both its Trial Balance closing and its own General Ledger
closing. The total closing is the sum of the fund rows.

**G. Receivables and Payables reconcile with the party ledgers, and the ageing
adds up.** Each party's balance equals that party's customer/supplier ledger, the
report total equals the Trial Balance A/R (and A/P as a credit balance), and the
buckets — **Current, 1–30, 31–60, 61–90, 90+** — add back to the balance, both per
party and in total. Two settlement rules, and the distinction is the contract:

* a **return, correction or void names the document it belongs to**, so it is
  applied to **that** invoice or bill (`SALES_RETURN` / `PURCHASE_RETURN` resolve
  through their parent document; corrections and voids already carry it), and
* a **receipt or payment names nothing**, so it clears the **oldest debt first**.

A credit larger than what remains on its own document spills into the oldest-first
pool, so nothing is created or lost.

**H. The ageing totals row is part of the report, on screen and in print.**
Current / 1–30 / 31–60 / 61–90 / 90+ / Balance, emphasised, beneath the parties
and aligned under the columns it totals. It is held **outside** the data rows —
the Stage 08 rule that a totals row is never counted as a data row — and a
statement whose totals are not per-column does not have one.

**I. COGS posts exactly once, and reverses correctly.** `Dr 5000 Cost of Goods
Sold / Cr 1200 Inventory`, taken from the Stage 08 movement `total_cost` —
**never recomputed and never from the selling price**. Frozen properties:

* **exactly once** is a database guarantee: `source_type='COGS'`,
  `source_id=<inventory_movements.id>` under a partial UNIQUE index, so a repeated
  or concurrent run cannot double-charge;
* each entry is dated by the **movement's own date**, so a past period is correct;
* every report calls `sync()` before reading, so the accounts are never stale;
* a **sales return, correction and void** each post their own costed compensating
  movement, so the journal is their exact reverse with no special case — a return
  reverses at **cost**, not at the selling price;
* the sales side is the Stage 08 set selected by `reference_type`:
  `SALE`, `SALES_RETURN`, `SALE_CORRECTION`, `SALE_VOID`.

**J. GL descriptions name business documents, never internal identifiers.**
`COGS — SALE-000009`, `COGS Reversal — SRET-000001`,
`COGS Correction — SALE-000009`, `COGS Void — SALE-000009`. An
`inventory_movements` row id must not reach a customer-visible report. With no
document to name, the label stands alone rather than falling back to an id.

**K. Period handling is From Date / To Date plus the financial year.** Quick
choices are the active financial year, this year, this month, and custom dates.
**There is no period close and no year close** — out of scope by instruction, and
(D) depends on that absence.

**L. Reporting: A4 only, EN / Dari / RTL, customer business identity.** The
financial statement sheet is a **subclass** of the locked Stage 08 costing
document — Stage 08 is not modified and renders exactly as before. It inherits the
customer's identity (logo, name, address, phone, email, tax id) from the shared
source and Dari pinned to bundled **Vazirmatn with no fallback**; it adds the
columnar totals row and a **bounded, wrapping title**. The title's width is
**pinned, not capped**: a word-wrapping `QLabel` reports a narrow size hint, and an
unbounded one overflowed and printed over the business name. The printed General
Ledger **names its account** — `General Ledger — 5000 Cost of Goods Sold` — and
every sheet carries its period. A figure already shown in a columnar totals row is
not repeated in the totals block.

**M. Schema (migrations 0011 and 0012, v12, forward/idempotent, appended never
edited).** 0011: the COGS uniqueness index, reporting indexes on account / entry
date / party, and the `accounting.reports` permission granted to Administrator,
Manager and Accountant — the statements expose the whole business position and are
gated in the service layer (§17). 0012: a **data-only** rewrite of COGS
descriptions to document references, re-runnable, matching on the old text so an
operator-edited description is left alone.

**Not locked by Stage 09:** period close / year close, retained-earnings posting,
a cash-flow statement, comparative or prior-period columns, budgets, cost centres,
multi-currency presentation and credit terms — none are built. Stage 09 locks the
**six statements, the COGS posting service, the ageing rules and the report
contracts**, not those unbuilt features.

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

## 13. Stage 01 — Project Foundation (implemented, pending review)

Foundation only. No business modules, no database tables (Prompt 01 §31).

### 13.1 Technology & dependencies

| Dependency | Scope | Justification |
|------------|-------|---------------|
| `PyQt6` (>=6.6) | runtime | UI framework (Master Spec §2). |
| `pytest`, `pytest-qt` | dev | Test foundation incl. headless UI (§32). |

- Python target **3.12+**; code kept **3.11-compatible** for CI/dev.
- Windows-safe data locations use the **standard library only** (no extra
  dependency) — `%APPDATA%` / `%LOCALAPPDATA%` with home-dir fallbacks.
- Build/packaging via `pyproject.toml`; console script `zenith-business`;
  module entry `python -m zenith_business`.

### 13.2 Approved project structure

```
zenith_business/
    app.py            # startup orchestration + entry point (Bootstrap + run)
    __main__.py       # python -m zenith_business
    core/             # identity, paths, config, exceptions, logging, i18n, error_handler
    database/         # connection, transaction context, health  (NO business tables)
    security/         # passwords (PBKDF2 readiness), licensing (architecture boundary)
    ui/               # main_window (shell), home_screen
        design/       # tokens, theme (QSS)  — centralized design system
    resources/        # static assets (logo placeholder only)
tests/                # pytest foundation (60 tests)
```

Reserved-but-not-faked: `accounting/`, `inventory/`, `reports/`, `backup/`,
`repositories/`, `services/`, `models/` are **not** created yet — they will be
added by the stages that own them, to avoid empty fake scaffolding (Prompt 01 §3).

### 13.3 Configuration architecture

- Single typed `AppConfig` (+ `LoggingConfig`, `UIConfig`) in `core/config.py`.
- Defaults → overlaid by optional JSON in the user config dir; corrupt config
  raises `ConfigurationError` (never silently ignored). Atomic save.
- No scattered constants; no hard-coded absolute paths (paths via `core/paths`).

### 13.4 Application identity

Central in `core/identity.py`: Zenith Soft / Zenith Business / version `0.1.0` /
channel `development`. Imported everywhere; never duplicated in UI.

### 13.5 Logging architecture

- `core/logging_setup.py`: namespaced `zenith.*` loggers, **rotating** file
  handler (1 MiB × 5) in the user logs dir, console handler in dev.
- Technical logging only — **separate from the future business Audit Log**.
- Never logs passwords/secrets (plumbing only; callers must not pass secrets).

### 13.6 Global exception handling

- `core/error_handler.py` installs a process-wide `sys.excepthook`: logs full
  traceback at CRITICAL, shows a friendly non-technical dialog when a Qt app is
  running, never displays raw stack traces to users, never swallows silently.
- Foundation exception hierarchy in `core/exceptions.py` (`ZenithError` base with
  `user_message`; `ConfigurationError`, `DatabaseError`, `TransactionError`,
  `SecurityError`, `LicensingError`).

### 13.7 Database infrastructure decision

- `database/connection.py` `Database` wraps a single SQLite connection; app
  talks to this, not `sqlite3` directly (keeps a future PostgreSQL path open).
- **SQLite safety pragmas (deliberate, documented):** `foreign_keys = ON`,
  `busy_timeout = 5000ms`, and for file DBs `journal_mode = WAL` +
  `synchronous = NORMAL`. **WAL rationale:** better read/write concurrency while
  remaining crash-safe; `synchronous=NORMAL` is SQLite's recommended companion
  for WAL and gives a sound durability/speed balance for a financial desktop
  app. WAL is skipped for in-memory DBs. *(This is the one non-default SQLite
  choice; flagged here for owner awareness.)*
- **Transactions:** explicit `with db.transaction(): ...` issuing BEGIN/COMMIT/
  ROLLBACK; nested blocks use SAVEPOINTs so composed operations stay atomic
  (Master Spec §6). Driver autocommit disabled (`isolation_level=None`).
- `database/health.py` non-destructive health probe (connection + FK + round
  trip). **No business tables created** — verified by test.

### 13.8 UI architecture

- **Top navigation is mandatory** (Prompt 01 §13): a `QMenuBar` across the top,
  **no permanent left sidebar**. Business menus exist as **disabled
  placeholders** (§33) — nothing appears functional.
- Placeholder top menus (localized): Base Data / Buy & Sell / Receipts &
  Payments / Funds / Account Reports / Item Reports / Tools. Final wording &
  availability defined by later prompts.
- Branded **home screen** (`ui/home_screen.py`): replaceable logo placeholder
  (auto-uses `resources/logo.png` if added — no permanent logo invented, no
  third-party assets), product name, tagline, version. Wrapped in a scroll area.
- **Status bar** shows only real state (§24): company (none), DB health, license
  (development/unlicensed). No faked business values.

### 13.9 Responsive / adaptive UI rules

- Qt **layout managers only** — no absolute x/y positioning.
- Window `minimumSize = 900×600`; starts maximized (configurable); home screen
  scroll area guards small windows. Logical-pixel tokens scale under Windows DPI
  (125%/150%).

### 13.10 RTL / LTR rules

- `core/i18n.py`: Dari (`fa_AF`) → **RTL**, English (`en`) → **LTR**; config may
  force direction (`auto`/`rtl`/`ltr`). Direction applied via
  `QWidget.setLayoutDirection`; **proven both ways** (default Dari RTL, switch to
  English LTR at runtime) and covered by tests + screenshots.
- User-facing shell strings go through a `Translator` (key-based catalog), not
  hard-coded literals. Future stages may migrate to Qt `.ts/.qm` behind the same
  interface.

### 13.11 UI design-system rules (centralized — §15-§18, §22)

- **Single source of truth**: `ui/design/tokens.py` (Spacing, Radius,
  ControlSize, **semantic FieldWidth**, Typography, Color) + `ui/design/theme.py`
  (QSS built from tokens). Applied once to the QApplication.
- **Field/label rule (§16):** field widths are *semantic* (NAME, AMOUNT, DATE,
  QUANTITY, DESCRIPTION, DROPDOWN, …) so labels always get proportionate,
  non-clipping inputs and related fields align. No arbitrary per-screen widths.
- Standard control heights (input 32 / button 34 / table row 30), validation
  state hook (`state="error"`), primary-button variant, table/header styling.
- **Rule for all future modules:** never hard-code sizes/colors/fonts in a
  screen — reference tokens/QSS classes. Fonts use a system/fallback stack
  (Segoe UI / Tahoma / Noto Naskh Arabic / B Nazanin) — no unlicensed fonts
  bundled (§21).

### 13.12 Security foundation

- **Passwords** (`security/passwords.py`): **never plaintext**. PBKDF2-HMAC-
  SHA256, per-password salt, 240k iterations, versioned self-describing format
  (`pbkdf2_sha256$…`), constant-time verify, `needs_rehash`. Stdlib-only;
  upgradeable to Argon2id/bcrypt behind the same interface later.
- **Licensing boundary** (`security/licensing.py`): Protocol + development-only
  `DevelopmentLicenseProvider` (always reports unlicensed dev build). **No keys,
  no secrets, no crypto** generated in Stage 01.
- Business data and license state are **logically separate** on disk (license
  under roaming dir; data under local dir).

### 13.13 Future machine-bound licensing requirement (recorded — do not implement)

Permanent project requirement for the dedicated future **Licensing, Activation &
Application Security Engine** (Prompt 01 §26-§28):

- Machine-bound **lifetime** license; purchased once; permanent for the approved
  machine. No SaaS/subscription requirement.
- Copying the installer **or** the business database must **not** transfer
  activation rights.
- **Offline activation** flow: Customer PC → Activation Request → Zenith Soft
  vendor tool approves → **signed** Activation Code → import → app verifies
  signature + device fingerprint → activate.
- Verification via **asymmetric signatures**: customer app embeds a **public**
  key only; vendor **private** signing key never ships. Never a plaintext key
  comparison.
- Vendor controls approve / reject / deactivate / **transfer** to a replacement
  machine; tolerate reasonable hardware changes; offline verification possible.
- Reserved directories already exist (`license/`) separate from business data.

### 13.14 Testing foundation

- `pytest` + `pytest-qt`; UI tests run **headless** via Qt `offscreen`
  (configured in `tests/conftest.py`); `ZENITH_DATA_HOME` sandboxes all data.
- **60 tests, all passing.** Coverage: imports, identity, paths/separation,
  config load/roundtrip/corrupt/fallback, DB connect, FK enforcement, WAL,
  commit, rollback, nested savepoint rollback, health, logging + rotation,
  i18n + direction, password hash/verify/rehash, licensing boundary, global
  error handler, bootstrap, **assertion that no tables are created**, UI shell
  (title, top menus, placeholder-only business menus, status bar truthfulness,
  RTL default, runtime direction flip). Normal **and** failure/edge cases.

### 13.15 Known issues / items requiring future resolution

- No real logo asset yet (placeholder shown by design — Prompt 01 §14).
- Localization catalog is an in-memory shell subset; a full Qt `.ts/.qm`
  pipeline is deferred (interface is ready).
- WAL journal mode is the only non-default SQLite setting — flagged for owner
  awareness (see 13.7).
- Reserved layers (services/repositories/models/accounting/inventory/reports/
  backup) are intentionally absent until their owning stages.
- Menu keyboard **mnemonics** are escaped for now (`&` shown literally);
  deliberate Alt-mnemonics/shortcuts assigned per module later (§23, §28).

---

## 13B. Stage 01B — UI/UX Foundation Refinement (pending review)

A UI/UX-only correction of Stage 01 (Prompt 01B). The technical foundation
(database, transactions, logging, exceptions, config, security, licensing
interfaces) is **unchanged**; all prior infrastructure tests still pass.

### 13B.1 Professional visual quality requirement (approved direction)

Zenith Business must look like a mature, premium commercial accounting/ERP
desktop product — not a prototype. "Clean" never means "empty/unfinished".
**UI approval requires visual review by the owner; automated tests passing is
not sufficient** to approve or LOCK the UI.

### 13B.2 Chortkeh-style top navigation concept, original Zenith identity

Preserve the concept — **TOP** = navigation, **CENTER** = working area,
**BOTTOM** = status — with an original Zenith visual identity. No left sidebar
as primary navigation. No Chortkeh graphics/assets.

### 13B.3 Three-tier top chrome (structural, business-free)

- **HeaderBar** (deep-navy brand header): brand mark + `ZENITH BUSINESS`
  wordmark + `Zenith Soft`; trailing user placeholder + development marker +
  EN/دری segmented language control. Clicking the brand returns Home.
- **PrimaryNav** (white strip): Home + the seven top categories (اطلاعات پایه،
  خرید و فروش، دریافت و پرداخت، وجوه، گزارش حساب‌ها، گزارش اجناس، امکانات برنامه)
  with a clear selected (underline) state.
- **ContextBar** (secondary command area, Prompt 01B §6): shows the selected
  category's commands. Business commands are **disabled placeholders**; Tools
  exposes enabled **Form/Table preview** commands (design-system validation
  only). Real module commands slot in here later with **no main-window
  redesign**.

### 13B.4 Home screen (redesigned)

Composed brand workspace: hero card (replaceable logo placeholder + product +
system tagline + version chip), a **System Readiness** card (database/language/
license/version — truthful state via chips, **no fake financial numbers**), and
a reserved **Quick Access** area for future modules.

### 13B.5 Design system (expanded, centralized)

- **Semantic color tokens** (§10): background, surface, surface_alt, border,
  text_primary/secondary/muted, primary(+hover/pressed/soft), selected, success,
  warning, danger, info, disabled, plus shell-chrome tokens. No per-widget hex.
- **Typography hierarchy** (§11): brand → page title → section title → body →
  labels → secondary → table header → status; body never below 9pt.
- **Control dimensions** (§12): header/nav/context/statusbar heights, input
  (+compact), button, toolbar-button, table row/header, page margin, section
  gap, field gaps.
- **Semantic field widths** (§13): `FieldWidth.XS/SM/MD/LG/XL` — width matches
  information purpose; labels + controls belong together (§14).
- **Reusable components** (`ui/components.py`): page/section titles, field label,
  chips, primary/secondary/ghost buttons, dividers, `Card`, `PageHeader`,
  `EmptyState`, `apply_field_width`. **Rule: modules compose from these; no
  local restyling.**
- **QSS** (`ui/design/theme.py`) is generated entirely from tokens; ampersands
  in button labels are escaped until deliberate mnemonics are assigned.

### 13B.6 Form / table / dialog / state standards

- **Form template** (`ui/pages/form_demo.py`, §18): page header, grouped
  sections, semantic widths, aligned labels/controls, right-aligned numerics,
  validation `state="error"` message — proves Sales/Purchase/Person/Product can
  share one language. Not a business form; nothing saved.
- **Table template** (`ui/pages/table_demo.py`, §19): styled header, selected
  row, alternating rows, numeric right-alignment, stretch column, scrolling.
  Placeholder rows only; **no business data, no tables**.
- **Dialog standard** (§20): tokens for min width/height + QSS for QDialog/
  QMessageBox; shared confirmation/warning/error language later.
- **Empty/unavailable/loading state** (§23): reusable `EmptyState`; selecting a
  not-yet-built category shows a truthful "module not available" panel.

### 13B.7 RTL/LTR visual rules & adaptive/DPI

- Dari is first-class: nav, labels, inputs, table headers, numerics, status bar,
  and dialog button order all mirror correctly; Latin brand/wordmark stays LTR.
  Verified via screenshots in both directions.
- Layouts only; min window 1024×640; content max-width column keeps proportions
  when maximized; logical-pixel tokens scale under Windows 125%/150%.

### 13B.8 Icon strategy (§21)

No icon library bundled yet. Chrome uses text + a typographic brand mark;
`ControlSize.ICON_*` tokens reserve sizing so an approved, licensed icon set can
be added later without layout changes. No third-party/Chortkeh icons.

### 13B.9 Tests & known issues

- **70 tests pass** (was 60): added design-system tokens/components + form/table
  construction, rebuilt shell tests (primary nav, disabled business commands,
  Tools previews, status truthfulness, RTL default + runtime flip). Fixed a test
  that could block on the global-error modal by patching the dialog (production
  behavior unchanged).
- Known issues: real logo still pending (placeholder by design); form/table
  retranslation updates key texts rather than full rebuild; icon set not yet
  chosen; mnemonics deferred.

---

## 13C. Stage 01C — Premium UI Redesign + Sales Invoice reference (pending review)

A further UI/UX-only redesign (Prompt 01C) raising the shell to a premium
commercial standard and establishing the **Sales Invoice** screen as the visual
reference for all future business forms. Backend untouched; all infra tests pass.
No business tables, no accounting/inventory logic, no persistence.

### 13C.1 Information density (§5)

Spacing/control tokens re-tuned denser for fast daily entry (page margin 14,
section gap 12, input 30 / compact 26, table row 28, header 54 / nav 42 /
context 40) — compact but not cramped. Card padding reduced via `CARD_PAD_*`.

### 13C.2 Grid-based business-form architecture (§2, §4)

Business screens follow **Top** (compact transaction header) → **Center**
(dominant line-item grid) → **Bottom** (totals + operational info + actions),
using the **full workspace width/height**. New building blocks:
`components.StatTile`, `components.LabeledField` (label-above-control for dense
multi-column headers), `apply_shadow` (subtle depth), `escape_amp` (centralized
ampersand escaping for all button factories).

### 13C.3 Sales Invoice prototype — REFERENCE DESIGN (§3)

`ui/pages/sales_invoice_demo.py` — the standard every future transaction screen
(Sales/Purchase invoices & returns, receipts, payments, journal voucher) must
follow. Sections: invoice header (number, date, currency, rate, warehouse,
salesperson, reference, description); customer panel (code, searchable name,
phone, address, previous-balance + credit-limit indicators); **dominant** line
grid (#, item code, item name [stretch], unit, qty, unit price, discount, total,
warehouse, numeric right-aligned, trailing entry row); summary (subtotal,
discount, additional expense, tax, emphasized **Grand Total**, cash received,
credit/remaining); operational stat tiles (current stock, last purchase, last
sale, average cost); bottom action bar (New/Save/Save & Print/Print/Receive
Cash/Close) with **shortcut hints** (F2/Ctrl+S/…). Wrapped in a resizable scroll
area: grid dominates at 1600×900 / 1920×1080, keeps a healthy minimum and
scrolls gracefully at 1366×768. **All figures are labelled demonstration data.**

### 13C.4 Field-width rules (§9)

Central `FieldWidth.XS/SM/MD/LG/XL` applied by meaning — code/date/qty/currency
compact; name/address/description wide; amounts medium + right-aligned;
searchable selectors wide (LG). Long labels never sit beside tiny inputs.

### 13C.5 List/management screen (§12 required screenshot #7)

`TableDemoPage` upgraded with a toolbar (search field, record count, New +
disabled Edit/Delete placeholders) above the styled table — the reference for
future master-data/list screens.

### 13C.6 RTL first-class (§10)

The complete Sales Invoice was verified in Dari RTL: header, customer panel,
line grid (columns mirror, numerics stay right-aligned), totals, operational
tiles, and action bar (button order mirrored, shortcut hints retained). Latin
brand/wordmark stays LTR.

### 13C.7 Screenshots delivered (§12)

Home (Dari, English), Sales Invoice (Dari 1600×900, English 1600×900, 1366×768,
1920×1080), and the list screen — all actual application renders.

### 13C.8 Tests & known issues

**72 tests pass** (added Sales Invoice construction in both directions + StatTile/
LabeledField; adjusted a density assertion). Known issues: real logo still
pending; at 1366×768 the invoice action bar sits just below the fold (small
scroll by design); demo figures are illustrative; icon set still deferred.

---

## 13D. Stage 01D — Rapid Invoice Entry UX + reusable search selectors (pending review)

UI/interaction-only stage (Prompt 01D) turning the Sales Invoice into a
keyboard-first, search-driven data-entry workspace and establishing a **reusable
autocomplete selector** architecture for the whole app. Backend untouched; no
tables, no persistence, no accounting/inventory logic. All data comes from
clearly-separated mock providers.

### 13D.1 Reusable search-selector architecture (§5, §12) — permanent UX rule

`ui/widgets/search_selector.py`: a data-source-agnostic `SearchSelector` driven
by a `SearchProvider` Protocol (`columns()` + `search()` returning rich
`SearchRow`s with display values **and** a structured `payload`). Results render
in an in-window overlay panel (Code/Name/Unit/Stock/Price, etc.) with keyboard
nav (↓ open/next, ↑ prev, Enter select, Esc close) and mouse select.
**Permanent principle:** never make users re-enter data the system already
knows — future modules (items, customers, suppliers, accounts, warehouses,
salespersons, units, categories) reuse this instead of long combo boxes. Stage
02+ supplies repository-backed providers **without changing the UI**.

### 13D.2 Keyboard-first invoice flow (§1-§3)

Item field → type to search → ↑/↓ choose → Enter select → auto-populates code,
name, unit, default price, warehouse, stock, then focuses **Quantity** →
Enter → **Unit Price** → Enter → **Discount** → Enter → commits the line, opens a
fresh line focused on item search. Esc closes suggestions; Delete removes the
selected committed line. Live line-total and grand-total/received/remaining.

### 13D.3 Customer autocomplete (§4)

Same pattern for the customer field (search by name / code / phone; results show
Name/Code/Phone/Balance). On selection the header fills phone, previous balance
(color-coded), and credit limit — no manual re-entry.

### 13D.4 Redesigned invoice workspace (§6-§9)

Denser ERP/POS composition: compact meta row + customer autocomplete on top; the
**line grid is the operational centre** (# | Code | Item Name [stretch] | Unit |
Qty | Unit Price | Discount | Total | Warehouse; monetary right-aligned; active
row uses inline editors + item search); bottom band = quick item info (stock /
last sale / default price) beside an always-visible payment card (emphasized
Grand Total, editable Amount Received, computed Remaining, Cash/Credit
indicator). Platform-style icons on actions with shortcut hints. **Cost & profit
are hidden by default** — a permission-gated note marks where RBAC integrates
(§8). No horizontal scroll at 1366×768 (verified).

### 13D.5 RTL & data separation

Full workflow verified in Dari RTL (header, grid, autocomplete popups, totals,
actions all genuinely mirrored) and English LTR. Mock providers live in
`ui/mock/` and are explicitly non-production (§13).

### 13D.6 Tests & known issues

**80 tests pass** (added provider matching, selector open/keyboard-select/hide,
and invoice item/customer population + line-commit + RTL construction). Known
issues: barcode/alternate-name matching and true per-cell in-grid editing are
represented at prototype fidelity; real providers/permissions arrive in later
stages; logo/icon-set still pending.

---

## 13E. Stage 01E — Premium color system + printed A4 invoice (pending review)

UI/print-only stage (Prompt 01E). Adds an intentional semantic color system, more
visual character to the Sales Invoice, and a real customer-facing **A4 printed
invoice** driven by the same demo transaction. Backend untouched; no tables, no
persistence.

### 13E.1 Semantic color system (§14) — centralized

New tokens in `ui/design/tokens.py`: secondary **accent** (teal), workspace
gradient, and financial/status roles — positive/negative value, cash/credit/
partial, in/low/out stock, selected-row vs **active-editing-row**, search-
selection, input focus, read-only, and an ink-friendly **print** palette.
Applied by meaning, not decoration:
- Grand Total → strong filled brand bar (max emphasis).
- Cash → success chip; Credit/Remaining → warning/red; debt → red.
- Stock tile → success / warning / danger by level.
- Active invoice row → warm tint + amber marker (distinct from committed rows).
- Selected autocomplete result → accent background.
- Save → primary; **Delete → destructive** variant.

### 13E.2 Sales Invoice visual character (§15)

Subtle workspace gradient behind cards; accent-topped section cards (navy header,
brand grid + payment, teal operational); stronger financial typography; colored
balance/credit indicators; icons + shortcut hints retained. Reads as the flagship
transaction screen, not a database form.

### 13E.3 Printed A4 Sales Invoice (§16-§19)

New print architecture: `ui/print/invoice_document.py` (`A4InvoiceDocument`,
794×1123) + `ui/pages/print_preview.py` (preview workspace with Back/Print). A
real customer document — company block + logo, `SALES INVOICE` identity, Bill-To,
items table (`# | Item | Qty | Unit | Unit Price | Discount | Total` — no
internal warehouse/stock/cost), summary (Subtotal/Discount, prominent **Grand
Total**, Amount Paid green, Remaining red), and footer (Prepared By / Customer
Signature / Authorized Signature / notes / thank-you). Ink-friendly (white page,
restrained navy accents; readable in grayscale). **English LTR and Dari RTL**
both genuinely laid out. Driven by `ui/mock/demo_invoice.py` — the **same
transaction** shown on screen; **Save & Print / Print** open the preview in-app.

### 13E.4 Tests & known issues

**84 tests pass** (added demo-invoice totals, A4 document EN/RTL construction,
print-preview page, and the Save & Print → preview workflow using the same
transaction). Known issues: company details are placeholder/configurable; real
print-to-paper/PDF export is a later stage; logo remains a placeholder.

---

## 13F. Stage 01F — One-screen workspace, Home dashboard, print reflow (pending review)

Major UI/print pass (Prompt 01F). Backend still untouched; no tables, no
persistence.

### 13F.1 Sales Invoice = one-screen workspace (§2)

The invoice page is now non-scrolling: header/customer, the (dominant) line
grid, totals+payment and the action bar all fit **one screen at 1366×768** with
no page scroll; the grid stretches on larger resolutions. Header compacted;
on-screen fields **bound to the shared transaction** so screen == print (§11 —
fixes the earlier date mismatch: date now shows the invoice's real date).

### 13F.2 Home business dashboard (§5)

`ui/pages/dashboard.py` replaces the branded home: KPI tiles (today's sales/
purchases, cash, receivables, payables, profit — colored by meaning), Quick
Actions (New Sale wired to the invoice; others reserved), Recent Transactions
(colored amounts) and Low Stock (low/out chips). Compact, operational, EN + Dari.
Old `home_screen.py` removed.

### 13F.3 Print engine — reflow, A4 + A5, multi-page, amount-in-words (§6-§10)

New paginated engine `ui/print/invoice_document.py`:
- **A4 and A5** presets, each with its own density (scale, row height, margins,
  capacity) — A5 is not a scaled A4.
- **Content reflow (§7):** short invoices compose compactly (items → totals →
  amount-in-words → footer stacked; no half-page gap); long invoices continue
  onto more pages with **repeated document + table headers, page numbers, and
  totals kept on the final page**; `paginate()` guarantees each page has ≥1 row.
- **Amount in words** from the actual grand total, English **and** Dari
  (`core/numbers.py`).
- Genuine RTL for Dari (header, columns, totals, words, signatures).
- Preview page gains an **A4/A5 toggle**; Save & Print opens it with the same
  transaction.

### 13F.4 Color / density / consistency (§1, §4, §13, §14)

Denser tokens (smaller tiles), workspace gradient, accent-topped cards and the
strong filled Grand Total carried across dashboard, invoice and print. Cost/
profit remain permission-gated. Barcode-scan increment behavior is noted as a
future configurable interaction (not yet wired).

### 13F.5 Tests & known issues

**88 tests pass** (added amount-in-words EN/Dari, print pagination reflow,
multi-page A4, A5 single-page). Known issues: barcode scanning not yet wired;
A5 header is tight (company name/title proximity); KPI/recent data is mock;
print-to-paper/PDF export is a later stage.

---

## 13G. Stage 01G — Final visual-quality & print-composition pass (pending review)

Graphic-design/document-composition pass (Prompt 01G). Backend untouched.

### 13G.1 Printed invoice redesigned as a document (§1, §4)

Rewritten `ui/print/invoice_document.py`: company identity block + boxed
invoice-identity panel (A4), accent-bar **Bill To** section, clean item table
(dark header, row-rhythm separators, **no Excel gridlines**), a single coherent
**financial summary panel**, amount-in-words in an accent strip, redesigned
signatures (thin lines, no gray rectangle).

### 13G.2 A4 vs A5 are genuinely different compositions (§2)

A4 = spacious header with a boxed identity panel and **3 signature columns**;
A5 = compact inline header, single-row Bill To, tighter table/typography and
**2 signature columns**. Not a scaled A4.

### 13G.3 Collision/overflow fixed (§5)

Grand Total is **stacked** (label above value), and numeric columns are sized
for large values — verified with a 13,024,800.00 grand total and 12,448,800.00
line total on both A4 and A5 (no clipping/collision). Long company/customer/item
names wrap or truncate cleanly.

### 13G.4 Balanced short & multi-page composition (§3, §6)

Short invoices center the closing+signatures block for a complete look (no
top-crammed layout, no fake stretch). `paginate()` now distributes rows evenly
with widow/orphan control (22 items → **11 + 11**, not 24 + … + 1); repeated
headers, page numbers, and totals stay on the final page.

### 13G.5 Print-preview workspace (§7)

`ui/pages/print_preview.py` rebuilt: **Paper A4/A5**, Orientation (Portrait),
**Language EN/Dari**, **Zoom −/+ with Fit Width / Fit Page**, and Print. The
document renders to a scaled pixmap so zoom/fit behave like a real preview.

### 13G.6 Screen & dashboard hierarchy (§8-§10)

Operational info is now a **compact contextual strip** (not a form section);
dashboard KPI tiles gain **colored accent left-borders** for scannability, with
Recent Transactions as the center and Low Stock as the alert panel. One-screen
1366×768 invoice preserved.

### 13G.7 Tests & known issues

**88 tests pass** (balanced-pagination assertion added). Known issues: invoice
header secondary fields (warehouse/salesperson/currency/rate) are not yet
visually de-emphasized (§8 partial); very long item names truncate on A5;
print-to-paper/PDF export is a later stage.

---

## 13H. Stage 01 refinements — header hierarchy + global typography (pending review)

Two global UI-foundation refinements requested before approval. Backend untouched.

### 13H.1 Global Dari/Persian typography system (permanent rule)

- **Font: Vazirmatn (SIL OFL 1.1)** — bundled in `zenith_business/resources/fonts/`
  (Regular/Medium/SemiBold/Bold) with its license. A high-quality Persian/Dari +
  Latin typeface with proper Arabic shaping, clear numerals and weight hierarchy.
- **Centralized loader** `core/fonts.py` registers the bundled fonts at startup
  (`apply_base_font`) and exposes `FONT_STACK`. The single `Typography.FAMILY`
  token now leads with Vazirmatn and is used by **both** the app theme and the
  printed documents — so navigation, dashboard, forms, labels, inputs, buttons,
  tables, dialogs, the Sales Invoice, the print preview, printed invoices and all
  **future Stage 02+ screens inherit it automatically** (no per-screen fonts).
- One family covers Persian, Latin and Western digits with a consistent baseline,
  so mixed content (`فروش امروز` · `128,400 AFN` · `SALE-000001` · `1404/02/03`)
  aligns cleanly. Dari now reads as a first-class, native, professional UI/print,
  not a lower-quality localization.

### 13H.2 Sales Invoice header hierarchy (§8)

Primary vs secondary is now explicit and systematic (design-system level, not
per-page): **Customer** is promoted to the top with an accent **eyebrow** label
and a prominent search field + balance/credit/phone chips; **Invoice No/Date**
stay normal; **Warehouse/Salesperson/Currency/Exchange Rate** become a **compact,
quieter** metadata strip (smaller muted labels, lighter/shorter inputs) via a new
`LabeledField(compact=True)` variant and shared QSS. One-screen 1366×768,
keyboard workflow, alignment, RTL/LTR and EN/Dari consistency all preserved.

### 13H.3 Tests & changed files

**90 tests pass** (added font-system tests). Changed: `core/fonts.py` (new),
`resources/fonts/*` (Vazirmatn + OFL), `app.py`, `design/tokens.py`,
`design/theme.py`, `components.py`, `pages/sales_invoice_demo.py`,
`print/invoice_document.py`, `pyproject.toml`.

---

## 13H. Stage 02 — Production Database, Authentication & Login (READY FOR REVIEW)

Stage 02 turns the Stage 01 database *infrastructure* into a real production
data platform and adds the authentication foundation, including the Login Page
and Initial-Administrator setup. **Not locked, not merged.** Built strictly on
the Stage 01 `main` baseline; the only touches to locked UI files are additive
(optional constructor params / new methods on `MainWindow` and `HeaderBar`) — no
existing Stage 01 public contract was renamed, removed, or behaviorally changed.

### 13H.1 Database architecture (§3, §24, §35, §38)
- **Money/quantity/rate are Decimal, never float** (`core/money.py`): stored as
  canonical TEXT (`money` 2dp, `quantity` 3dp, `rate` 4dp), `ROUND_HALF_UP`,
  floats routed through `str`. All aggregates (stock, ledger balance) are summed
  with `Decimal` in Python — never a float SQL aggregate.
- **Timestamps are canonical UTC ISO-8601 TEXT**, dates `YYYY-MM-DD`
  (`core/clock.py`); Jalali is display-only.
- **Schema (`database/schema.py`, migration 0001)** — 29 production tables:
  currencies, users, roles, permissions, user_roles, role_permissions,
  exchange_rates, units, categories, warehouses, companies, items, customers,
  suppliers, accounts, financial_entries, financial_entry_lines, sales,
  sales_lines, purchases, purchase_lines, inventory_movements, receipts,
  payments, expense_categories, expenses, document_sequences, audit_log,
  app_settings (+ `schema_migrations` created by the runner).
- **FK policy:** `RESTRICT` protects business/financial history; `CASCADE` only
  for pure mapping/child rows (user_roles, role_permissions, *_lines).
- **Inventory is a signed ledger:** on-hand = SUM(movements.quantity).
- **Migrations (`database/migrations.py`)** — integer-versioned, each applied
  once inside an atomic transaction (rollback on failure), tracked in
  `schema_migrations`. 0001 initial_schema, 0002 baseline_seed. Idempotent.
- **Baseline seed (migration 0002)** — production-safe system data only: 34
  permission codes, 7 roles (Administrator = all), role→permission grants, 4
  currencies (AFN base), 8 units, 10-account chart, 6 document sequences. **No
  fake customers/items/sales.**

### 13H.2 Layered data access (§4, §47, §48)
- **Repositories** (`repositories/`, own all SQL, parameterized): base, users
  (User/Role/Permission), master (Unit/Category/Warehouse/Currency/ExchangeRate/
  Item/Customer/Supplier/Account/Company), documents (Sales/Purchase/Inventory/
  Receipt/Payment/Expense/Financial), system (Audit/DocumentSequence/AppSettings).
- **Services** (`services/`, own transactions + authorization): SessionContext +
  CurrentUser, AuthorizationService, AuditService, DocumentNumberService,
  AuthenticationService, InitialSetupService, UserService, SalesService,
  PurchaseService, InventoryService, BackupService. `ApplicationContext`
  (`services/context.py`) is the composition root; `open_application_context`
  migrates then wires everything. **The UI never executes SQL.**

### 13H.3 Authentication, RBAC & sessions (§10–§16)
- PBKDF2 verification (reuses Stage 01 `security/passwords.py`), transparent
  rehash-on-login when parameters strengthen. **No plaintext passwords/secrets
  in logs or audit.**
- Failed-attempt lockout: 5 attempts → 15-minute lock; auto-unlock after window.
  Inactive accounts refused. Generic error messages (never reveal which field).
- Permissions enforced at the **service layer** (`AuthorizationService.require`),
  not only in the UI — verified by tests that call services directly.
- Language-neutral permission codes; behavior driven by permissions, not role
  names. Roles: Administrator/Manager/Cashier/Salesperson/Accountant/Warehouse/
  Viewer.

### 13H.4 Startup gate, Login & Initial Setup (§2, §11)
- Production startup: APP START → LICENSE → DB OPEN + MIGRATIONS + HEALTH →
  INITIAL-SETUP CHECK → **AUTH GATE (setup/login)** → load user/roles/perms →
  MainWindow. Production never opens straight into the Dashboard.
- **Initial Administrator setup** (first run only, empty user table): owner types
  a real username + policy-compliant password. **No insecure default admin**
  (`admin`/`admin` is forbidden by the password policy).
- **Login Page** and setup are built entirely from the Stage 01 design system
  (tokens, Vazirmatn typography, components), genuinely bilingual (EN LTR / Dari
  RTL), with Show/Hide password and an EN/دری switch. Sign-out returns to the
  gate without restarting the process.
- Non-breaking UI extension: `MainWindow`/`HeaderBar` show the signed-in user +
  role and a Sign Out action, and the status bar shows the configured company
  name — all via optional params, defaulting to the unchanged Stage 01 behavior.

### 13H.5 Transactional integrity (§29, §32, §34)
- `SalesService.create_and_post` / `PurchaseService.create_and_post` post header
  + lines + inventory movements + **balanced double-entry ledger** + audit in
  ONE atomic transaction; any failure rolls back everything and reclaims the
  document number. Verified: debit == credit; failed post leaves zero rows and
  an unchanged next number.
- Document numbering (`document_sequences`) is transaction-safe (read+increment
  inside the caller's transaction; nested via SAVEPOINTs).

### 13H.6 Audit, backup, settings (§36, §41)
- Every business-significant action is audited with attribution (never secrets).
- Backup uses SQLite's online backup API to a timestamped file; restore validates
  integrity + expected schema before replacing the live DB.

### 13H.7 Tests & delivery
- **144 tests pass** (90 Stage 01 unchanged + 54 new): money/Decimal, clock,
  migrations/seed, auth + lockout + setup, authorization, users service, sales &
  purchase posting (totals/inventory/ledger/rollback/permission), numbering,
  backup/restore, master data, and the auth UI flow (setup→login, error state,
  RTL). One Stage 01 test (`no business tables`) was repurposed to assert the
  Stage 02 migrated schema — a deliberate, documented supersession.
- Required screenshots self-inspected: Login EN/Dari, Initial Admin EN/Dari,
  Login error state, Main Window after auth (EN/Dari) — all correct, RTL genuine.

### 13H.8 Known items for later stages (not blockers)
- Dashboard/Sales-Invoice screens still render Stage 01 demonstration data; wiring
  them to live repositories is a later-stage UI task.
- Receipts/payments/expenses have repositories + schema; dedicated posting
  services beyond the sales/purchase flagship are deferred to their modules. Their
  repositories are low-level primitives — the Stage 03 modules must post them
  through `FinancialService.post_entry` (the guarded journal API) and validate
  amounts, exactly as sales/purchases already do.

### 13H.9 Final technical audit & hardening (2026-08-13)
A strict production-level audit was performed across 7 passes (architecture/schema,
functional/integration, adversarial, security/RBAC, migration/backup/integrity,
UI/RTL, regression). Adversarial probes found real gaps, all **fixed at the service
layer** (no Stage 01 contract touched):

- **Unbalanced journals could commit** → added `document_math.assert_journal_balanced`
  + `FinancialRepository.entry_balance`; sales/purchase posting now assert balance
  before commit, and a new **`FinancialService.post_entry`** is the only sanctioned
  (guarded) journal API for future modules. Unbalanced entries roll back.
- **Sales could oversell into negative stock** → stockable lines now require a
  warehouse and enough on-hand stock (checked before any write); `InsufficientStockError`.
  An explicit `allow_backorder=True` escape hatch exists for businesses that permit it.
- **Silent inventory hole** (stockable item sold with no warehouse) → now rejected.
- **Negative price / negative discount / discount > line total** → rejected by the
  shared `document_math.compute_line` validator (used by sales *and* purchases).
- **Warehouse transfer foundation** added: `InventoryService.transfer` posts an atomic
  `TRANSFER_OUT`/`TRANSFER_IN` pair (stock-checked) so totals are always conserved.

Reporting **indexes** added to migration 0001 (unmerged, so amended in place):
`financial_entry_lines(account_id)`, `financial_entries(source_type, source_id)`,
`audit_log(entity_type, entity_id)`. Query plans confirmed index use for login,
account-ledger, journal-by-document, and barcode lookups.

**Audit verification results:**
- Money: no `float(`/`REAL`/`DOUBLE`/float SQL aggregate in Stage 02 code; edge values
  (0, 0.01, 0.10, 1.10, 10.99, 999999999.99, 1e12) round-trip exactly; repeated
  fractional sums exact.
- Accounting: sale/purchase/manual journals balance (debit == credit); unbalanced
  rejected; rejected operations leave zero partial rows and reclaim document numbers.
- Inventory: stock == SUM(signed movements); multi-warehouse isolation + conservation;
  transfer atomic; insufficient-stock blocked; rollback leaves no movement.
- Security: no plaintext password/hash stored or logged/audited; lockout after 5;
  success resets counter; inactive rejected; malformed input rejected; RBAC enforced
  below the UI (role→permission matrix); session cleared on logout; setup cannot re-run.
- Migrations: empty DB, already-current DB, repeated run (idempotent), and simulated
  **failure** (partial rolled back, version not marked) all verified.
- Backup/restore: real file-DB backup → mutate → restore → data rolls back to backup
  point; invalid file rejected; `PRAGMA integrity_check = ok` and
  `PRAGMA foreign_key_check` = 0 violations after complex transactions and after restore.
- Full **end-to-end** on a real on-disk database incl. simulated restart (data +
  document numbering persist) and backup/restore.

**Tests: 191 pass** (was 144 at first submission; +47 audit/adversarial/integration
tests). Stage 01 contracts unchanged. Status remains **READY FOR OWNER FINAL REVIEW —
not locked, not merged.**

### 13H.10 Final Owner Acceptance Test (2026-08-13)
A full production-readiness gate was executed against a **fresh on-disk SQLite
database** (not in-memory), driving the real services end to end and verifying
persisted data directly, with DB close/reopen between steps.

- **Acceptance date:** 2026-08-13 · **Branch:** `claude/zenith-business-architecture-ywcgpe`
- **Starting commit:** `b0e7420` · **Ending commit:** recorded in the change log below
- **Schema version:** 2 · **Migrations:** 0001+0002 applied · **Tables:** 29 (+`schema_migrations`)
- **Baseline tests:** 191 → **Final tests: 212** (+21)

**Real business workflow (all verified against persisted rows, across restarts):**
Admin setup → login → master data (2 warehouses, 3 stockable items, customer,
supplier) → **purchase** (Rice 100 / Oil 50 / Sugar 40; total 245,000.00; balanced
journal) → **sale** (Rice 25 @1980 −50, Oil 10 @320, Sugar 8 @2600; total 73,450.00;
stock → 75/40/32) → **transfer** 20 Rice Main→Showroom (55 / 20; company 75 conserved)
→ **second sale** 5 Rice from Showroom (Showroom 15, Main 55, company 70).

**Defect found & fixed during acceptance (root cause, not test patch):**
- *Malformed numeric input silently coerced to 0.00* (e.g. price `"12x3"`) — the
  lenient display helper `D()` was on the write path, so a garbage price would post
  a zero-value line. **Fixed** by adding a strict `money.parse_decimal` and routing
  all service write inputs (document lines, `amount_paid`, journal debit/credit,
  inventory quantities) through `document_math.parse_money_input`, which **rejects**
  malformed input (`ValidationError`) instead of zeroing it. Regression tests added.
  `D()` stays lenient for display only. Severity: Medium.

**Adversarial results:** oversell rejected with zero partial state and unconsumed
document number; negative/zero qty, negative price, negative discount, discount>line,
malformed decimal, and stockable-without-warehouse all rejected pre-write; unbalanced
manual journal (`FinancialService.post_entry`) rejected + rolled back, balanced posts.
Auth: wrong/blank user+password, inactive, and lockout (blocks even the correct
password) all rejected; logout clears session; protected op after logout fails; relogin
fresh. RBAC via direct service calls: Salesperson blocked from admin-user creation,
backup, cost visibility, settings. Setup cannot re-run. FK RESTRICT blocks deleting a
customer/item/warehouse referenced by history; duplicate username/item_code rejected.
Backup→mutate→restore rolls back post-backup data, keeps pre-backup data, auth+schema
intact; invalid restore file safely rejected. `integrity_check=ok` and
`foreign_key_check=0` after the full workflow and after restore. Every journal balances;
inventory == SUM(signed movements) for every item×warehouse.

**Recommendation:** *STAGE 02 IS TECHNICALLY READY FOR OWNER APPROVAL TO LOCK AND MERGE.*
Not locked, not merged — owner decision only.

---

## 13I. Stage 03 — Master Data & Business Setup (READY FOR OWNER REVIEW)

Converts the locked foundation into the first operational master-data layer.
**Not locked, not merged.** Built on locked main (`b6e633d`); the 212-test gate
passed before implementation. Owner-approved architectural decision: parties use
an **additive unified `parties` table** (Option A) — no locked Stage 02 contract
touched.

**Database (migration 0003, schema v3, forward/idempotent):** adds `parties`
(unified customer/supplier, DB CHECK requires ≥1 role) and `financial_years`
(DB CHECK start<end, partial unique index = one active year); additive columns on
`companies` (display_name, registration_number, default_warehouse_id, is_active),
`items` (alternate_name), `units` (decimal_allowed), `warehouses` (notes); 14 new
permission codes granted to Administrator + relevant roles; indexes for parties
name/company/phone/roles and items.alternate_name. Locked `customers`/`suppliers`
tables untouched (vestigial; a future stage will additively reference `parties`).

**Repositories:** new `PartyRepository`, `FinancialYearRepository`; additive
methods on locked master/user repos (item alternate_name + broadened search,
unit/warehouse/category update + code_exists, company new fields, user search +
`count_active_with_role` + `has_role`).

**Services (RBAC + validation + audit + transactions):** `CompanyService`
(logo copied into app data dir, never an absolute dev path), `FinancialYearService`
(valid range, single active, close/reopen, `is_postable` guard exposed for future
transaction modules — NOT retrofitted into locked Stage 02 posting), `WarehouseService`,
`UnitService`, `CategoryService`, `ItemService` (code/barcode uniqueness, strict
non-negative Decimal prices), `PartyService` (≥1 role, dup code, non-negative
credit), `RoleService` (grouped human-readable permissions, Administrator keeps all),
extended `UserService` (reset password, set_roles, search, **last-administrator
protection**).

**Search providers (reusable, decoupled):** `ItemSearchProvider` (name/alt/code/
barcode) and `PartySearchProvider` (name/company/code/phone, role-filtered)
implement the locked `SearchProvider` Protocol with rich payloads for future
Sales/Purchases — indexed SQL + limited results (§31).

**UI (bilingual EN/Dari, RTL, on the locked shell):** reusable `ManagementPage` +
`FormDialog` framework; screens for Items, Persons, Warehouses, Categories, Units,
Company, Financial Years, Users, Roles & Permissions, wired additively into
`MainWindow` (optional `context` param; nav commands enabled when present). No SQL
in UI; services surface `user_message` errors.

**Verification:** **261 tests** (was 212; +49 Stage 03). On-disk acceptance
workflow (§37): admin→company→FY→warehouses→units/categories→10 items→customer/
supplier/both→item & person search→salesperson RBAC→deactivate→**restart
persistence**→`integrity_check=ok`, `foreign_key_check=0`, schema v3 — all pass.
Self-inspected screenshots (Items EN/Dari, Item form EN/Dari, Persons, Person form
EN/Dari, Warehouses, Company, Financial Years, Users, Roles matrix, Units,
Categories). No Stage 01/02 locked contract changed (only additive extensions;
three Stage 02 migration tests updated to the new latest schema version).

**Known limitations (deferred, intentional):** financial-year posting enforcement
is exposed (`assert_postable`) but not wired into the LOCKED Stage 02 posting
(will be integrated when the production Sales/Purchase modules are built).

### 13I.1 Final Owner Acceptance Test & hardening (2026-08-14)
Full production-readiness gate on a fresh **on-disk** database (not in-memory).
Starting commit `8342f2d`; baseline 261 tests re-verified; no locked core file
modified (diff-audited). Two defects found by adversarial probing and **fixed at
the service layer** (no locked contract changed):

- *NaN / Infinity / 1e999 as a numeric business input raised an uncaught
  `InvalidOperation`* instead of a clean error (would crash the UI). **Fixed** in
  `document_math.parse_money_input`: reject non-finite and absurdly-large
  (`adjusted() > 30`) values as `ValidationError`. Covers items, parties, journals,
  inventory. Severity Medium.
- *`company.default_warehouse_id` accepted a non-existent warehouse* (DB rejected
  it with a raw `IntegrityError`). **Fixed:** `CompanyService.save` validates the
  reference → clean `ValidationError`; no dangling default. Severity Low.

**Two owner-review items completed (were listed as deferred):** the Company screen
now has a **logo picker** (choose/preview/remove; PNG/JPG validated; stored in the
app data dir, not an external path) and the Category form now has a **parent-
category selector** (with self-parent guard).

**Acceptance results (all pass):** migrations 0001→0003 + idempotent + failure
isolation; locked customers/suppliers/sales/purchases/receipts/payments intact;
company profile persistence + multi-update single record; financial year
create/activate/close/reopen + single-active + posting guard; warehouses/units/
categories CRUD + FK protection; 20 items with exact Decimal edge values +
dup-code/barcode + negative/malformed/NaN/Infinity rejection; item search
(code/partial/alt/barcode); unified persons (customer/supplier/both, role
transitions, ≥1-role DB+service guard); party search + role filters; users
(create/roles/reset-password/deactivate) with **last-administrator protection**;
role/permission edit persists + takes effect in a fresh session; **RBAC matrix**
(Administrator/Manager/Salesperson) via direct service calls; audit (no secrets);
rollback leaves no partial state; **restart persistence** of every entity;
**backup/restore with Stage 03 data** (post-backup rows roll back, pre-backup
intact); `integrity_check=ok`, `foreign_key_check=0` throughout. **Tests: 277 pass**
(was 261; +16). Static scan clean; index review confirms equality/code/phone/role/
username/active-FY lookups are index-backed (substring search is a bounded LIMITed
scan, acceptable for the target dataset — no over-engineering).

**Recommendation:** *STAGE 03 IS TECHNICALLY READY FOR OWNER APPROVAL TO LOCK AND
MERGE.* Not locked, not merged — owner decision only.

---

## 13J. Stage 04 — Sales, Purchases & Returns (READY FOR OWNER REVIEW)

Built additively on locked `main` (`184ae4a`, 277 tests) — no Stage 01/02/03
locked contract altered. Delivers the four real production documents that replace
the Stage 01 mock invoice: **Sales, Purchases, Sales Returns, Purchase Returns**,
each an atomic transaction across header + lines + inventory + double-entry ledger
+ party balance + document number + audit (all commit or all roll back).

**A. Database (migration 0004, schema v4, forward/idempotent).** New tables
`sales_returns` / `sales_return_lines` / `purchase_returns` / `purchase_return_lines`
(own `DRAFT/POSTED/CANCELLED` status CHECK, `document_no` UNIQUE, RESTRICT refs to
source doc / party / warehouse, Decimal-text money). Additive nullable party links
`sales.party_id` and `purchases.party_id` → `parties` (RESTRICT), plus
`purchases.supplier_reference`; the locked `customer_id`/`supplier_id` FKs are left
intact. New `SRET`/`PRET` numbering sequences; 4 new permissions
(`sales.return`, `sales.print`, `purchases.return`, `purchases.print`) with role
grants. Never edits a shipped migration.

**B. Engine.** `documents_s4.py` repositories (party link, returns, returned-qty
queries, party-aware list joins, Decimal party balances derived from the LOCKED
ledger where `party_type IN ('CUSTOMER','SUPPLIER')`). `SalesDocumentService` /
`PurchaseDocumentService` compose the LOCKED Stage 02 repositories and add: **FY
enforcement at the service layer** (`assert_postable` before every post — the
Stage 03 deferred item, now wired), the unified `parties` model (writes
`customer_id/supplier_id = NULL` + sets `party_id`), stock checks, no-overpayment,
proportional return discounts, over-return + return-more-than-on-hand guards, and
the reversing ledger entries. Money/quantities are Decimal end to end.

**C. UI (real, service-backed, on the locked shell).** One keyboard-first
`DocumentEntryPage` (sale/purchase) — party + item autocomplete via the locked
`SearchSelector` + Stage 03 providers, live Decimal totals, payment, Save / Save &
Print; `DocumentListPage` (sales/purchases/returns) with search, status filter and
per-row Print/Return; `ReturnEntryPage` (from-original, editable return qty). Wired
into the **Buy & Sell** top-nav category; the Stage 01 mock invoice is no longer in
the production navigation. The Home **dashboard is now live** — real Today's Sales/
Purchases, real Recent Sales, real Low-Stock (reorder level), truthful `—` for
KPIs without a computed source (no mock data on a production screen).

**D. Printing.** `print_builder.py` converts each persisted document into the
LOCKED print `InvoiceData` (screen == print; float only at the display boundary).
The locked A4/A5 reflow engine and preview were extended **additively** with an
optional `title_key` (default preserves Stage 01 "SALES INVOICE"), so the same
engine composes Purchase Invoices and Return notes in English + Dari.

**E. Verification.** **311 tests** (was 277; +34: 20 engine + 14 UI). On-disk
acceptance workflow (22 checks): admin→company→FY→warehouses→items(+reorder)→
customer/supplier→purchase(stock in)→cash/credit/partial sales→sales & purchase
returns→over-return rejected→**global ledger balanced (Dr==Cr)**→`check_health`
ok→**backup + restore** (restored DB carries the sales). Self-inspected screenshots
(dashboard, sales entry, sales list, purchase entry, purchase list, sales return,
purchase return, print preview — EN + Dari) and A4/A5 EN/Dari prints for all four
document types; fixed a list cell-widget redraw defect and null party-field print
rendering during self-inspection. No locked contract changed (only additive
extensions; the Stage 04 migration test asserts schema v4).

**Known limitations (deferred, intentional):** documents post directly to
`POSTED` (no separate DRAFT editing screen yet); the locked print engine's
"Bill To"/"Salesperson" labels are reused as-is for purchases (title is
overridden, side labels are not); receipts/payments settlement of remaining
balances is a later module.

### 13J.1 UI/UX consistency + final polish (2026-08-16)
Two owner-directed refinement passes aligned the Stage 04 screens with the locked
Stage 01–03 design system (no business logic, calculations, posting, schema,
migrations, RBAC, or locked contracts touched):
- Adopted the shared `LabeledField`/compact metadata, cards, buttons, tables and
  totals tokens; wired the real application stylesheet in review captures.
- Fixed a **responsiveness defect** — at 1366×768 the invoice line grid could
  collapse to zero visible rows; the grid now has a minimum-height floor and the
  totals/payment area is a single compact strip, so the grid shows several rows
  at 1366×768 and grows at 1600×900 / 1920×1080.
- Compacted the Return source area (removed a title duplicating the field label).
- Verified EN + Dari RTL (numbers/dates/document numbers/currency read correctly
  in RTL tables/fields), many-record list scrolling, autocomplete edge cases,
  and Print Preview (A4/A5, EN/Dari, zoom/fit/print).
- Accepted known limitation: RTL phone-number bidi reordering inside the LOCKED
  Stage 01 `SearchSelector` dropdown (cosmetic; persistent data unaffected).

**LOCK RECORD:** *Stage 04 is owner-approved and **LOCKED** (2026-08-16).* Its
public contracts (§8, §13J) are frozen. **313 tests pass.** Stages 01–04 are all
locked baselines; future stages must preserve backward compatibility and must not
modify Stage 04 code/UI/logic/DB contracts/tests without explicit owner
authorization. Not merged by the assistant (owner controls merge). Stage 05 NOT
STARTED.

---

## 13K. Stage 05 — Receipts, Payments & Expenses (READY FOR OWNER REVIEW)

The real money-movement / settlement layer, built additively on locked Stage 04.
No Stage 01–04 locked contract altered; no shipped migration edited; no business
logic changed in the locked stages.

**A. Database (migration 0005, schema v5, forward/idempotent).** Reuses the money
tables Stage 02 already created. Adds: ``accounts.is_fund`` (marks cash/bank/fund
accounts — the minimum foundation for choosing where money moves, no treasury
module); additive ``party_id`` + ``payment_method`` + posting stamps on
``receipts``/``payments`` (unified Stage 03 ``parties`` model, locked
``customer_id``/``supplier_id`` untouched); ``payment_method``/``notes``/stamps on
``expenses``; ``expense_categories.account_id`` (each category maps to a real
expense account — categories stay master data, never hard-coded in the UI). Seeds
funds (Cash, Bank, Petty Cash), a standard set of expense accounts + categories,
RCP/PAY/EXP sequences, indexes, and 10 permissions with role grants.

**B. Engine.** ``money_s5.py`` repositories (party/method writes, party-aware list
joins, fund + expense-category reads, ledger-derived fund balances). ``ReceiptService``
/ ``PaymentService`` / ``ExpenseService`` post ONE atomic transaction each —
header + Stage 05 metadata + **balanced double-entry ledger** + party-balance effect
+ document number + audit — reusing the LOCKED ``FinancialRepository`` +
``assert_journal_balanced`` and Stage 04 ``PartyBalanceRepository``. Ledger: Receipt
Dr fund / Cr AR(customer); Payment Dr AP(supplier) / Cr fund; Expense Dr expense
account / Cr fund. Financial-year enforcement, RBAC and Decimal-safe strict input
validation (rejects zero/negative/malformed/NaN/Infinity/oversized amounts and
non-positive rates) run before any write. Balances are **derived, never editable**:
a receipt/payment moves the party's ledger balance and the balance re-derives.

**C. Accounting / balances (owner example verified).** Customer owes 13,440 → receives
5,000 → remaining 8,440. Supplier payable and expense cash movement verified; every
journal balances (Dr==Cr); cash/bank fund balances derive from the ledger.

**D. UI.** One reusable keyboard-first ``MoneyEntryPage`` (receipt/payment/expense)
and ``MoneyListPage`` (three history lists) on the LOCKED Stage 01–04 design system
— same cards, LabeledField metadata, SearchSelector autocomplete, strong amount
pill, tables, buttons, status pills and RTL. Wired into the **Receipts & Payments**
top-nav. Compact: the short forms group at the top and fit 1366×768; the lists use
the Stage 03/04 management-list pattern.

**E. Printed vouchers.** ``VoucherPrintDocument`` composes real business vouchers
(Receipt / Payment / Expense) reusing the LOCKED print design language (palette,
typography, company identity, accent party bar, amount-in-words EN+Dari, strong
amount panel, signature blocks) at A4 and A5, EN and Dari RTL. The Stage 01
print-preview workspace is reused unchanged via a subclass.

**F. RBAC + audit.** 10 service-enforced permissions (receipts/payments/expenses
``.view/.create/.print`` + ``funds.view``) with role grants; every create/post is
audited (actor, timestamp, entity, action; no secrets). Failed posts roll back
leaving no partial document / balance / journal / audit record.

**G. Verification.** **350 tests pass** (313 baseline + 29 engine/failure-safety +
8 UI). 17-step on-disk acceptance (admin → funds → credit sale → partial receipt →
payable → partial payment → expense → **ledger balanced** → ``integrity_check=ok``
/ ``foreign_key_check`` clean → restart persistence → **backup + mutate + restore**
rolls back to backup state). Self-inspected EN + Dari screenshots at 1366×768 and
1920×1080 and A4/A5 vouchers; fixed two self-found defects (a mid-form empty gap
on the short entry screens; a missing voucher amount-label i18n key + voucher
signature anchoring).

**Known limitations (deferred, intentional).** Documents post directly to POSTED
(no separate DRAFT/void UI). Multi-currency: original amount + rate are preserved
and the base equivalent is derivable, but the GL is posted in document currency
(consistent with the LOCKED Stage 04 ledger) — cross-currency GL consolidation is a
later reporting concern. Seeded fund/expense-account names are English master data
(a user renames them, as with warehouses/units).

**LOCK RECORD:** *Stage 05 is owner-approved and **LOCKED** (2026-09-04.)* Its
frozen public contracts are in §8. The locked state is Stage 05 **as it stands
today**, including the changes the owner requested during the Stage 06
verification rounds — in-place `correct_sale`, the derived `net_view`, and the
explicit Cash/Credit selector — which supersede the corresponding descriptions in
§13M and §13O below. Those sections are kept as the historical record of how the
stage was built, not as the current contract.

### 13K.2 §33 amendment 01 — party ledger totals could not be reconciled

**Status: owner-approved (2026-09-06). Applied. The only change to locked Stage
05 behaviour since the lock.** Raised during Stage 07, presented under the §33
STOP procedure, and approved with the instruction *"Keep the confirmed
customer_totals fix. Do NOT revert it."*

**(1) The change.** `PartyLedgerRepository.customer_totals` and
`supplier_totals` now derive their three figures so that

```
total_sales     − total_received == receivable      (customer)
total_purchases − total_paid     == payable         (supplier)
```

holds for every party in every state. Two corrections make that true:
documents are counted **net of posted returns**, and "received"/"paid" counts
the money settled **on the document itself** in addition to the separate
Receipt/Payment documents.

**(2) Why it was necessary.** The summary was not merely imprecise — its three
numbers contradicted each other, so a reader could not trust any of them.
Reproduced on a real database before anything was edited: a supplier with a
1,000 bill, a 400 return and a 200 payment reported **Purchases 1,000 − Paid
200** against a **Payable of 400**. The balance was right; the two figures
printed beside it were wrong. Sales/purchase returns and part-paid documents
both existed in locked stages, so this was reachable in normal use — a
confirmed bug, not a new Stage 07 requirement.

**(3) Affected components.** `repositories/ledger_s6.py` only. It changes what
the **Customer Ledger** summary (Stage 05) and the **Supplier Ledger** summary
display, and it is the source the new Suppliers screen reads. The **running
balance, the ledger lines, the receivable/payable, every posting and every
stored value are untouched** — only the two summary figures beside the balance
are now derived correctly.

**(4) Migration / compatibility risk: none.** No schema change, no data
migration, no stored value rewritten, no public method renamed or removed. The
return type and dict keys are unchanged; the arithmetic behind two of the three
values is corrected. A database written before this change reads correctly
after it, because nothing was ever persisted from these figures.

**(5) Alternatives considered.** *(a) Leave it and note it* — rejected: the
owner reads these numbers to decide what a customer owes. *(b) Fix the supplier
side only, since Stage 07 is the purchases stage* — rejected: it is one shared
defect in one repository; fixing half of it would leave the customer screen
wrong and the two sides inconsistent with each other. *(c) Change the balance to
match the totals instead* — rejected: the balance is derived from the ledger and
is the figure that was already correct.

**Regression cover.** `tests/test_locked_stage05_ledger_totals.py` asserts the
identity itself — not example numbers — across an ordinary account, a partial
payment, a partial return, a full return, a mixed history and a dual-role party,
for **both** the customer and the supplier ledger, plus the party-ledger service
and the Suppliers screen reading the same figures.

### 13K.1 Confirmed future requirement — Opening Stock (Inventory stage)

Recorded per owner direction; **not implemented in Stage 05**. The future Inventory
stage must distinguish **Opening Stock / موجودی اول دوره** (opening quantity + opening
inventory value, per item, per warehouse, historically preserved) from **Current
Stock / موجودی فعلی** (opening + subsequent movements → current quantity + value).
Inventory reporting must show Opening Quantity, Opening Value, Current Quantity,
Current Value, Quantity Difference and Value Difference. **Opening Stock must NOT be
implemented as a fake Purchase Invoice.** The inventory ledger already reserves an
``OPENING`` movement type for this. Stage 05 does not contradict this requirement.

---

## 13L. Owner manual-test hardening pass (READY FOR OWNER REVIEW)

Six owner-reported defects from the manual Windows test, all fixed **additively**
(no LOCKED public contract — service API or DB schema — broken; the pass does edit
locked Stage 01/04 UI/print files with explicit owner authorization, keeping every
prior test green).

- **Migration 0006 (schema v6, forward/idempotent).** Adds nullable
  ``sales.walkin_name/walkin_phone/walkin_address`` snapshot columns and the new
  ``parties.ledger`` permission; extends the pre-existing ``sales.void`` /
  ``purchases.void`` grants to Manager/Accountant. `PRAGMA integrity_check` = ok,
  `foreign_key_check` = 0.
- **#1 Sales Invoice refined** (`ui/documents/entry_page.py`): explicit
  Customer → invoice-info → item search → lines → payment → totals → Save/Print
  reading order; Registered/Walk-in toggle; same locked design language.
- **#2 Walk-in / general customer**: `SalesDocumentService.post_sale` gains optional
  ``walkin_name/phone/address`` snapshotted onto the sale (printed on the invoice
  via `print_builder`), with NO permanent `parties` row; a walk-in sale must be
  paid in full — **walk-in credit is rejected** so no anonymous receivable is ever
  created. Registered vs walk-in stay distinguishable (`party_id` vs snapshot).
- **#3 Line editing + posted correction**: in-grid Qty/Price/Discount inline edit,
  double-click-item replace, delete — all pre-post (no stock movement until Save);
  **`void_sale`** safely reverses a posted sale (stock via ADJUSTMENT_IN + reversing
  JV + customer balance + VOID stamp + audit), keeping the original document, with a
  guard blocking void when returns exist. Returns (Stage 04) remain the partial
  correction path.
- **#4 Customer/Supplier ledger**: new `repositories/ledger_s6.PartyLedgerRepository`
  + `services/party_ledger.PartyLedgerService` + `ui/documents/party_ledger_page.PartyLedgerPage`
  under Account Reports — running balance + Total Sales/Received/Receivable (or
  Purchases/Paid/Payable), all DERIVED from the authoritative ledger; a party that is
  both customer and supplier is one identity with two ledger views.
- **#5 Responsive**: reusable `components.vscroll` scroll-body + pinned action bar on
  the Stage 05 money entry pages so Save/Print/Close never leave the viewport;
  widened list actions column so Print+Return+Void don't clip.
- **#6 Company logo on prints**: `CompanyInfo.logo_path` rendered by the invoice and
  voucher print headers (`_logo_widget`) with aspect-ratio preserved and a graceful
  letter-mark fallback; persists across restart; EN + Dari verified.

**Testing:** full suite **368 pass** (+18 in `tests/test_owner_fixes.py`); 20-step
real on-disk acceptance (walk-in, void reversal, customer/supplier ledgers, restart,
re-open + print, ledger balanced, integrity/fk clean). Self-inspected EN/Dari
screenshots; 2 self-found UI defects fixed before delivery.

**Recommendation:** *STILL READY FOR OWNER REVIEW.* Not locked, not merged, Stage 06
not started — awaiting owner manual acceptance of the corrected Windows build.

---

## 13N. Full UI/UX modernization — Stages 01–05 (READY FOR OWNER REVIEW)

A **presentation-layer-only** modernization across every Stage 01–05 screen,
applied in 7 controlled passes. **No database, migration, repository, service,
accounting, inventory, posting, correction, auth, RBAC, audit, licensing or
document-numbering behaviour was changed.** Schema stays **v7**. Full suite
**391 passing** (377 baseline + 14 new UI tests). The single authorized
functional addition is **New Item Opening Stock**, which introduces no new
inventory behaviour — it orchestrates the *existing* `inventory.record_opening`
service (one `OPENING` movement) after `items.create`.

- **Pass 1 — shared foundation.** `FormDialog` recomposed into fixed header +
  scrollable body + pinned Save/Cancel footer, clamped to `availableGeometry`
  (so Save/Cancel can never leave the screen at 1366×768). New reusable
  `RowActions` (inline buttons + `⋯` overflow menu). `ManagementPage` adopts it,
  with a header `minimumSectionSize` floor. QSS for dialog header/footer + kebab.
- **Pass 2 — login/shell/dashboard.** Login redesigned into a two-panel
  composition: left **Zenith Soft** developer brand panel (company, kind,
  Phone/Email/Address — phone & email forced LTR in RTL) and right product
  login/setup form with a Version + Licence footer. Real Dari RTL mirroring. No
  Zenith Soft logo asset exists → a typographic monogram is used (no invented
  logo). Fixed a latent Qt quirk where bare `background:transparent` widget
  stylesheets stripped child control fills (blanked the Sign In button / dialog
  inputs) — moved to app-level ID-scoped rules.
- **Pass 3 — documents.** Sales/Purchase Invoice already delivered the approved
  reference layout (dominant items table, walk-in panel, strong Grand Total,
  pinned actions) and inherits the design system; verified EN/Dari at 1366×768.
  The **walk-in "paid in full" treatment reflects existing logic**
  (`sales_documents.py` credit guard), not a new UI rule. Document lists moved
  to Print-inline + `⋯` (Return/Correct/Void) — no more 4-button crowding.
- **Pass 4 — master data.** New Item gains an **Opening Stock** section
  (Opening Quantity + Opening Warehouse, create-only, stockable-only) → existing
  `inventory.record_opening`. All master dialogs inherit the scroll+pinned
  footer.
- **Pass 5 — money/ledger.** Receipts/Payments/Expenses lists adopt `RowActions`
  (View Account + Print inline). Ledgers/entry pages already on the system;
  balances consumed from the authoritative party-ledger service.
- **Pass 6 — users/account.** Change Password (Tools → My Account) confirmed
  against the existing `change_own_password` (verifies current password, existing
  hashing/policy, audited, RBAC-safe). Roles permission dialog de-duplicated to
  use the native dialog scroll.
- **Pass 7 — regression.** Responsive tests at **1366×768 / 1600×900 /
  1920×1080** assert no action button falls off-screen (Sales Invoice with 12
  lines, Receipt entry, tall FormDialog). Printed customer documents use the
  **customer's** company identity + logo (`company.logo_path`), never Zenith
  Soft's dev contact (§18 preserved).

New UI tests: `test_ui_foundation.py`, `test_item_opening_stock_ui.py`,
`test_responsive_layout.py`. Stage 05 remains **READY FOR OWNER REVIEW — not
locked, not merged**; Stage 06 not started.

---

## 13M. Owner review round 2 (READY FOR OWNER REVIEW)

Owner-review-2 defects, fixed **additively** (no LOCKED public contract broken;
the pass edits locked Stage 01/03/04 UI files with explicit owner authorization).
Migration **0007 (schema v7)** adds `sales.corrected_from_id` and the `sales.correct`
permission; `PRAGMA integrity_check` = ok, `foreign_key_check` = 0.

- **Sales Invoice restructure (§1-§8)** — `ui/documents/entry_page.py`: compact
  customer+invoice header (customer-type toggle inline), a **dominant Expanding
  items table** (grid card set to Expanding + table Expanding with a 150px floor →
  ~5 rows at 1024×768/1366×768, ~15 at 1080p, internal scroll beyond), a single
  entry strip carrying **Unit** + **Add / Edit Line / Delete Line**, and a two-row
  totals strip with **Previous + Updated customer balance**. Walk-in is a clearly
  labelled bordered panel.
- **Complete line editing before posting (§6/§7)** — inline Qty/Price/Discount edit,
  a per-line Unit selector, item replacement via Edit Line, and Delete; no inventory
  movement until posting.
- **Safe posted-invoice correction (§9)** — `SalesDocumentService.correct_sale`:
  atomic **void-of-original + linked replacement** (`corrected_from_id`), audited
  `sales.correct`, all-or-nothing; **blocked when a dependent sales return exists**
  (directs to Return/Void). Refactored `post_sale`/`void_sale` into shared
  `_prepare_sale` / `_do_post_sale` / `_do_void_sale` so correction reuses one source
  of truth. Wired as a **Correct** action on the Sales list opening the invoice in
  the entry form.
- **Contextual account history (§10/§11)** — `PartyLedgerPage.show_party`;
  `ManagementPage.on_view` adds a **View Account** row action on the Customers list;
  `MoneyListPage.set_view_account_handler` adds it on the Receipts/Payments lists.
  Ledger figures stay derived from the authoritative ledger.
- **Account Settings (§12)** — `UserService.change_own_password` /
  `change_own_username`: current-password verified, password-policy enforced, hashed
  (never plaintext), id-preserving (all relationships intact), duplicate-username
  guarded, audited; new `AccountSettingsPage` under Tools → My Account.
- **Responsive (§13/§14)** — Save/Print/Close reachable at 1024×768/1280×720/
  1366×768/1080p; dominant table on normal+large screens; list stretch column keeps
  a legible minimum. (1280×720, the shortest listed resolution, shows ~3-4 table rows
  with internal scroll — an honest height constraint, all controls reachable.)
- **Logo/print (§16)** — unchanged and re-verified (invoice + vouchers, EN/Dari,
  aspect-preserved, graceful fallback).

**Testing:** full suite **377 pass** (+9 `tests/test_round2.py`). 13-step round-2
on-disk acceptance (correction reconciles stock+ledger+balance, dependency block,
password/username change, restart persistence, integrity/fk clean). Self-inspected
EN/Dari screenshots incl. 1024×768; the items-table compression found on first
inspection was fixed (Expanding grid card + tightened chrome).

**Recommendation:** *STILL READY FOR OWNER REVIEW.* Not locked, not merged, Stage 06
not started — awaiting owner manual acceptance of the next Windows build.

---

## 13O. Stage 05 final — Sales Reporting + Return-lookup fix + correction audit (READY FOR OWNER REVIEW)

Additive; **no** accounting, inventory, ledger, numbering, auth, RBAC or licensing
logic changed, **no** migration added (schema stays **v7**). Reads only the
authoritative `sales` / `sales_returns` tables.

- **P1 — Sales Return lookup.** The return page (`ui/documents/return_page.py`)
  rejected a typed invoice number unless it *exactly* equalled the stored
  `document_no`, so a partial entry (`2`, `000002`) failed with "not found". It now
  accepts a **unique partial match**, **flags an ambiguous fragment**
  (`s4.msg_source_ambiguous`), and still rejects a genuinely nonexistent number.
  Partial-return, over-return and stock/ledger reversal already reconciled and are
  re-covered by tests.
- **P2/P3 — Correction is not a duplicate; audit enriched.** Confirmed the LOCKED
  void-and-replace `correct_sale` does **not** create a second normal invoice or
  double-count — the VOID original is excluded from every total and the replacement
  counts exactly once. The `sales.correct` audit note now records a **human-readable
  line diff** ("Rice qty 5 → 3; Sugar 2 removed; Oil 4 added") alongside the old→new
  totals and the reason. (In-place mutation was deliberately **not** adopted: it
  would destroy the auditability the owner asked to preserve.)
- **P6 — Sales Reporting system (new).** `repositories/reports.py`
  (`SalesReportRepository`) + `services/sales_reports.py` (`SalesReportService`)
  compute **Gross / Paid / Credit / Returns / Net** for any period —
  Today / This Week / This Month / This Year / **Custom From–To** — plus **daily,
  monthly and yearly** breakdowns and per-invoice transaction detail. Correct by
  construction: **partial payments split** into paid vs credit (never whole); **later
  receipts** (debt collection) are **not** counted as sales; **corrected invoices count
  once** (VOID excluded); **Gross and Returns stay distinguishable**, Net = Gross −
  Returns. Filters: date range, warehouse, customer, payment status,
  registered/walk-in. Money summed with `Decimal`.
- **P6 UI + print.** `ui/documents/sales_report_page.py` — period presets, custom
  range, all filters, five colour-coded summary tiles, and
  Transactions / Daily / Monthly views; wired into **Account Reports**, English +
  Dari RTL. `ui/print/sales_report_document.py` + `sales_report_preview.py` — a
  printable report on the existing preview standard, using the **CUSTOMER's**
  business identity (logo / name / address / phone) from Company settings — never the
  Zenith Soft developer identity. **A4 only** (owner decision, 2026-08-21): a
  nine-column report is unreadable squeezed onto A5, so the report preview exposes
  **A4 exclusively** (English + Dari) — the whole table fits the A4 printable area
  with all nine columns (Date, Invoice #, Customer, Type, Gross, Paid, Credit,
  Returned, Net), the five summary cards and the totals row, and no document-level
  horizontal scrolling. A5 is **not** removed globally — invoices, receipts and
  vouchers still offer A4/A5.

**Verification.** Full suite **431 pass** (+34: engine reconciliation, partial-paid
split, later-receipt-excluded, corrected-not-double-counted, returns math, date
boundaries, presets, all filters, correction audit; UI: return lookup
exact/partial/nonexistent/ambiguous, report tiles, view switch, walk-in filter,
print payload uses customer identity, Dari). A real on-disk end-to-end scenario
(opening stock → cash / credit / partial / walk-in sales → correction → receipt →
partial return) reconciles **by hand**: Gross 3000, Paid 2000, Credit 1000, Returns
300, Net 2700; stock Rice 481 / Sugar 490; ledger balanced (Dr = Cr). Self-inspected
EN + Dari screenshots of the report screen (detail/daily/monthly), the A4 EN and A5
Dari customer-identity print, and the return lookup loaded by a partial number.

**Recommendation:** *STILL READY FOR OWNER REVIEW.* Not locked, not merged, Stage 06
not started.

---

## 14A. Stage 06 — Inventory & Stock Management (🔒 LOCKED)

Stock was already a signed movement ledger, and Stage 06 keeps it that way: every
figure the app shows — the Inventory screen, the product list, the reports, and the
stock a sale is validated against — is the `Decimal` sum of `inventory_movements`.
Nothing stores a stock number, so no two screens can disagree.

**Migration 0008 (schema v8, forward/idempotent)** — one column and three indexes:
`inventory_movements.notes` (the reason an adjustment was made, what a transfer was
for). Previously a reason reached only the audit log, so the history the operator
reads could not show it. No new permission: `inventory.view/adjust/transfer` already
existed and were granted.

**Engine.** New `InventoryReadRepository` + Stage 06 service reads:
`movement_history` (date, item, warehouse, type, in/out, **source document number**
resolved by joining sales/purchases/returns, user, note), `stock_overview`
(opening / current / unit / warehouses / minimum / low flag),
`stock_by_warehouse`, `low_stock`. `adjust` now **requires a reason**, stores it on
the movement, and refuses to remove more than a warehouse holds. `transfer` and
`record_opening` carry notes. New `InventoryReportService` builds the five reports
— Current Stock, Opening vs Current, Stock by Warehouse, Item Movement (stock card
with a running balance), Low Stock.

**Integration fix to locked Stage 05 (the one exception, required for the mandatory
workflow).** `correct_sale` deleted and re-inserted lines, so
`sales_return_lines.sale_line_id` (ON DELETE RESTRICT) forced a blanket block on
correcting any invoice that had a return — the owner's flow (sale 10 → return 2 →
correct to 5) was impossible. Correction now **updates surviving lines in place**,
keeping their ids so the return stays valid, and refuses only what is genuinely
contradictory: removing an item that has returns, or correcting a quantity below
what already came back.

**UI.** Inventory (code / name / unit / opening / current / minimum / warehouse /
low-stock status, with search and a low-stock filter), Stock Adjustment (in/out,
mandatory reason), Warehouse Transfer (over-transfer blocked, shows available),
Stock Movement history (item / warehouse / type filters), and Inventory Reports
with **A4-only** print using the CUSTOMER's business identity. All under Item
Reports, EN + Dari RTL. The product list gained Unit, Opening Stock, Current Stock,
Warehouse and Stock Status columns.

**Verification.** Full suite **495 pass** (+28 in `tests/test_stage06_inventory.py`).
The owner's mandatory workflow was run on a real on-disk database through the real
screens and reconciled on every surface:

| Step | Expected | Actual |
|------|----------|--------|
| Opening 100 (entered in the real product form) | 100 | 100 ✓ |
| Purchase +20 | 120 | 120 ✓ |
| Sale 10 | 110 | 110 ✓ |
| Sales Return 2 | 112 | 112 ✓ |
| Correct sale 10 → 5 (2 already returned) | 117 | 117 ✓ |
| Adjustment +3 | 120 | 120 ✓ |
| Transfer 10 Main → Warehouse 2 | 110 / 10, total 120 | 110 / 10 / 120 ✓ |

The same figures agree in the Product List, Inventory, Stock Movement (9 movements
summing to 120), Sales (one invoice, original number, corrected line 5), Sales
Return (history preserved, 3 still returnable) and all five reports; the ledger
stays balanced. Two self-found UI defects were fixed during screenshot review (a
clipped Low-Stock chip; printed report headers rendering in the wrong language).

**LOCK RECORD:** *Stage 06 is owner-approved and **LOCKED** (2026-09-04)* after
manual acceptance testing plus three owner verification rounds (§14A.1–§14A.3).
Accepted commit `a4017ec`, **538 tests pass**, schema **v8**. Its frozen public
contracts are in §8. **PR #4 is not merged yet** (owner's instruction). Stage 07
not started. Stage 06 behaviour must not change from here except to fix a
confirmed bug, via the §33 STOP procedure.

### 14A.1 Owner verification round — a return must update the original sale visibly

The owner asked for proof of one requirement before manual testing: returning an
item has to change what the **original invoice** shows, everywhere it is shown.
Verified on a real on-disk database with the owner's own example (Rice 5 × 100 =
500, return 1). The sale document is deliberately **never rewritten** — the sold
quantity and the invoiced total remain the historical record — and the current
position is derived from the return documents by `SalesDocumentService.net_view`,
so there is exactly one answer to "what is this invoice worth now".

| Surface | Before the return | After returning Rice 1 |
|---------|-------------------|------------------------|
| Stock on hand | 5 | **6** |
| Sales invoices in the list | 1 (`SALE-000001`) | **1 (`SALE-000001`, POSTED)** |
| Sales List — Invoiced / Returned / Net | 500 / 0 / 500 | 500 / **100** / **400** |
| Sales List — Remaining owed | 500 | **400** |
| Invoice line — sold / returned / net | 5 / 0 / 5 | 5 / **1** / **4** (400) |
| Printed invoice | Rice 5 → 500 | **Rice 4 → 400** |
| Sales Report — Gross / Returns / Net | 500 / 0 / 500 | 500 / **100** / **400** |
| Customer receivable | 500 | **400** |
| Stock movements | OPENING, SALE −5 | + **SALE_RETURN +1** (no second SALE) |

Three gaps that verification exposed, and the fixes:

1. **The Sales List "Remaining" column still showed the invoiced remaining (500)
   after a return**, disagreeing with the customer's ledger (400). `list()` now
   also derives `net_remaining` = net total − paid and the column shows it. On a
   *paid* invoice this correctly goes negative (a refund owed back), matching the
   receivable exactly.
2. **The human-readable note was stored but visible nowhere.** The Sales Return
   list gained a **Note** column (the note is the widest field, so it takes the
   stretch column), showing "Rice — Qty 1 returned." beside the source invoice.
3. **The Dari note used the item's English name.** It now uses the item's second
   (Dari) name when one exists — "برنج به تعداد 1 دانه برگشت شد." The note is
   stored in the language the operator posted it in, as written at the time.

This behaviour previously had **no regression tests at all**; it now has 16 in
`tests/test_return_reflects_on_invoice.py`. Full suite **511 pass**.

The Windows test build was also renamed from Stage 05 to Stage 06: the workflow
takes the stage from a single `env.STAGE`, publishing tag `stage06-test-build`
and `ZenithBusiness-Stage06-TestBuild-win64.zip`, and retiring the old
`stage05-test-build` release so only one download link exists.

### 14A.2 Owner verification round 2 — the FULL return

Second verification pass: sell Rice 5 × 100 = 500 and return **all five**, posted
through the real Return screen in **both languages** (one invoice returned from
the English screen, one from the Dari screen, on the same database).

| Check | Result |
|-------|--------|
| Warehouse stock back up by +5 per invoice | 0 → **10** in Main Store |
| Sales List Returned = the full invoice | **500.00** on both rows |
| Sales List Net Total | **0.00** |
| Sales List Remaining / customer debt | **0.00** / receivable **0.00** |
| Second SALE invoice created | **none** — 2 sales sold, 2 sales listed |
| Return note visible in the Returns list | EN "Rice — Qty 5 returned." · Dari "برنج به تعداد 5 دانه برگشت شد." |
| Sales Report Gross / Returns / Net | 1000 / 1000 / **0** |
| Nothing further returnable | returnable **0**, a further return is refused |
| Ledger | balanced |

**Defect found by this test — a fully-returned invoice printed as a blank form.**
When every line comes back, the netted item table is legitimately empty, so the
A4 sheet showed an empty table and 0.00 totals with nothing explaining why. The
printed document now carries an optional document-level note
(`InvoiceData.note_key`, additive with an empty default) rendered above the
standard terms: "All items on this invoice were returned. Nothing remains
payable." / "تمام اقلام این بل برگشت داده شده است. مبلغی قابل پرداخت باقی نمانده."
It is stored as an i18n **key**, not text, so it follows the preview's EN/Dari
toggle like every other word on the sheet — the same mistake that produced
wrong-language inventory report headers earlier in Stage 06. Partially-returned
and untouched invoices carry no note: their own lines already tell the story.

The Dari return note was also re-verified end to end in the running UI (not only
in a unit test): posted from the Dari screen it names the item by its Dari name
and appears in the Returns list in Dari, beside the English note on the other
invoice.

12 further regression tests (28 in `tests/test_return_reflects_on_invoice.py`).
Full suite **523 pass**.

Two observations recorded, deliberately NOT changed in this round: the Stock
Movement history's Reason/Note column is blank for sales returns (the note lives
on the return document; carrying it onto the movement would mean touching Stage
05 sale posting), and item names render in their primary name on the Dari
screens (a general second-name question across every screen, not a return bug).

### 14A.3 Owner verification round 3 — reopening a sale must show its current state

The Sales List, the printed copy and the reports all showed the net result after
a return, but **reopening the saved sale still listed the returned item as an
active payable line at the original Grand Total**. The invoice screen was the one
surface still reading the raw stored lines.

The reopened invoice now shows the invoice's CURRENT position, from the same
`net_view` every other surface reads:

* a partly returned line loads at its **net quantity** (sold 4, returned 1 → 3);
* a fully returned line is **not an active line at all**;
* **Grand Total is the net total** — the owner's example (Rice 1980 + Sugar 1750
  = 3730, Rice returned in full) reopens as Sugar alone at **1750**;
* the returned goods appear read-only under **Returned Items / اقلام برگشتی**
  with item, quantity, amount and the return document number, so nothing is
  hidden — the panel is absent entirely on an invoice with no returns.

**History is never rewritten to make the screen look right.** The returned
quantities are remembered while the form is open and folded back in when a
correction is saved, so the stored sale keeps its original quantities and the
return document keeps pointing at a line that exists. Correcting Sugar 1 → 2 on
that invoice saves Sugar 2 **and** Rice 1: stored gross 5480, net 3500,
receivable 3500, the return still valid, one invoice with its original number.

Two related inconsistencies fixed in the same screen:

* **Previous Balance** double-counted the invoice being corrected — it showed the
  customer's whole receivable, which already contains this invoice, and then
  added the invoice's remaining on top. It is now the balance **before** this
  invoice (`balance_before_sale`), so Updated Balance equals the customer's
  actual receivable. It is never used to absorb returned goods. The header chip,
  which shows the account balance itself, is relabelled **Customer Balance /
  بیلانس مشتری** so one screen does not use "Previous Balance" for two figures.
* **Amount Paid** was re-derived from the reduced total on reopen, which would
  have claimed back cash the customer still holds. A reopened invoice now shows
  what was actually paid; Remaining goes negative when a paid invoice is returned
  against (a refund owed), exactly matching the Sales List and the receivable.
  Choosing a payment type deliberately still re-derives it.

Also corrected: the save message said "Corrected — new invoice {no}" although a
correction creates no new document. It now reads "Invoice {no} corrected".

Verified on a real on-disk database in **English and Dari**; 15 regression tests
in `tests/test_invoice_view_after_return.py`. Full suite **538 pass**. No
migration, and no change to inventory posting, returns, accounting or numbering.

---

## 14B. Stage 07 — Purchases Parity / Purchase & Supplier Management (IMPLEMENTED — READY FOR OWNER REVIEW)

Agreed scope, 2026-09-04. **Accounting Reports and Costing/valuation are explicitly
out of scope.** §14B.0–§14B.7 are the plan as agreed; §14B.8 records what was
built. Stage 07 is **not locked** — it awaits the owner's manual approval.

### 14B.0 What is already there (inspected, not assumed)

Verified by reading the code and by running a probe against a real on-disk
database — the findings below are reproduced facts, not expectations.

**Already working and NOT to be rebuilt:** `post_purchase` (atomic header + lines +
`PURCHASE` movements + balanced journal + numbering + audit, FY-enforced);
`post_return` (over-return guard, a real stock-availability guard, `PURCHASE_RETURN`
movements, Dr A/P — Cr Inventory); `find_by_reference` (PUR-000002 / 000002 / 2 all
resolve); `returnable_quantities`; the supplier side of `PartyBalanceRepository`
(`payable`), `PaymentService`, `PartyLedgerPage` (supplier ledger with running
balance and totals) and `supplier_search`; the Persons master screen with a
supplier role; purchase entry/list/return screens and A4/A5 purchase printing;
`supplier_reference` on the header; the Note column on the returns list.

**Confirmed gaps (each reproduced):**

| # | Finding | Evidence |
|---|---------|----------|
| P1 | A **credit purchase from an unregistered supplier is accepted** and posts an **anonymous payable** (`party_type='SUPPLIER', party_id=NULL`). No supplier ledger can ever show it. Sales rejects the mirror case (walk-in credit) outright. | Probe: PUR-000001, remaining 500.00, A/P line with `party_id=None`. |
| P2 | **Purchase List disagrees with the supplier balance after a return.** The list shows `grand_total` 1000.00 / remaining 1000.00 while the payable is correctly 600.00. There are no Returned / Net / net-remaining columns. | Probe step 3. |
| P3 | **The printed purchase invoice ignores returns** — still prints Rice 10 → 1000.00 after 4 were returned. | Probe: `build_purchase_invoice` uses raw `lines_for`. |
| P4 | **Reopening a purchase is impossible** — there is no purchase equivalent of `load_for_correction`, and no `correct_purchase`. A wrong purchase can only be voided… except there is no `void_purchase` either. | `PurchaseDocumentService` has none of `net_view`, `returned_items`, `correct_purchase`, `void_purchase`, `balance_before_purchase`. |
| P5 | **Purchase returns save no readable note** (`notes = None`), so the Note column on the returns list is empty for them. | Probe step 4; `return_page._post` passes `notes` only in the sales branch. |
| P6 | **No Cash/Credit selector on the purchase invoice** — the amount paid is typed by hand, so it can drift from the total. (This deliberately reverses the Stage 05 decision to scope the selector to sales; the owner has now asked for Cash/Credit purchase behaviour.) | `entry_page` gates the selector on `self._mode == "sale"`. |
| P7 | **No `purchases.correct` permission and no `purchases.corrected_from_id`.** | `permissions` holds only view/create/edit/post/void/return/print for purchases. |

### 14B.1 Migration 0009 (schema v9, forward/idempotent, appended never edited)

Only what is genuinely required: `purchases.corrected_from_id` (mirroring
`sales.corrected_from_id`) and the `purchases.correct` permission with grants to
Admin / Manager / Accountant. Nothing else — supplier payments, the supplier
ledger and purchase returns all already have their storage.

### 14B.2 Engine work

Mirror the locked, owner-accepted sales contracts rather than inventing new ones:

* `PurchaseDocumentService.net_view(purchase_id)` — per line `bought` / `returned`
  / `net_quantity` / `net_line_total`, `active_lines`, `gross_total`,
  `returned_total`, `net_total`, `net_remaining`; the **single** answer to "what is
  this bill worth now", read by the list, the reopened bill, the print, the
  supplier balance and any purchase report.
* `list()` enriched with `returned_total` / `net_total` / `net_remaining`, summed
  with `Decimal`, never a SQL aggregate (§24).
* `returned_items(purchase_id)` + `PurchaseReturnRepository.returned_lines_for_purchase`.
* `balance_before_purchase(purchase_id)` — the supplier's payable excluding this
  bill's own net remaining, so Previous Balance never double-counts.
* `void_purchase` — reverse stock, ledger and payable, stamp VOID, keep the
  document, refuse when a return exists.
* `correct_purchase` — **amends the ORIGINAL bill in place**: same row, same
  document number, surviving lines updated in place so `purchase_return_lines
  .purchase_line_id` (ON DELETE RESTRICT) stays valid, compensating stock
  movements, a **difference-only** journal, and an audited line diff. Refuses only
  to drop a returned item or go below the returned quantity.
* Reject a **credit purchase with no registered supplier** (P1), the exact mirror
  of the walk-in-credit rejection on sales. A cash purchase from an unregistered
  supplier stays allowed.
* A readable purchase-return note, localized by the screen, generated by the
  service when the caller supplies none.

### 14B.3 UI work

* **Purchase Invoice**: Cash/Credit selector with Paid/Remaining derived from the
  same existing grand-total computation (no second calculation); reopening a
  posted bill through `load_for_correction`, showing the **net** position with a
  read-only **Returned Items / اقلام برگشتی** panel and Previous Balance excluding
  this bill — the same shapes now locked on the sales side.
* **Purchase List**: Billed / Returned / Net Total / Paid / Remaining / Status,
  with Correct and Void row actions.
* **Purchase Return**: pass the localized note; the Already-Returned column is
  already shared.
* **Suppliers**: a supplier-focused management view (code, name, phone, payable,
  last purchase) with "View Account" into the existing supplier ledger.
* **Printed purchase invoice**: net quantities, and the fully-returned note key.
* EN + Dari with genuine RTL throughout.

### 14B.4 Required consistency (the acceptance contract)

**Purchase List = Purchase Invoice View = Printed Purchase Invoice = Purchase
Return = Supplier Balance = Inventory = Stock Movement.** Every one of those reads
`net_view` or the movement ledger; none stores its own copy.

### 14B.5 Mandatory real workflow test (must reconcile everywhere)

Buy Rice 10 × 100 = 1000 on credit → partial return 4 (net 600) → correct the bill
to 8 × 100 (net 400 after the return) → pay the supplier 200 → full return of the
remainder. At every step: stock, the Purchase List row, the reopened bill, the
printed bill, the supplier balance, the supplier ledger and the movement history
must agree, with exactly ONE bill carrying its original number, the return
documents intact and the journal balanced. **Stage 07 is not finished if any two
disagree.**

### 14B.6 Delivery rules

Preserve the layered architecture and §24 Decimal rules; migration only as in
§14B.1; preserve EN/Dari + RTL; do not touch authentication, RBAC, licensing,
sales, inventory posting or numbering beyond what is listed here; **Stage 05 and
Stage 06 are LOCKED** — any needed change there stops and uses the §33 procedure.
Full suite plus new engine, integration and UI tests; real screenshots EN + Dari;
PROJECT_MASTER updated. Do not merge PR #4; do not start Accounting Reports or
Costing.

### 14B.7 Payment model (owner decision, 2026-09-04)

Purchases take a **three-way** model, unlike sales:

| Type | Paid | Remaining |
|------|------|-----------|
| Cash | Grand Total | 0 |
| Credit | 0 | Grand Total |
| **Partial** | the operator's own figure | Grand Total − Paid |

Paid may not be negative and may not exceed the Grand Total; Remaining
recalculates automatically as lines change. Any **later** payment goes through
the existing Supplier Payment module and never touches the bill, so no duplicate
payment or accounting entry is created. The supplier balance always reconciles
with the bill, its payments, its returns and the reports.

Sales keep the strict Cash/Credit model — a part-paid sale is a Credit invoice
plus a Receipt — so the Partial option is offered on purchases only.

### 14B.8 Implementation record (IMPLEMENTED — NOT LOCKED)

All seven gaps in §14B.0 are fixed; each was reproduced on a real database
first and the workflow was then driven through the real screens.

**Migration 0009 (schema v9)** — `purchases.corrected_from_id`, the
`purchases.correct` permission with Admin/Manager/Accountant grants, and an
index on `purchase_returns(purchase_id, status)`.

**Engine** — `net_view` (per line `bought`/`returned`/`net_quantity`, plus
`gross_total`/`returned_total`/`net_total`/`net_remaining`) is the single answer
to "what is this bill worth now"; `list()` enriched with the same figures summed
in `Decimal`; `returned_items`; `balance_before_purchase`; **`correct_purchase`
amends the SAME bill in place** (surviving lines keep their ids so
`purchase_return_lines.purchase_line_id` stays valid, compensating stock
movements, a **difference-only** journal, an audited line diff, refusing only to
drop a returned item or go below what went back); `void_purchase` (reverses
stock, ledger and payable; blocked while a return exists); a readable return
note; and a **credit purchase without a registered supplier is refused** —
previously it posted a payable with no party that no ledger could show.

**UI** — Cash/Credit/**Partial** on the purchase invoice; reopening a posted bill
on its net position with the read-only **Returned Items** panel and a Previous
Balance that excludes the bill itself; Purchase List columns Billed / Returned /
Net Total / Paid / Remaining with Correct and Void actions; the printed bill nets
its quantities and explains a fully-returned bill; the Persons list gained a
ledger-derived **Balance** column labelled per side. EN + Dari RTL throughout.

**Two labelling defects found in screenshot review:** the purchase header chip
showed the supplier's payable under a "Supplier Ref." label (now **Supplier
Balance**), and the printed purchase bill said "Bill To / Customer Code" for a
supplier — `InvoiceData` gained an additive `party_kind` so the shared print
engine says **Bill From / Supplier** on purchase documents, with the default
preserving the locked sales wording.

**Verification.** Full suite **568 pass** (+30 in
`tests/test_stage07_purchases.py`). The mandatory workflow ran on a real on-disk
database through the real screens — buy Rice 10 × 100 = 1000 on credit → return 4
(net 600) → correct to 8 × 100 (net 400) → pay the supplier 200 — and every
surface agreed at every step: Purchase List, the reopened bill, the printed bill,
the purchase return, the supplier balance, inventory and the movement history,
with ONE bill carrying its original number, the return intact and the ledger
balanced. Three pre-existing tests asserted contracts this stage supersedes (the
migration count, the permission total, and a purchase-entry test that relied on
the amount paid being implicitly blank).

### 14B.9 Control audit against the official scope (owner-directed)

The owner noted that implementation began before the Stage 07 prompt was formally
approved, and directed that the work be treated as a **draft** and audited against
the official scope before any approval is sought. No new features were added.

Each scope item was exercised on a real on-disk database through the real screens:

| Official scope item | Verdict |
|---------------------|---------|
| Supplier Management | **Matched, with a deviation** — delivered as the shared Persons screen (supplier role filter, ledger-derived Balance column, View Account into the Supplier Ledger) rather than the **dedicated supplier view** §14B.3 promised. Functionally complete; structurally not what the plan said. |
| Purchase Invoice | Matched |
| Cash / Credit / Partial Payment | Matched (§14B.7) |
| Supplier Balance | Matched |
| Purchase Correction on the SAME invoice | Matched |
| Partial + Full Purchase Return | Matched — both verified end to end |
| Supplier Payments | Matched — a payment leaves the bill untouched; no duplicate entry |
| Inventory integration | Matched |
| Purchase List / Invoice View / Print consistency | Matched |
| EN / Dari + RTL | **Two defects found and fixed** (below) |

**Two owner-reported defects, each reproduced before being fixed:**

1. **Line total could disagree with the Grand Total.** Typing in the grid was
   always correct, but the line dict kept a stored `total` — a second copy of
   derived data — that another code path could leave stale, producing a row
   reading 12 × 100 = **1,000** under a Grand Total of **1,200**. The total is now
   **computed at render time** from qty × price − discount, so no path can make
   the cell, the subtotal and the grand total disagree.
2. **The Dari UI showed the English return note.** The note was stored as text at
   posting time, so a return posted from the English screen showed
   "Rice — Qty 4 returned." to a Dari reader. The sentence holds nothing the
   return's own lines do not, so the returns list now **derives it in the reader's
   language** — Dari naming the item by its Dari name
   ("برنج به تعداد 4 دانه برگشت شد."). A note the operator typed by hand is
   detected and preserved exactly as written. This touches the shared returns list,
   so it corrects the same defect on the sales side; no stored data changes.

**Verification.** Full suite **573 pass** (+5). The audit script drove every scope
item on a real database in English and Dari: the required consistency chain held
at each step (list 600 = invoice view 600 = print 600 = returnable 6 = supplier
balance 600 = inventory 6 = movement sum 6), a full return took the bill, the
balance and the stock to zero with the printed sheet explaining itself, and the
ledger stayed balanced.

**Recommendation:** *READY FOR OWNER REVIEW.* Stage 07 is **not locked and not
merged**; Stages 05 and 06 are unchanged. **One deviation is outstanding for the
owner to accept or reject: supplier management as a Persons filter rather than a
dedicated Suppliers screen.**

### 14B.10 Supplier UI finalization (closes the §14B.9 deviation)

The owner resolved the deviation: keep the shared Persons architecture
internally, add a **dedicated Suppliers screen** in the UI. No second supplier
data source, no duplicated supplier record, no duplicated balance.

**How it stays one source of truth.** `SuppliersPage` subclasses `PersonsPage`
and is *pure configuration* — `PersonsPage` was refactored into three overridable
hooks (`_page_columns`, `_page_config`, `_role_filter_choices`) plus a
`_default_role` attribute, so the supplier view is a different presentation of
the same page, not a second page. It reads people through the same
`parties` service with `role="supplier"`, creates and edits through the same
person form (Supplier pre-ticked), and takes every figure from
`party_ledger.supplier_ledger(...)["totals"]` — the same call the Supplier Ledger
screen makes. A dual-role party's Current Balance names both sides rather than
netting them into a single misleading number. Columns: Supplier Code, Name,
Business Name, Phone, Current Balance, Total Purchases, Total Paid, Remaining
Payable, Status, View Account. Search, New Supplier, Edit Supplier and Open
Supplier Ledger all work; the screen is registered under Base Data and shares the
main window's `_open_party_account` handler.

**A reconciliation bug found while wiring it up (confirmed, not assumed).**
`supplier_totals` and `customer_totals` did not add up: a supplier with a 1,000
bill, a 400 return and a 200 payment reported Purchases 1,000 − Paid 200 = 800
against a Payable of 400. The totals counted documents **gross of returns** and
counted only the separate Payment/Receipt documents as "paid", ignoring the
amount paid on the document itself, while the balance was computed correctly from
the ledger. Both are now derived so that **total − paid == balance** always holds:
documents count **net of posted returns**, and paid/received includes the amount
settled on the document plus the payment documents. Same data, corrected
arithmetic — no schema change and no stored value rewritten.

*This changes a figure displayed by the Stage 05-locked customer ledger summary.*
It is reported under the §33 rule as a **confirmed integration bug**: the three
figures on that screen previously could not be reconciled by the reader. Nothing
else about Stage 05 behaviour is touched, and `tests/test_owner_fixes.py` was
updated from the old non-reconciling expectation to assert the identity.

**Two shared-table rendering defects fixed (both reproduced first).** The
"View Account" row action rendered as an **empty box**. Two independent causes,
each confirmed by measuring the live widget rather than by eye:
1. The button was 42px tall inside a 26px cell, so its label was clipped away.
   `setFixedHeight()` could not fix it — Qt applies a stylesheet `min-height` by
   calling `setMinimumHeight()` on the widget itself, which overrides it — so the
   height now comes from the sheet (`QPushButton[role="row-action"]`).
2. `RowActions` set an **unscoped** `background: transparent` stylesheet, which
   in Qt also applies to every child, stripping the fill from the accent button
   and leaving white text on a white row. The selector is now scoped to the
   container by object name.
Both live in shared UI code, so every table's row actions were checked
(purchases, sales, payments, persons) — all fit their cells and paint their
labels.

**Verification.** EN and Dari captured **inside the real main window** on an
on-disk database, so RTL is genuinely exercised (a standalone page inherits no
direction). The Suppliers list and the ledger reached through View Account show
the same three figures — 1,100 / 400 / 700 — with the ledger's running balance
1,000 → 600 → 400 → 700. Stage 07 remains **not locked and not merged**.

### 14B.11 Documented future item — ledger Description is stored English text

**Owner decision (2026-09-06): do NOT change this now.** Recorded here so it is
not rediscovered as a defect.

**What the reader sees.** In the Dari Customer/Supplier Ledger, every column is
translated and the layout is properly RTL, but the **Description** column still
reads `Purchase PUR-000001` / `Payment PAY-000001` in English.

**Why.** The description is composed **at posting time** and written into
`financial_entries`, so it is stored text, not a translation key — the same
class of defect as the return note fixed in §14B.9, but on ledger rows rather
than document notes. The stored value is a permanent record of what was posted;
changing how it is *written* would not fix rows already in a live database.

**The eventual fix (not now).** Store the parts a description is made of — the
document type and its number — and compose the sentence in the reader's language
at display time, with a fallback to the stored text for rows written before that
change. This touches locked Stage 04/05 posting, so it needs the §33 procedure
and belongs to a stage that owns localization work, **not** Stage 07.

**Scope note.** Cosmetic only. No amount, balance, document number or posting is
affected, and the document type is also shown in its own translated **Type**
column, so a Dari reader can already tell what each row is.

### 14B.12 🔒 LOCK RECORD — Stage 07 owner-approved and LOCKED (2026-09-11)

**Stage 07 — Purchases Parity / Purchase & Supplier Management is LOCKED.**
Owner-approved after manual acceptance testing of the Stage 07 Windows test
build. Its frozen public contracts are listed in §8. **PR #4 is not merged**
(owner's instruction). **Stage 08 is not started.**

**Accepted state**

| | |
|---|---|
| Locked commit | `c10dfd4` |
| Manually tested build | `5a8ea99` — release `stage07-test-build`, asset `ZenithBusiness-Stage07-TestBuild-win64.zip` |
| Difference between them | one UI sizing fix found during the lock run (below); no business logic, no schema, no posting |
| Tests | **600 pass**, 56 test files, run on a rebuilt environment |
| Database schema | **v9** (migration 0009 `stage07_purchases_parity`) |
| Scope audit | §14B.9 — all ten official scope items matched, the one deviation closed in §14B.10 |

**One defect found during the lock run and fixed before freezing.** Running the
Stage 07 tests in isolation — rather than after the rest of the suite — failed
where the full suite passed. The cause was real, not test noise: a row-action
button's minimum width was **computed by hand** (`text width + margins`), which
lands a pixel short of what Qt actually needs under a different font or DPI, and
one pixel is enough for Qt to clip the label away and leave the empty box the
owner originally reported. The shipped build bundles Vazirmatn, where the guess
happened to be exact, so the manually tested build renders correctly — but the
margin was a single pixel. Three changes remove the guesswork:

* the button's width floor is now its **own polished size hint**, not arithmetic
  over fonts, padding and borders;
* the action **column** is fitted from the **assembled widget's** size hint,
  carrying the table's per-cell overhead, instead of magic constants; and
* that fit also runs on `showEvent`, because rows are built before the page has
  geometry — where a cell has no width and the overhead is invisible.

Verified on the real main window in **both** languages across Suppliers, Persons
and Items: every row action fits its cell and paints its label, including the
longer Dari "مشاهده حساب". The regression test now asserts that the label is
**lighter than the fill behind it** rather than an exact colour, so it no longer
depends on which font a run happens to load, and it passes in isolation and in
the full suite alike.

**Stage 07 behaviour must not change from here** except to fix a confirmed bug,
via the §33 STOP procedure — the same discipline that produced §13K.2.

---

## 14C. Stage 08 — Costing & Inventory Valuation (🔒 LOCKED 2026-09-17)

**Stage 08 is LOCKED (2026-09-17, owner-approved); PR #4 is NOT merged and
Stage 09 is not started.** The lock record is §14C.10; frozen contracts are §8. The
constitution has required this since day one (§4.7 / Spec §11: *"Weighted Average
Cost. Single, centralized, testable costing engine. Sales use the correct cost
basis for COGS/gross profit. No duplicated cost logic."*). Until now the system
knew how much stock it had and nothing about what that stock was worth.

### 14C.0 Baseline — reproduced before anything was written

On a real on-disk database, the owner's scenario (buy 10 @ 100, buy 10 @ 120,
sell 5) produced a correct quantity of 15 and **no cost information at all**:
`inventory_movements` had no cost column, and no service could answer what the
stock was worth or what the sale cost. Recorded as the before-state.

### 14C.1 The decision that shaped everything: cost is captured, never re-derived

The obvious design is to leave the ledger alone and work a movement's cost out on
demand from the purchase that caused it. **That cannot work here**, and the
inspection proved it rather than assuming it: `correct_purchase` rewrites its
line row **in place** (same id, new price), so after a correction the price a
movement was actually made at is gone. A cost derived later would silently use
today's price for yesterday's receipt.

So a movement's cost is recorded **when the movement happens**, exactly like its
quantity, and a later edit posts a new compensating movement instead of
rewriting history. This is not a second source of truth — it is the SAME ledger
row answering a second question, which is precisely what the constitution's §10
describes ("movements with product, warehouse, quantity, type, source doc/ID,
datetime, user, **and cost**").

### 14C.2 Migration 0010 (schema v10, forward/idempotent, appended never edited)

`inventory_movements.unit_cost` (costing precision) and `.total_cost` (money
precision, signed like the quantity), plus an item+warehouse+id index. Both
nullable, so the migration is additive.

**Existing databases are back-filled.** A live database already holds purchases
and sales; leaving them uncosted would tell the owner their stock is worth
nothing. The backfill replays each movement in ledger order through the SAME
engine that costs new ones — there is no second costing path to disagree with —
and is idempotent, so re-running never re-values history.

### 14C.3 One engine, at the one choke point

`services/costing.py` holds the rules; they are applied inside
`InventoryRepository.add_movement`. Every posting path in the application funnels
through that one method, so **no route can create stock that nobody costed** —
and **no locked Stage 05/06/07 service had to change to get costing.** Callers
pass exactly what they always passed; cost is derived, never supplied.

The rules, averaged per **(item, warehouse)** because valuation must be
reportable per warehouse and a transfer must not change what the company is worth:

| Movement | Costed at |
|---|---|
| Purchase, opening stock | the price actually paid (`line total / quantity`, so a discount lowers the cost) |
| Sale, issue, transfer out | the current weighted average — for a sale, that is COGS |
| Correction / void reversal | the cost the ORIGINAL movement went at, never today's average |
| Purchase return | what was paid for those goods, via the return's own link to the purchase line |
| Sale return | the cost the sale took them out at |
| Transfer in | the EXACT value that left the other warehouse |
| Adjustment in | the current average, so the average is undisturbed |

### 14C.4 Two rounding decisions, both made for a reason

* **`total_cost` is stored at money precision.** Sub-cent fractions were tried
  first and rejected: rounding a sum is not the same as summing rounded parts, so
  warehouse rows stopped adding up to the company total. Whole cents mean every
  subtotal at every grouping level adds up exactly.
* **A transfer moves the exact value, not a re-multiplied unit cost.** The
  arriving side takes the paired movement's `total_cost`, so the company total is
  unchanged to the cent — the owner's explicit requirement — rather than landing
  a cent away from it.

### 14C.5 Reports

Inventory Valuation, Cost of Goods Sold and Gross Profit, EN/Dari, printed on the
**existing A4 inventory-report sheet** rather than a second print standard. Net
sales is read from the locked Sales Reporting engine; gross profit is
`net sales − COGS` with both halves shown so the subtraction is checkable.
**No P&L and no balance sheet** — out of scope by instruction, and they need
operating expenses and the whole chart of accounts, which belong to an accounting
stage.

### 14C.6 Two engine bugs the tests caught (neither found by reading the code)

1. **COGS double-counted a corrected invoice.** Selecting the sales side by
   `movement_type` counted the original sale AND its replacement while ignoring
   the compensating movement that undoes the first charge. Selecting by
   `reference_type` (SALE, SALES_RETURN, SALE_CORRECTION, SALE_VOID) fixes it.
   On the real-data scenario this moved COGS from 976.67 to **426.67** and gross
   profit from −376.67 to **+173.33** — the difference between a report that
   looks broken and one that is right.
2. **The backfill averaged a movement against itself.** When re-costing an
   existing row the row is already in the ledger, so it polluted the average it
   was about to be priced from. A replay boundary (`before_id`) fixes it.

### 14C.7 Verification

The owner's mandatory scenario, on a real on-disk database, reconciling
**Inventory Qty = Costing = Inventory Value = COGS = Reports after every step** —
two purchases, a sale, a sales return, a purchase return, a sale correction, a
purchase correction, a stock adjustment and a warehouse transfer. Every step
asserts the invariants, not just the figures: value equals the ledger's own sum,
item rows and warehouse rows both add up to the company total, and no movement is
left uncosted.

Headline figures, exactly as the owner specified: **qty 20, average 110, value
2,200; sell 5 → net sales 750, COGS 550, gross profit 200, remaining 15 @ 1,650.**
A transfer left the company value at **1,369.33 before and after**.

`tests/test_stage08_costing.py` adds **24 tests**. The three report screens were
driven through the real main window in EN and Dari on an on-disk database, with
the figures on screen compared against the engine rather than merely counted.

### 14C.8 Known limitations (carried into review)

* **Valuation is weighted average only** — no FIFO/LIFO, by instruction.
* **Opening stock is valued at the item's purchase price**, the only cost figure
  the system has at that moment; an explicit opening *value* field would be a
  Stage 09+ question.
* **An inbound adjustment into empty stock** falls back to the item's purchase
  price, since there is nothing to average.
* **No accounting posting for COGS yet.** Stage 08 reports cost; it does not post
  a COGS/Inventory journal, which belongs with the accounting stage.
* **The valuation is "as of now" by default.** An `as_of` date is supported by the
  read layer, but the screen offers a live position rather than a historical one.
* **Cross-unit quantity totals.** A company "total quantity" adds bags to litres;
  it is a tally, not a business figure. The meaningful company total is the value.

### 14C.9 Owner report round — three printed-report defects fixed

Owner-reported, each reproduced on real data before being touched, and each
fixed without changing locked Stage 05/06/07 behaviour.

**1. The reports printed the PRODUCT name as the customer's identity.** First-run
setup stores the business name as a **setting** (`company.name`), while the
Company screen writes the `companies` row. `_company_info` read only the row, so
a customer who had never opened that screen saw *"Zenith Business"* on their own
report — the exact opposite of the rule those documents were built to follow.
The shared identity source now falls back through the setup name, leaving the
product name as the last resort it was meant to be. Address, phone, email and
**tax id** print when configured; the costing sheet carries the full
`CompanyInfo` rather than a reduced copy, so the tax id reaches the page without
a second identity shape to keep in step.

*This is shared with the locked Stage 05/06/07 reports.* It can only replace the
product name with the customer's own configured name — which those stages'
own documentation already states they want ("the CUSTOMER's business identity …
never the Zenith Soft developer identity") — so it is reported as a **confirmed
bug fix against their stated contract**, not a behaviour change.

**2. A two-item valuation reported "4 item(s)".** The Stage 06 sheet counts the
rows it is handed, and the totals had been folded in as rows. Stage 08 now has
**its own print document**: the table holds items, the totals are a block of
their own beneath it, and the count counts items. The locked Stage 06 document
is untouched.

**3. Dari printed in whatever face the machine had.** The shared font stack lists
system faces after Vazirmatn, so on a machine with Segoe UI or Tahoma — every
Windows machine — Qt could substitute one of them for Persian text and the sheet
came out in a different face from the rest of the application. This did **not**
reproduce on Linux, where those fallbacks do not exist, which is exactly why it
reached the owner. The Stage 08 sheet pins Dari to the bundled **Vazirmatn** with
no fallback at all, across title, headers, table, totals and footer, and sets the
widget font as well as the stylesheet. **English keeps the shared stack
unchanged.** RTL is unaffected.

**4. Gross Profit counted its own calculation steps as items.** The sheet's foot
read "5 item(s)" for the five figures that make up the profit — net sales, COGS
and the rest are not stock, so the line is now omitted from that report
entirely. Inventory Valuation and COGS keep their counts, which do describe
items.

**Windows verification of the Dari font.** The substitution this fixes cannot
happen on the Linux development machine, because the fallback faces do not exist
there — which is precisely why it reached the owner. The Windows build workflow
now runs the font tests **on windows-latest before freezing the executable**, so
"Dari resolves to bundled Vazirmatn" is checked on the platform where it can
fail, and a regression there fails the build rather than shipping.

`tests/test_stage08_report_fixes.py` adds **20 tests**, including one asserting
that the locked Stage 06 print data is still untouched and one that fails if the
PyInstaller spec ever stops bundling the font files.

### 14C.10 🔒 LOCK RECORD — Stage 08 owner-approved and LOCKED (2026-09-17)

**Stage 08 — Costing & Inventory Valuation is LOCKED.** Owner-approved after
manual acceptance testing of the Stage 08 Windows test build. Its frozen public
contracts are in §8. **PR #4 is not merged** (owner's instruction). **Stage 09 is
not started.**

**Accepted state**

| | |
|---|---|
| Locked commit | `4027a9c` (the lock record itself; the code it locks is `b0fcd2a`) |
| Manually tested build | `b0fcd2a` — release `stage08-test-build`, asset `ZenithBusiness-Stage08-TestBuild-win64.zip`, SHA-256 `b762cb41…5b0f276` |
| Difference between them | **none** — the tested build is the locked commit |
| Tests | **644 pass**, 58 test files |
| Database schema | **v10** (migration 0010 `stage08_costing_valuation`) |
| Costing method | Weighted average, per (item, warehouse) |
| Windows verification | the Dari font tests run on `windows-latest` before the exe is frozen; 8 passed on the runner that produced the accepted build |

**The owner's acceptance numbers, reproduced on a real on-disk database:** buy
10 @ 100 and 10 @ 120 → qty 20, average 110, value 2,200; sell 5 @ 150 → net
sales 750, COGS 550, gross profit 200, remaining 15 @ 1,650. The chain
**Inventory Qty = Costing = Inventory Value = COGS = Reports** held after every
one of the eight steps, including a sales return, a purchase return, a sale
correction, a purchase correction, a stock adjustment and a warehouse transfer
that left company value at 1,369.33 before and after.

**Stage 08 behaviour must not change from here** except to fix a confirmed bug,
via the §33 STOP procedure — the same discipline that produced §13K.2.

---

## 14D. Stage 09 — Accounting Reports & Financial Statements (🔒 LOCKED 2026-09-18)

**Stage 09 is LOCKED (owner-approved 2026-09-18) and NOT merged. Stage 10 is not
started.** Stages 05–08 are LOCKED and **none of them was modified** — including
the COGS integration, which is the part that looked like it would have to touch
locked sale posting. The frozen contracts are in §8; the lock record with the
accepted state is §14D.7.

### 14D.0 Baseline — reproduced before anything was written

The owner's scenario on a real on-disk database (buy 8 @ 125, sell 5 @ 200, rent
100) showed a ledger that balanced and still told a false story:

| | |
|---|---|
| Cost of Goods Sold (5000) | **0.00** — the sale never charged cost |
| Inventory (1200) | **1,000.00**, while the stock was genuinely worth **375.00** |
| Overstatement | **625.00** — exactly the COGS that was never posted |

A purchase debited Inventory and a sale credited only Revenue, so **Inventory
only ever grew**. Stage 08 already knew the 625; nothing charged it.

### 14D.1 COGS integration — and why no locked code had to change

Posting from inside the sale would mean editing LOCKED Stage 05/07 services, or
turning the Stage 08 repository choke point into a journal-posting orchestrator —
a repository posting double-entry is the wrong place for it, and both would break
a locked contract. `CogsPostingService` instead **reads** the costed ledger and
posts what is missing::

    Dr  Cost of Goods Sold     the cost the goods left at
        Cr  Inventory

Two properties make that equivalent to posting inline, and they are the reason
the §33 procedure was **not** needed:

* each entry is dated with the **movement's own date**, so a statement for any
  past period is correct once posted; and
* every report calls `sync()` before it reads, so what a user sees is never
  missing a cost.

The amount is **taken from the Stage 08 movement**, never recomputed and never
from the selling price. Because the value comes from the movement, the hard cases
need no special handling: a **sales return** posts a movement that brings goods
back at the cost they left at, so its journal is the exact reverse; a
**correction** or **void** posts its compensating movement the same way; and a
corrected invoice is never double-charged.

**Exactly once is a database guarantee, not a hopeful check.** A COGS entry is
keyed `source_type='COGS'`, `source_id=<movement id>` under a **unique index**
(migration 0011), so a repeated or concurrent run cannot produce a second charge.
A test asserts the database itself refuses the duplicate.

### 14D.2 Migration 0011 (schema v11, forward/idempotent, appended never edited)

The COGS uniqueness index, reporting indexes on account / entry date / party, and
an `accounting.reports` permission granted to Administrator, Manager and
Accountant. **No back-fill is needed**: history is posted on demand and dated by
the movement it came from, so an upgraded database reports last month correctly.

**Migration 0012 (schema v12)** was appended in the report-polish round: a
data-only rewrite of COGS journal descriptions from the internal
`Cost of goods sold — movement <id>` to the document reference
`COGS — SALE-000009`. It changes no amount, date, account or line, is
re-runnable, and matches on the old text so an operator-edited description is
left alone. See §14D.5c.

### 14D.3 The six statements

All read `financial_entry_lines` — there is no reporting store — and all sum with
`Decimal`, never a SQL aggregate (§24).

| Report | Contract |
|---|---|
| **Trial Balance** | opening / debit / credit / closing per account; **total debits == total credits** |
| **Profit & Loss** | Net Sales − COGS = Gross Profit; − Operating Expenses = Net Profit |
| **Balance Sheet** | **Assets = Liabilities + Equity** |
| **General Ledger** | date, reference, description, debit, credit, running balance; date and account filters |
| **Cash & Bank** | opening / in / out / closing for the fund accounts |
| **Receivables / Payables** | per party, aged Current / 1–30 / 31–60 / 61–90 / 90+ |

**COGS is an expense but not an operating one** — it sits above the gross-profit
line, so operating expenses are every other EXPENSE account. Adding an expense
account needs no code change.

**Equity carries the period's own result.** A balance sheet built only from
EQUITY accounts cannot balance while income and expense accounts are open,
because the profit has nowhere to sit. There is **no year close in Stage 09** (out
of scope by instruction), so the result is folded into equity as its own line.
That is what makes `A = L + E` an identity rather than a hope.

**Ageing settles the oldest debt first.** Payments do not say which invoice they
clear, so the standard rule applies; what survives is aged by the date of the
charge still standing, which is why the buckets always add back to the party's
balance.

### 14D.4 Two defects caught by looking at the screens

1. **"Balanced: 0.00" instead of "Yes".** The status line guessed whether a value
   was money by trying to parse it — and `D()` turns anything unparseable into
   **zero rather than raising**, so the word "Yes" printed as "0.00". Summary
   entries now carry how to format themselves instead of being guessed at.
2. **"Profit _Loss" and "Cash _Bank" on the tabs.** Qt reads a lone `&` as a
   keyboard mnemonic; the report titles are the first in the application to
   contain one. They are escaped like every other label.

### 14D.5 Verification

The owner's mandatory scenario on a real on-disk database, with every
reconciliation they listed:

| Check | Result |
|---|---|
| Net sales / COGS / expenses | 1,000 / 625 / 100 |
| Gross profit | **375.00** |
| **Net profit** | **275.00** |
| Trial balance | Dr 2,725.00 == Cr 2,725.00 |
| Balance sheet | Assets 1,275.00 == Liabilities + Equity 1,275.00 |
| General Ledger vs Trial Balance | every account agrees |
| Customer receivable vs customer ledger | 1,000.00 == 1,000.00 |
| Supplier payable vs supplier ledger | 1,000.00 == 1,000.00 |
| COGS journal vs Stage 08 COGS | 625.00 == 625.00 |
| **GL Inventory vs Stage 08 valuation** | **375.00 == 375.00** (was 1,000 vs 375) |

Then held through a sales return, a sale correction and a void. All six reports
were driven through the real main window in EN and Dari with the on-screen
figures compared against the engine. `tests/test_stage09_accounting.py` adds
**31 tests**.

#### 14D.5a Second verification round — the six reports the owner named

A larger dataset was built specifically so that **every ageing bucket is really
populated** as of 2026-09-17 (two customers, two suppliers, seven invoices, five
bills, part-payments on both sides), because a scenario where everything lands in
"Current" cannot test ageing at all.

| Report | Verified |
|---|---|
| General Ledger | per account, running balance ends at the closing; opening + Dr − Cr == closing; **every** account's GL closing == its TB closing; unfiltered GL totals == TB totals; a date filter returns only rows in range and its own opening/closing are consistent |
| Cash & Bank | cash in 5,000 / out 3,100 / closing 1,900; bank in 1,000 / out 900 / closing 100; each fund's closing == its TB closing **and** its General Ledger closing |
| Receivables ageing | Current 1,100 · 1–30 2,220 · 31–60 2,100 · 61–90 3,000 · 90+ 4,000 → 13,280; each party's buckets add to that party's balance; total == TB Accounts Receivable == the customer ledgers |
| Payables ageing | Current 1,400 · 1–30 2,600 · 31–60 3,600 · 61–90 3,900 · 90+ 22,000 → 33,500; total == TB Accounts Payable (a credit balance) == the supplier ledgers |
| COGS reversal after a Sales Return | on an item whose average cost is exactly 50.00, selling 10 charges 500.00 and returning 4 reverses **exactly 200.00** — 4 × cost, *not* 4 × the 90.00 selling price |
| COGS after a Sale Correction / Void | correcting 10 → 6 leaves exactly 300.00 charged (not 800.00, which double counting would give); voiding returns COGS to its pre-sale figure to the cent, and Inventory returns to the Stage 08 valuation |

After **every** step above the four standing invariants were re-checked: the trial
balance balances, the balance sheet balances, GL Inventory == the Stage 08
valuation, and the P&L COGS == the Stage 08 COGS.

**One defect was found by this round and fixed** — see §14D.5b. It was found only
because the dataset contained a return, a correction and a void against *recent*
invoices while *older* invoices were still open; the earlier scenario could not
have exposed it.

#### 14D.5b Defect found and fixed: ageing credited the wrong invoice

`_age_party` applied **every** credit oldest-debt-first. That rule is right for a
receipt or a payment, which name no invoice — but a **return, a correction and a
void all name the document they belong to**, and crediting an older invoice
instead misstates the one thing an ageing report exists to state.

On the verification data the customer's balance was right (12,420.00, equal to his
customer ledger) while the ageing was wrong:

| Bucket | Before the fix | After the fix | Truth |
|---|---|---|---|
| 1–30 days | 3,480.00 | **2,220.00** | 1,680 (28 Aug) + 540 (10 Sep sale net of its own return) — the **voided** 14 Sep invoice must not appear at all |
| 90+ days | 2,740.00 | **4,000.00** | the untouched 20 Apr invoice, which nothing had paid |

The fix: `AccountingReadRepository.party_documents` now returns a `charge_key` for
each row — the document it belongs to. `SALE_CORRECTION`, `SALE_VOID`,
`PURCHASE_CORRECTION` and `PURCHASE_VOID` already carry the original document's id
as their `source_id`; `SALES_RETURN` and `PURCHASE_RETURN` carry the *return's* id,
so the parent is read from `sales_returns.sale_id` / `purchase_returns.purchase_id`
in one query per side. `_age_party` then applies an identified credit to **its own**
document and keeps the oldest-first rule strictly for money that identifies
nothing. A credit larger than what is left on its own document spills into the
oldest-first pool, so nothing is created or lost and **the buckets still add back
to the party balance** — asserted per party and in total.

Stage 09 code only; **no locked stage was touched** and §33 did not apply. +5
regression tests: a return credits its own invoice, a voided invoice leaves the
ageing entirely, a correction ages with the invoice it amends, the same on the
supplier side, and an unallocated receipt still clears the oldest debt.

#### 14D.5c Report polish round — ageing totals, ledger naming, ledger header

Three owner-requested report fixes, each verified on the real A4 preview rather
than in the payload alone.

1. **Ageing totals row.** Receivables and Payables now carry a bold totals row —
   Current, 1–30, 31–60, 61–90, 90+ and Balance — on screen and on the printed
   sheet, under the columns they total. The row stays **out of** `rows`: that
   separation is the Stage 08 lesson that folding totals into a table made a
   two-item valuation report "4 item(s)". Statements whose totals are not
   per-column (trial balance, P&L, balance sheet, general ledger, cash & bank)
   have no such row and are unchanged.
2. **General Ledger descriptions name the document.** `Cost of goods sold —
   movement 14` exposed an `inventory_movements` row id the customer cannot look
   up. Lines now read `COGS — SALE-000009`, `COGS Reversal — SRET-000001`,
   `COGS Correction — SALE-000009`, `COGS Void — SALE-000009`. Migration **0012**
   (schema v12) rewrites descriptions already posted, so an upgraded database does
   not keep the old wording; it is data-only, re-runnable, and matches on the old
   text so an operator-edited description is left alone.
3. **The printed General Ledger names its account** — `General Ledger — 5000 Cost
   of Goods Sold  ·  2026-01-01 — 2026-09-17`.

**A fourth defect was found while checking the printed sheet for (3).** The title
label had no width limit and did not wrap, so the longer title overflowed to the
left and printed **over the business name**: the header came out reading *"Kabul
Traders Ltd ods Sold"* — hiding both the customer's identity and the account the
page had just been changed to show. Stage 08's titles are two or three words, so
the unbounded label had never been stressed. The Stage 09 sheet pins the title's
width and lets it wrap; the width is **pinned rather than capped**, because a
word-wrapping `QLabel` reports a narrow size hint and a maximum alone still left
it in five lines. The identity block gets a trailing stretch so its lines stay
together when the header grows. The printed ageing total also appeared **twice** —
once in the new row and once in the totals block beneath — so the block is omitted
when a columnar totals row is present.

All of this is Stage 09's own code: the print sheet is a **subclass** of the
LOCKED Stage 08 document, which is not modified and renders exactly as before.
`tests/test_stage09_report_polish.py` adds **17 tests**; **697 pass**.

### 14D.6 Known limitations (carried INTO the lock, intentional)

* **No period close or year close** — out of scope by instruction. The period
  result is shown in equity rather than moved to retained earnings.
* **COGS is posted when a report is read**, not inside the sale transaction. The
  entry is dated by the movement so every period is correct, but a database
  inspected directly without ever opening a report will not yet hold the charge.
* **Ageing has no credit terms** — "Current" means not yet past its document
  date, because the system has no payment-terms field yet.
* **General Ledger descriptions are stored English text.** The COGS lines now name
  the document (`COGS — SALE-000009`) rather than an internal id, but the label
  itself is English in a Dari statement, as are the seeded account names. Stored
  descriptions were left English by owner decision in Stage 07.
* **Seeded account names are English** (as noted since Stage 05); a Dari
  statement shows translated headings with English account names.
* **Single currency in the statements** — the GL is posted in document currency,
  so a multi-currency book would need a presentation-currency pass.
* **No cash-flow statement** and no comparative/prior-period columns.

None of these was fixed during the lock run, by instruction. They are the
recorded state of the locked stage, not defects.

### 14D.7 Lock record — the accepted state

**Stage 09 — Accounting Reports & Financial Statements is LOCKED.**
Owner-approved on 2026-09-18 after manual acceptance testing of the Stage 09
Windows test build.

| | |
|---|---|
| Locked commit | **`b8a2cfc99dbb7ae81b756bb3958646b310a48a60`** |
| Windows build target | **`b8a2cfc`** — the same commit that was tested (release `stage09-test-build`, run #29, `success`) |
| Test count | **697 passing**, 60 test files |
| Schema version | **v12** (migrations 0011 and 0012) |
| Locked on | 2026-09-18 |
| PR #4 | **not merged** |
| Stage 10 | **not started** |

**Verified at the lock run:** the full suite was run once more on the locked
commit with the working tree clean at `b8a2cfc`, and the published Windows build
targets that exact commit — no Stage 09 behaviour changed between the tested
build and the lock.

**What the acceptance covered.** The owner's mandatory scenario (net sales 1,000
− COGS 625 = gross 375, − expenses 100 = **net profit 275**) on a real on-disk
database, with trial balance Dr 2,725 == Cr 2,725, balance sheet 1,275 == 1,275,
every account's GL closing equal to its TB closing, receivable and payable equal
to the party ledgers, the COGS journal equal to the Stage 08 cost, and **GL
Inventory 375 == Stage 08 valuation 375** where the accounts had held 1,000. Then
a second round over the six reports the owner named — General Ledger, Cash & Bank,
Receivables ageing, Payables ageing, COGS reversal after a Sales Return, and COGS
after a Sale Correction / Void — on a dataset built so that **every ageing bucket
is genuinely populated**, followed by the report-polish round. All driven through
the real main window in English and Dari with the on-screen and printed figures
compared against the engine.

**Three defects were found by the owner's verification rounds and fixed before
the lock**, each in Stage 09's own code:

1. **Ageing credited the wrong invoice.** Every credit was applied oldest-first —
   right for a receipt or payment, wrong for a return, correction or void, which
   name the document they belong to. A **voided** invoice sat in the 1–30 bucket
   (3,480 rather than 2,220) while an untouched April invoice looked part-paid
   (2,740 rather than 4,000). The balance was right and the ageing was not, which
   is the one thing an ageing report exists to get right.
2. **The General Ledger exposed an internal movement id** (`Cost of goods sold —
   movement 14`) to the customer.
3. **The printed title overflowed onto the business name** — the header read
   *"Kabul Traders Ltd ods Sold"*, hiding both the identity and the account the
   header fix had just added. Found by reading the rendered sheet; the tests
   passed because the title string itself was correct.

**No locked stage was modified and the §33 procedure was not invoked at any point
during Stage 09** — including the COGS accounting integration and the printed
sheet, which is a subclass of the locked Stage 08 document rather than an edit to
it.

---

## 14E. Stage 10 — Single-PC Security, Backup & Licensing (IMPLEMENTED — READY FOR OWNER REVIEW)

**Stage 10 is NOT locked and NOT merged. Stage 11 is not started.** Stages 05–09
are LOCKED and **none of them was modified**; the §33 procedure was not needed.

### 14E.0 Baseline — what already existed

Stage 10 was scoped against the code rather than against the brief. A probe on a
real database found **35 of the required capabilities already present** and **22
missing**. Stage 02 already hashed passwords with PBKDF2, counted failed
attempts, locked the account temporarily, recorded the last login and audited all
of it; the backup writer already produced verified, timestamped snapshots; the
database already ran WAL with foreign keys on and explicit savepoint
transactions; and Stage 01 had already reserved the licensing boundary with the
exact requirements Stage 10 implements. **Stage 10 extends all of that and
replaces none of it.**

What was genuinely missing: a re-authentication check, recovery for the only
account on the PC, audited settings, an audit viewer, a restore that survives
failure, integrity verification of the live database, and the whole of licensing.

### 14E.1 Licence verification — public key only

Ed25519, implemented from RFC 8032 with `hashlib` and Python integers. A native
crypto dependency was rejected deliberately: the project ships PyQt6 and nothing
else (Master Spec §2), and a licence check is the wrong place to introduce a
binary wheel that must then be bundled and kept current inside a PyInstaller
build.

**The application can verify and cannot sign.** No private key exists in the
application code, and no shipped module accepts one or produces a signature. Two
tests enforce it, one of them a repository-wide scan so a future change cannot
quietly add signing. Signing lives only in `tests/tooling/` and in `tools/`,
neither of which the PyInstaller spec can reach.

**The verifier was checked, not trusted — and that immediately paid.** The first
implementation **rejected every genuine signature**, because the x-recovery
dropped the `(u·v⁷)` factor of the RFC formula. Every negative test still passed:
a verifier that rejects everything rejects forgeries too. Only a cross-check
against a reference implementation could have found it.

### 14E.2 Machine binding — five traits, weighted

| Trait | Weight | Why |
|---|---|---|
| `machine_guid` | 3 | per OS install; does not travel with a copied folder |
| `volume_serial` | 2 | per filesystem |
| `mac` | 1 | easy to change or spoof |
| `cpu` | 1 | two identical PCs share it |
| `hostname` | 1 | a second PC can be renamed to match |

A licence activates at a score of **5 of 8**. The number is chosen, not guessed:
the three weak traits total 3, so **5 is unreachable without a strong trait**. A
PC with the same model, the same name and a cloned MAC still fails. A legitimate
machine survives a disk swap (3+1+1), an OS reinstall that keeps the disk
(2+1+1+1), a new network card or a rename. Traits are hashed with the product id,
so a fingerprint is not a reusable hardware identifier — verified by asserting no
raw value appears in the fingerprint or in an activation request.

### 14E.3 Restore that is safe when it fails

The Stage 02 restore validated carefully and then copied straight over the live
database. Everything before the copy was safe; the copy was not — a disk filling
up part way would leave **neither** the old database nor the new one, on the day
the customer needs it most.

Restore now takes a **safety backup** of current data, copies to a temporary file
and swaps with `os.replace` (atomic on Windows and POSIX), **verifies the
restored file** before calling it a success, and **puts the previous database
back** if it does not verify. Stale WAL/SHM files are swept so SQLite cannot
apply them to the restored database. It refuses to run without explicit
confirmation and writes the audit entries the old path never wrote.

Proven by simulating a disk-full failure mid-swap: the restore reports failure
and the live database is still present, still passes integrity, still holds its
data, with no partial file left behind.

**A property worth stating:** a restore replaces the database, so audit entries
written *before* the swap go with it. They are preserved in the safety copy, and
the completion entry is written *after* the swap into the restored database, so
it always records that a restore happened and which file it came from.

### 14E.4 Demo, and where it is enforced

`DemoPolicy` defines demo centrally. An expired demo **restricts access, never
data**: nothing in demo mode deletes a row, trims history or rewrites the
database, and backup and licence import stay reachable so the customer can always
take their data with them.

**Enforcement is at the application-shell level, not inside posting.** Gating
individual postings would mean either editing locked Stage 05–09 services or
putting a licence check inside `AuthorizationService.require`, which is a frozen
Stage 03 contract. Neither is permitted without §33, and a licence gate is not a
bug fix — so demo restriction is applied where Stage 10 owns the code. This is a
deliberate scope decision, recorded for the owner rather than hidden.

### 14E.5 Verification

101 tests added; **798 pass**. All three screens driven through the real main
window in English and Dari with RTL, on a real on-disk database.

The full vendor round trip was exercised end to end: the application wrote a
`.zreq`, the vendor tool signed it, and the application imported the resulting
`.zlic` and reported **Licensed**. The tool's pure-Python signatures are
**byte-identical** to the reference implementation.

**One defect found by reading the rendered screen rather than the test output:**
an activated installation still showed *"Development build (unlicensed)"* in the
status bar, because the shell was still asking Stage 01's development provider
instead of the real licence service.

### 14E.7 Hardening pass (owner-requested, 2026-09-19)

Seven items, each verified on real data and on the real screens.

**§1 Licence state — one source of truth.** Two places still lied. The login
screen printed the development-build text **unconditionally**, so an activated
installation told the customer it was unlicensed every time they signed in; and
the boot log reported Stage 01's development provider. All four readers — boot
log, login footer, status bar and License page — now call
`context.licensing.summary()`. Activation is re-verified after a restart.

**§2 Backup security.** Backups were plain SQLite: anyone who picked up the USB
stick could read every customer and balance, and an edited byte would be
restored without complaint. Backups are now `.zbak` containers —
**AES-256-GCM** with a **scrypt**-derived key (n=2¹⁵), the plain intermediate
deleted after wrapping. The header (created-at, schema version, product) is
authenticated but not encrypted, so the Backup screen can list and identify a
backup **without** the passphrase, while a single altered byte anywhere in the
header or body fails the tag and is refused **before** a restore begins.
**Legacy plain `.db` backups still restore**, so this protects data instead of
orphaning it.

**§3 / §7 Release security — and the auditor's own first run failed the build.**
That was the point of scanning the real package, and the three findings were all
**false positives worth understanding**: `cryptography`'s `_rust.pyd` contains
`Ed25519PrivateKey` and `private_bytes` because it is a general-purpose library
that supports signing for everyone who uses it, and `Qt6Network.dll` contains
`-----BEGIN RSA PRIVATE KEY-----` because it *parses* PEM. Capability strings
cannot honestly be asked of a frozen package at all — PyInstaller embeds the
bundled `cryptography` modules inside the executable, so those strings appear
there no matter what our code does.

So the auditor now asks two separate questions. **Key material and tools** — a
PEM header *with a base64 body*, the signing-key file shape, a packaged
`.zlic`, the vendor tool, test tooling, a generator, a bypass, a backdoor, a
default password — fail the build, and are matched against the file **path** as
well as its contents, because a file named `zenith_license_tool.py` ships
whether or not its text mentions its own name. **Signing capability inside
vendored libraries** is reported as information. The real guarantee, that no
module under `zenith_business/` references a private-key type, is enforced at
source level where it can be.

Eleven trials pin this: a clean package carrying the vendored crypto and Qt
binaries passes, and ten planted threats each fail the build.

**The second run then failed on the opposite problem**, and it was the more
interesting one: the auditor could not find our own public-key module, because
**PyInstaller zlib-compresses the Python archive** — our module strings are not
visible to a byte scan at all, so an absence there means nothing. A scan can
prove things are *absent* from a package; it cannot prove the licence path is
*present and working*.

**And the third run failed too, on a mistake worth recording:** the shipped
executable is built **windowed** (`console=False`), where `sys.stdout` is `None`
and a bare `print` raises. The self-test had actually run fine; it looked like a
failure because its report went nowhere. It now writes to a **file**
(`--selftest-out=PATH`) as well as stdout, and CI reads the file — the only
thing it can rely on from a windowed binary.

So that half is now proved by asking the binary. `ZenithBusiness.exe --selftest`
prints the crypto backend, whether signature verification and backup encryption
are available, whether a vendor key is configured, the licence status, the
machine id and the audit-chain state, then exits. CI runs it against the frozen
executable and fails the build unless it reports a working state. It only
prints — a test asserts its source contains no call that could import a licence
or write to the database.

`packaging/audit_release_package.py` scans the
**assembled package** — every file, including the bytes inside the frozen exe and
its PyInstaller archive — for private keys, the vendor tool, the test signing
tooling, licence-generation capability, bypass switches, backdoors and default
passwords, and fails the build on any hit. It also asserts the public-key module
and a verification path are present. It runs in CI before the release is
published, and two tests prove the auditor actually catches a planted key rather
than just printing PASS.

**§4 Crypto review — the home-grown implementation is gone.** Verification now
delegates to **`cryptography`**, and the hand-written RFC 8032 module was
deleted. The earlier justification (PyQt6 as the only dependency) was not worth
it for the one piece of code whose failure mode is silent. It **fails closed**:
no backend means "not licensed", never "assume licensed". The vendor tool keeps
its own stdlib implementation so it runs on an offline machine with no pip, and
a test asserts its signatures are **byte-identical** to the reference and that
the application accepts them — both signing and verification paths audited.

**§5 Audit integrity — a hash chain.** Migration **0013** adds nullable
`entry_hash` / `prev_hash`; each entry commits to the one before it. Nullable is
the design: locked services call `AuditRepository.record` inside their own
transactions and know nothing about hashing, so nothing locked changed. Editing,
deleting or inserting a row breaks the chain and the screen names the entry.

**A gap in this was found and closed during the pass.** Verification originally
skipped unsealed rows, so a forged entry **inserted between sealed entries**
chained correctly around it and passed. A legitimate unsealed row is always at
the tail; anything earlier was put there, and is now reported.

**§6 Machine data privacy.** Already hashed; now asserted. No raw hostname, CPU
string or MAC appears in an activation request or a licence — traits are
fixed-length salted hashes and the fingerprint is a 32-character digest.

**809 tests pass.** Verified in EN and Dari through the real main window: an
encrypted backup listed, the database health check, the integrity check
reporting both success and a detected tampering, Demo → Activated with every
DEMO indicator cleared from the status bar, and the login footer showing the
real licence id.

### 14E.8 Lockout polish (owner-requested, 2026-09-20)

The owner asked for the exact lockout behaviour before asking for any change.
Reading it out on a real on-disk database found a defect that the code review
alone had not: **waiting out the lock did not give the attempts back.**

`set_locked(id, False, None)` moved `is_locked` and `locked_until` and stopped
there, so `failed_login_attempts` was still sitting at the threshold of 5 when
the window expired. The very next wrong password therefore re-locked the account
for another full fifteen minutes. The owner served the wait and got **one** try,
not five — and each further typo cost another quarter of an hour, which is
indistinguishable from an account that has simply stopped working.

Clearing a lockout now clears the count that caused it, in one repository method
(`UserRepository.clear_lockout`) used by every path that lifts a lock: expiry
noticed at the login screen, expiry noticed during sensitive-action
re-authentication, and a recovery code. Each expiry writes an
`auth.lockout_expired` audit entry, so a lock disappearing is recorded rather
than silent.

**The countdown.** A screen that says only "locked" is what makes an owner
reinstall over a wait that would have passed. `LoginGuardState` now carries
`seconds_remaining` alongside the existing minutes, and the login screen shows
*"Account locked. Try again in 12m 34s."* — ticked down once a second, in
English and Dari, and re-rendered on a mid-lock language switch. Pressing Sign In
again does not wipe it (an ordinary error clear leaves a running countdown
alone, because the wait is still real). At zero it says the lock has ended, in
the neutral colour rather than the error red.

**What deliberately did not change**, and is pinned by tests: the lock still
falls on the fifth wrong password, still lasts fifteen minutes, still ignores
attempts made during the window instead of extending them, still rejects the
*correct* password while active, still survives closing the application and the
PC, is still cleared by a successful login or a recovery code, and still locks
nothing at all for a username that does not exist.

+30 tests; **853 pass**, schema v13 (no migration — this is behaviour, not
shape).

**A limitation that remains:** expiry is compared against the PC's own clock, so
someone with access to the machine can end a lock early by moving the Windows
clock forward. On a single-PC install where the owner is also the administrator
there is no external time source to check against, so this is recorded rather
than claimed away.

### 14E.9 Final real-Windows fixes (owner-requested, 2026-09-21)

Ten issues found by the owner testing the actual packaged build. The largest was
architectural, and it is worth stating plainly: **the licence gate was in the
wrong place.**

#### The gate moved in front of login

Stage 10 shipped licensing as a screen under Tools. An unlicensed installation
reached the login form, signed in and used the whole workspace, and licensing
was something you went and looked at afterwards. A licence checked after the
door is open is not a gate.

Activation is now a **page in the same window as login**, in front of it
(`ui/auth/activation_page.py`). It is not a dialog that could be dismissed and
not a separate window that could be skipped: `AuthWindow._show_initial_page`
asks `licensing.evaluate()` first and there is no route from activation to the
login form except a licence that comes back FULL or DEMO. `_handle_login` asks
again on the way through, because a licence can be deleted or expire while the
screen sits open.

The gate is rebuilt on every pass of the main loop, so the licence is
re-verified at every startup *and* every time the workspace is left.

#### A missing licence is no longer a free demo

`NO_LICENSE_FILE` used to evaluate to DEMO with a 30-day clock kept in a
settings row, which made the gate pointless — deleting the licence granted
access. There is a new **`UNLICENSED`** status: not an error, not an
entitlement, and not a way past the screen. A demo is something the vendor
issues and signs, exactly like a full licence, machine-bound the same way, with
its own expiry in the payload.

The wording is per-reason rather than a single "invalid": not activated yet,
issued for a different computer, altered, expired, wrong product, no vendor key.
Telling a customer the wrong one of those costs a support call.

#### A clock a demo cannot be cheated out of

`security/trusted_clock.py` keeps the latest moment the installation has ever
seen and never believes an earlier one: `trusted_now = max(system, high-water)`.
Moving Windows **forward** advances the mark and cannot be undone; moving it
**back** changes nothing. The mark lives in three places, the highest winning,
so deleting any one resets nothing: a DPAPI-sealed file beside the licence
(HMAC-keyed elsewhere), a mirror row in the database, and the licence's own
**signed `issued_at`** as a floor.

A demo that runs out while the program is open no longer waits for a restart —
`MainWindow` re-evaluates every 60 seconds and hands control back to the
activation screen.

**Honest limit:** this raises the cost of a rollback, it does not prevent one. A
local Administrator can delete both stores, and where DPAPI is unavailable the
fallback key is derived from the same machine. What survives all of that is the
signed floor. Anti-rollback on an offline PC whose owner is Administrator is a
cost problem, never a proof.

#### The Persian-keyboard backup inconsistency, explained

The owner found that **Check Backup** accepted the physical keys of the English
password under a Persian layout while **Restore** did not. Probing the real
paths on a real database found the cause, and it was not a keyboard conversion
anywhere in the code — there is none, and the characters Qt reports are the
characters scrypt sees, proven both ways including for Persian text.

The defect was that **creating** a backup never checked the typed text against
the account, although the helper's own docstring claimed it did. With a Persian
layout active the backup got locked with a string the owner never chose. Check
then passed (it *was* the passphrase) and Restore failed (it also
re-authenticates against the real account password). Same keys, two answers.

Creating a backup now verifies the password against the account first and
refuses otherwise: a backup nobody can open is worse than no backup, because it
looks like protection.

#### The rest

* **The pre-restore safety copy** was a plain readable `.db` of the live books.
  It is now a `.zbak` locked with the owner password the restore screen has just
  verified, and rollback decrypts it from the passphrase held in memory rather
  than asking again at the worst possible moment.
* **`bad_passphrase` reached the screen.** One GCM failure has three possible
  causes and the customer cannot be told which, so the message now names all
  three, in EN and Dari.
* **Backups state which password they need** — the one active when the backup
  was made.
* **"Expires: Never" with no licence** became "—". Never is a promise about a
  licence that exists.
* **One source of truth, translated.** Every screen reads the same evaluated
  status; `components.license_summary` chooses the *sentence* from the
  catalogue, so a Dari workspace no longer reports its licence in English.
* **Activation requests** take the customer's own business name from the
  companies row or the setting, and nothing at all when neither is set — never a
  sample name and never the product's.
* **Recovery exists in the UI.** The service was built in Stage 10 behind no
  button. There is now "Forgot your password?" on the login screen and a
  Recovery Code card in My Account that issues one after re-authentication,
  shown once and never again.

#### Verification

+53 tests; **907 pass**, schema v13 (no migration — none of this changes the
database shape). The full vendor round trip was re-run end to end against the
new gate: UNLICENSED → `.zreq` → vendor tool signs a DEMO → 30 days remaining →
FULL import → *Licensed*, in English and Dari.

**Not yet verifiable on the real Windows build:** acceptance items B, C, D and
E–H all sit behind the gate, and the build embeds no vendor key. Item A (fresh
install stops at activation; login unreachable) is testable today. The owner
holds the signing key by their own choice of custody and will supply the public
half.

### 14E.10 Activation by copy and paste (owner-requested, 2026-09-21)

The owner compared the activation flow with their other product and asked for
its shape: copy a code, send it, paste a key back, activate. They were right.
The first version made a customer save a `.zreq`, attach it, receive a `.zlic`,
find it on disk and import it — four file operations for someone who only wants
to start work.

**Nothing about the security model changed.** A Product Key is the same
Ed25519-signed, machine-bound licence a `.zlic` holds; only the packaging is
different. Same signature, same machine binding, same expiry, same
public-key-only verification, same refusals.

#### Two codes

`ZBR1-…` **Request Code** carries this machine's fingerprint and hashed traits
— exactly what the `.zreq` carried, in one line. A short Machine ID alone would
not do: the traits are what let a licence survive a disk swap, and they cannot
be recovered from a truncated id. It is not secret and not signed, so it carries
a CRC — a code mangled in a WhatsApp message is caught **before** the vendor
issues a licence against a machine that does not exist.

`ZB1-…` **Product Key** is the signed licence, about 250 characters. That is
meant to be pasted, not typed, and the paste box shows three lines so a customer
can see the whole key arrived rather than learning it was truncated from a
signature failure.

Why so long: an Ed25519 signature is 64 bytes and cannot be shortened, so the
floor is ~105 base32 characters before any licence content. The payload is packed
binary rather than JSON — base64 of the JSON ran past a thousand characters.

#### One judgement, two shapes

`parse_any_license` returns the same interface for both, so `evaluate()`
verifies and judges them through **one** code path. Two judgement routines for
two shapes is exactly how a second one ends up missing a check.

The trait comparison now accepts a prefix, because a Product Key packs each
trait into four bytes to stay short. This is a bounded weakening of a
*tolerance* check, not of the binding: a 32-bit prefix collides about once in
four billion, and only ever matters on a machine that has already failed the
128-bit fingerprint comparison.

#### Vendor side

`tools/zenith_license_tool.py issue` takes a Request Code and prints a Product
Key — no files in either direction. It records customer, phone and city to a
vendor-side history file that is never shipped. **DEMO length is the vendor's
choice** (`--days`), carried in the signed payload; the customer application has
no setting for it and no way to extend it.

The private key never leaves the vendor side. The codec the application ships
holds no keys and cannot sign, which a test asserts against its source.

#### Three defects found by reading the rendered screens

* **The Dari UI reported refusals in English.** The service raises English
  strings, so `LicenseError` now carries a catalogue key and the screen
  translates it, with the English kept as the fallback for the log and the
  vendor tool.
* **`ZB1-` rendered as `-ZB1` in Dari.** The bidi algorithm reorders a trailing
  hyphen, so the message told the customer their key starts with the wrong
  thing. Fixed with Unicode directional isolates, pinned by a test.
* **A fresh install showed its instructions in red**, which reads as a fault
  when nothing is wrong. Red is now reserved for a licence that was refused.

Two behaviours were also *discovered* rather than designed, and are recorded so
nobody later reads them as bugs: a paste survives line breaks, lower case and a
lost separator after the prefix; and changing only the final character of a key
may leave it valid, because the payload length is not a multiple of five bytes
so that character carries dead bits — the signature covers the decoded bytes, so
an attacker gains nothing from a key that decodes to the licence they had.

+39 tests. The file route stays under **Advanced**: a long code can be mangled
by an email client and a file cannot.

### 14E.11 The Zenith Soft License Manager (owner-requested, 2026-09-22)

A second Windows application, built from the D-Clinic workflow the owner sent:
paste a request code, choose FULL or DEMO, press one button, copy one line. It
is the half of the licensing system that can **issue**; Zenith Business is the
half that can only **check**, and that asymmetry is the security model.

`vendor/zenith_license_manager/` — never collected by the customer build, never
imported by it, and asserted so by three tests and a CI step that looks for the
executable inside the customer package.

#### Where the private key lives, and how

Not in this repository, and not in any build. A signing key is created by the
Manager at run time and written to `%APPDATA%\ZenithSoft\LicenseManager\keys\`
as an encrypted `.zkey`: **AES-256-GCM** with the key derived by **scrypt at
n=2¹⁷** — four times the backup container's work factor, because a backup
protects one customer's books while this protects the ability to issue licences
at all. The header carries the product and the public half and is readable, so
the Manager can list keys without unlocking any; it is fed to GCM as additional
data, so it cannot be edited either.

The passphrase is not stored. Losing it means every licence must be reissued
under a new key with a rebuilt application, and the Manager says so before
creating one rather than after.

The raw seed exists in memory only while a key is unlocked, is used in exactly
one function, and never reaches the interface, a log, the history file or an
error message. Neither *Create key* nor *Import key* will overwrite an existing
key file, because overwriting a signing key invalidates everything issued under
it.

#### What it does

**Generate License** — product, request code (with the Machine ID shown back as
it is pasted, so a wrong code is caught before a licence is bound to a machine
that does not exist), customer name, phone, city, notes; FULL or DEMO with
7/14/15/30/custom days or an explicit date; a licence number suggested from
history and editable.

**License History** — every issue, searchable by anything a vendor would
remember. Append-only: a reissue writes a new row and a used number is reported
rather than replaced, because "we sent a 14-day demo, then a full licence in
May" is exactly the history that matters.

#### Multi-product

`products.py` is the catalogue: product id, key file, licence rules. D-Clinic is
registered and **greyed out** — it uses a different key format, and claiming
support before that exists would produce keys that silently do not work.

#### The vendor key is now embedded

`EMBEDDED_PUBLIC_KEY_B64` carries the **public** half of a keypair generated in
the Manager. Its private counterpart has never been in this repository. Proven
end to end against the real embedded key: a fresh install reads UNLICENSED, a
DEMO key activates with the vendor's 14 days, a FULL key activates with no
expiry, activation survives a restart, and a wrong-machine key, a key signed by
a different key, and a key with one character changed are all refused with the
licence already in place left untouched.

A consequence worth recording: `public_key=None` used to mean "no key" and now
means "use the embedded one". A test that relied on the old reading had to take
the embedded key away explicitly to keep asking its real question — what an
UNKEYED build does.

**Honest note on custody.** This keypair was generated here, so its private half
has passed through a message. That is acceptable for acceptance testing and not
for production: the Manager's *Create key* makes a fresh one that has never left
the vendor's machine, and the application then needs rebuilding with its public
half.

+51 tests; **993 pass**, schema v13 (no migration — none of this touches the
database).

### 14E.6 Known limitations (carried into review)

* **No vendor key is embedded yet.** The build reports *Unlicensed build* and
  runs in Demo until the owner generates their signing key with `tools/` and
  returns the public half. This is by the owner's own choice of key custody.
* **Demo expiry restricts access, not individual postings** — see §14E.4.
* **The audit chain detects tampering; it does not prevent it.** Editing,
  deleting or back-inserting an entry is caught and located. Two things are
  **not** caught, and are stated rather than implied away: an attacker who
  recomputes every hash from the altered point onward (the chain has no secret
  they lack), and a **new entry appended at the tail**, which is
  indistinguishable from genuine activity. Defeating the first needs an HMAC key
  held outside the database or an external anchor; neither fits a single offline
  PC where the owner holds every key.
* **Backup encryption uses the owner password as the passphrase.** One secret
  instead of two, and it is the one already required to restore — but a backup
  opens with the password that was current **when it was written**. After a
  password change, older backups still need the older password. There is no
  recovery path for a forgotten backup passphrase, by design: a stored copy
  would undo the encryption.
* **Recovery code**: one active code at a time, and issuing a new one replaces
  the old. If the owner loses both the password and the code, only a backup
  restore recovers the installation.
* **Machine binding cannot survive a motherboard replacement plus a fresh OS
  install plus a new disk** — that is a new machine by every trait, and needs a
  re-issued licence from the vendor.
* **Audit action names and details are stored English text**, as since Stage 05.

---

## 14. Change Log

| Date | PROJECT_MASTER version | Change |
|------|------------------------|--------|
| 2026-09-22 | 6.6 | **Zenith Soft License Manager — the vendor application (Stage 10 still NOT locked, NOT merged).** A second Windows program, built to the D-Clinic workflow the owner sent: paste a request code, pick FULL or DEMO, press one button, copy one line. It is the half that can **issue**; Zenith Business is the half that can only **check**, and that asymmetry is the security model rather than a convention. Lives in `vendor/`, never collected by the customer build, never imported by it, and asserted so by three tests plus a CI step that hunts for the executable inside the customer package. **The private key never touches this repository:** the Manager creates one at run time and writes it to the vendor's own AppData as an AES-256-GCM `.zkey` with the key derived by scrypt at n=2¹⁷ — four times the backup work factor, because a backup guards one customer's books while this guards the ability to issue licences at all. The passphrase is not stored, neither Create nor Import will overwrite an existing key, and the raw seed is used in one function and never reaches the screen, a log or the history. **Generate License** shows the Machine ID back as the code is pasted, so a mangled code is caught before a licence is bound to a machine that does not exist; **License History** is append-only and searchable, so a reissue never erases what was sent before. `products.py` makes it multi-product, with D-Clinic registered but greyed out because it uses a different key format and claiming support would ship keys that silently fail. **The vendor public key is now embedded**, so the build verifies for real: proven end to end that DEMO and FULL activate, survive a restart, and that wrong-machine, wrong-signer and altered keys are refused with the existing licence untouched. One consequence recorded: `public_key=None` used to mean "no key" and now means "the embedded one", so a test had to take the key away explicitly to keep asking what an unkeyed build does. Custody is stated honestly — this keypair was generated here, which is fine for acceptance and not for production; Create key makes one that never leaves the vendor's machine. +51 tests; **993 pass**, schema v13. See §14E.11. |
| 2026-09-21 | 6.5 | **Stage 10 — activation by copy and paste (still NOT locked, NOT merged).** The owner compared the flow with their other product and asked for its shape, and they were right: the first version made a customer save a `.zreq`, attach it, receive a `.zlic`, find it on disk and import it — four file operations for someone who only wants to start work. Activation is now **copy a code, send it, paste a key, activate**, with the file route folded away under Advanced because a long code can be mangled by an email client and a file cannot. **Nothing about the security model changed:** a Product Key is the same Ed25519-signed, machine-bound licence a `.zlic` holds, with the same signature, binding, expiry, refusals and public-key-only verification — only the packaging differs, and `parse_any_license` feeds both shapes through **one** evaluation so a second judgement routine cannot drift from the first. A `ZBR1-` request code carries the fingerprint and hashed traits (a short Machine ID could not: the traits are what let a licence survive a disk swap) plus a CRC, so a code mangled in a message is caught **before** the vendor issues a licence against a machine that does not exist. A `ZB1-` key is ~250 characters, because an Ed25519 signature is 64 bytes and cannot be shortened; the payload is packed binary rather than JSON, which ran past a thousand. Trait comparison now accepts a prefix, since a key packs each trait into four bytes — a bounded weakening of a *tolerance* check that only ever matters on a machine which already failed the 128-bit fingerprint. Vendor side gains `issue`, which takes a request code and prints a key with **the vendor choosing the DEMO length**, and records customer/phone/city to a history file that never ships. **Three defects found by reading the rendered screens:** the Dari UI reported every refusal in English, so `LicenseError` now carries a catalogue key; `ZB1-` rendered as `-ZB1` because bidi reorders a trailing hyphen, fixed with directional isolates; and a fresh install showed its instructions in red, which reads as a fault when nothing is wrong. Two behaviours were discovered rather than designed and are recorded so they are not later mistaken for bugs: a paste survives line breaks, case and a lost separator; and the final character of a key carries dead bits, so changing only those leaves the same licence — the signature covers the decoded bytes. +33 tests. See §14E.10. |
| 2026-09-21 | 6.4 | **Stage 10 — final real-Windows fixes (still NOT locked, NOT merged).** Ten issues from the owner testing the packaged build, one of them architectural: **the licence gate was in the wrong place.** Licensing was a screen under Tools, so an unlicensed installation reached login and the whole workspace and looked at its licence afterwards — a gate behind an open door. Activation is now a page in the same window as login, in front of it, with no route to the login form except a licence that evaluates FULL or DEMO, re-asked on the way through because a licence can lapse while the screen sits open. **A missing licence is no longer a free demo:** `NO_LICENSE_FILE` used to grant 30 days from a settings row, so deleting the licence granted access; there is now an `UNLICENSED` status, and a demo is a vendor-signed, machine-bound licence with its own expiry like any other. **A clock a demo cannot be cheated out of:** the installation remembers the latest moment it has ever seen and never believes an earlier one, kept in a DPAPI-sealed file, a database mirror and the licence's own signed `issued_at` as a floor, highest of the three winning — and an expiry that falls while the program is open returns it to activation within a minute instead of waiting for a restart. **The Persian-keyboard inconsistency was real and was not a keyboard conversion:** creating a backup never verified the typed text against the account despite its docstring claiming so, so a backup made under a Persian layout was locked with a string the owner never chose — which Check accepted (it *was* the passphrase) and Restore refused (it also re-authenticates). Creating a backup now verifies first and refuses otherwise. Also: the pre-restore safety copy is no longer a plain readable `.db` of the live books; `bad_passphrase` no longer reaches the screen, replaced by a message naming all three causes in EN and Dari; "Expires: Never" with no licence became "—"; every screen reads one evaluated status and now words it from the catalogue, so Dari stops reporting its licence in English; activation requests carry the customer's real business name or none at all; and recovery, built in Stage 10 behind no button, is now on the login screen and in My Account. **Honest limit recorded:** anti-rollback raises the cost of a clock change, it does not prevent one — a local Administrator can delete both stores, and only the signed floor survives that. +53 tests; **907 pass**, schema v13 (no migration). Acceptance items B–H sit behind the gate and need the owner's vendor key before they can be run on the real build. See §14E.9. |
| 2026-09-20 | 6.3 | **Stage 10 — lockout polish (still NOT locked, NOT merged).** The owner asked what the lockout actually does before asking for anything to change, and reading it out on a real on-disk database found a defect the code review had missed: **waiting out the fifteen minutes did not give the five attempts back.** Clearing a lock moved `is_locked` and `locked_until` but left `failed_login_attempts` at the threshold, so the next single wrong password re-locked the account for another full quarter of an hour — the owner served the wait and got one try, not five, and each further typo cost another fifteen minutes, which is indistinguishable from an account that has stopped working. Every path that lifts a lock (expiry at the login screen, expiry during sensitive-action re-authentication, and a recovery code) now goes through one `UserRepository.clear_lockout` that clears the flags **and** the count, and writes an `auth.lockout_expired` audit entry so a lock disappearing is recorded rather than silent. The login screen now counts the wait down to the second — *"Account locked. Try again in 12m 34s."* — in EN and Dari, re-rendered on a mid-lock language switch, surviving a repeated Sign In press, and ending in the neutral colour with "the lock has ended" instead of going blank. Everything else is deliberately unchanged and pinned by tests: fifth wrong password, fifteen minutes, attempts during the lock do not extend it, the correct password is still refused while it runs, it survives app and PC restart, a successful login or recovery clears it, and an unknown username locks nothing. **Expiry is judged against the PC's own clock** — someone at the machine can end a lock early by moving the Windows clock forward, recorded as a limitation rather than claimed away. +30 tests; **853 pass**, schema v13 (no migration). See §14E.8. |
| 2026-09-19 | 6.2 | **Stage 10 — security hardening pass (still NOT locked, NOT merged).** Seven owner-requested items. **Licence state** had two liars: the login screen printed the development-build text *unconditionally*, so an activated install said it was unlicensed at every sign-in, and the boot log reported Stage 01's dev provider; all four readers now call one source. **Backups** were plain SQLite — readable by anyone holding the USB stick and restorable after an edit — and are now AES-256-GCM `.zbak` containers with a scrypt-derived key, an authenticated-but-readable header so backups can still be listed without the passphrase, and **legacy plain backups still restore**. **The home-grown Ed25519 is deleted**: verification delegates to `cryptography` and fails closed, while the vendor tool keeps a stdlib implementation for offline use, proven byte-identical to the reference. **Migration 0013** adds an audit hash chain that locates any edited, deleted or back-inserted entry — and a **gap in it was found and closed during the pass**: verification skipped unsealed rows, so a forgery inserted between sealed entries chained around it and passed. **A package auditor** scans the assembled Windows build — including inside the frozen exe — for private keys, signing tools, generators, bypasses, backdoors and default passwords, and fails the build on any hit. Machine traits confirmed to expose no raw hardware identifier. **The auditor's own first run failed the build** on three false positives — a vendored crypto library naming its own signing classes and Qt's PEM parser holding a header literal — which is exactly why it scans the real package; it now separates key material (fails, and matches the path as well as the content) from vendored capability (reported), with eleven trials pinning both halves. Its **second** run then failed on the opposite problem — it could not find our own public-key module, because PyInstaller zlib-compresses the Python archive, so a byte scan can prove what is ABSENT from a package but never that the licence path is present and working. That half is now proved by asking the binary: `ZenithBusiness.exe --selftest` reports its crypto backend, licence state and audit-chain status, and CI fails the build unless the frozen exe reports a working state. Its **third** run failed too: the shipped exe is built windowed, where `sys.stdout` is `None` and `print` raises, so the report went nowhere and a passing self-test looked like a failure; it now writes to a file, which is the only thing CI can read from a windowed binary. +25 tests; **823 pass**, schema v13. See §14E.7. |
| 2026-09-18 | 6.1 | **Stage 10 — Single-PC Security, Backup & Customer-Side Licensing implemented (READY FOR OWNER REVIEW; NOT locked, NOT merged).** Scoped against the code first: a probe found **35 required capabilities already present** and 22 missing, so Stage 10 **extends** Stage 02's hashing, lockout, audit and backup rather than rebuilding them, and **no locked stage was modified**. **Licensing** is Ed25519 from RFC 8032 in pure stdlib — a native crypto dependency was rejected because the project ships PyQt6 and nothing else and a licence check is the wrong place to add a bundled binary wheel. The application **can verify and cannot sign**: no private key in application code, no shipped module that accepts one, enforced by a repository-wide scan test. **The verifier was cross-checked against a reference and that immediately paid — the first implementation rejected EVERY genuine signature** (a dropped `(u·v⁷)` factor), and every negative test still passed, because a verifier that rejects everything rejects forgeries too. **Machine binding** scores five weighted traits: weak traits total 3 so the threshold of 5 is unreachable without a strong one, which is what stops a look-alike PC while still surviving a disk swap, a NIC change, a rename or an OS reinstall. **Restore** now takes a safety backup, swaps atomically with `os.replace`, verifies the restored file and rolls back if it fails — proven by simulating a disk-full failure mid-swap, after which the live database is still present, healthy and complete. **Demo** restricts access and never data; it is enforced at the shell because gating individual postings would require touching locked services or the frozen `AuthorizationService.require` contract. Adds re-authentication behind every sensitive action (rate-limited like the login screen), a single-use recovery code for the only owner account, audited settings, an audit viewer, and a live-database integrity check alongside — not inside — Stage 01's locked `check_health`. Three screens in EN/Dari with RTL. **One defect found by reading the rendered screen:** an activated install still showed *"Development build (unlicensed)"* in the status bar. Full vendor round trip verified end to end, with the tool's pure-Python signatures byte-identical to the reference. +101 tests; **798 pass**. See §14E. |
| 2026-09-18 | 6.0 | **🔒 Stage 09 — Accounting Reports & Financial Statements LOCKED (owner-approved).** Manually accepted on the Stage 09 Windows test build; locked at `b8a2cfc`, the same commit that was tested — **697 tests pass**, schema **v12**, 60 test files. Frozen contracts are in §8 and the lock record with the accepted state is §14D.7. The frozen set: **one source, six readings** — every statement reads `financial_entry_lines` directly, so there is no reporting store to drift; the Trial Balance always balances, with a liability closing negative because that is a credit balance; P&L as Net Sales − COGS = Gross Profit, − Operating Expenses = Net Profit, with net sales reconciled against rather than replacing the locked Sales Reporting engine; **Assets = Liabilities + Equity**, which holds because equity carries the period result in the absence of a year close; the General Ledger reconciling with the Trial Balance account by account, with a running balance and date/account filtering; Cash & Bank reconciling with both; receivables and payables reconciling with the party ledgers, with ageing buckets that add back to the balance under **two settlement rules** — a return, correction or void credits **the document it names**, a receipt or payment clears the **oldest debt first**; the ageing totals row on screen and in print, held outside the data rows; **COGS posted exactly once** under a database UNIQUE index, taken from the Stage 08 movement cost and never from the selling price, dated by the movement, reversing correctly on Return, Correction and Void; GL descriptions naming **business documents** (`COGS — SALE-000009`) and never an internal movement id; From/To plus financial year with **no period or year close**; and A4-only EN/Dari/RTL printing with the customer's business identity and Dari pinned to bundled Vazirmatn, on a **subclass** of the locked Stage 08 sheet. Migrations 0011 and 0012 (v12). **Three defects found by the owner's verification rounds and fixed before the lock:** ageing applied every credit oldest-first, so a voided invoice sat in the 1–30 bucket while an untouched April invoice looked part-paid; the ledger exposed `Cost of goods sold — movement 14`; and the printed title overflowed onto the business name, reading *"Kabul Traders Ltd ods Sold"* — found by reading the rendered sheet, since the title string itself was correct. **No locked stage was modified and §33 was never invoked during Stage 09.** Known limitations carried into the lock: no period/year close, COGS posted on report read rather than inside the sale, no credit terms in ageing, English stored descriptions and seeded account names, single-currency statements, and no cash-flow or comparative columns. PR #4 still not merged; Stage 10 not started. |
| 2026-09-17 | 5.3 | **Stage 09 — report polish: ageing totals, ledger naming, ledger header (still NOT locked, NOT merged).** Three owner-requested fixes. **(1) Ageing totals row** — Receivables and Payables now show a bold Current / 1–30 / 31–60 / 61–90 / 90+ / Balance row on screen and on the printed sheet, under the columns it totals; the row is kept OUT of `rows`, the Stage 08 lesson that folding totals into a table reported a two-item valuation as "4 item(s)". Statements whose totals are not per-column are unchanged. **(2) General Ledger descriptions name the document** — `Cost of goods sold — movement 14` exposed an internal `inventory_movements` id; lines now read `COGS — SALE-000009`, `COGS Reversal — SRET-000001`, `COGS Correction — SALE-000009`, `COGS Void — SALE-000009`, and **migration 0012 (schema v12)** rewrites entries already posted, data-only, re-runnable, leaving an operator-edited description alone. **(3) The printed ledger names its account** — `General Ledger — 5000 Cost of Goods Sold`. **A fourth defect was found while checking the printed sheet for (3):** the unbounded, non-wrapping title overflowed left and printed OVER the business name — the header read *"Kabul Traders Ltd ods Sold"*, hiding both the identity and the account the fix had just added. The Stage 09 sheet PINS the title width (a capped word-wrapping QLabel still reports a narrow size hint and stayed squeezed into five lines) and keeps the identity lines together; the printed ageing total, which appeared twice, is no longer repeated in the totals block. All Stage 09 code — the sheet is a **subclass** of the LOCKED Stage 08 document, which is untouched and renders as before. +17 tests; **697 pass**. See §14D.5c. |
| 2026-09-17 | 5.2 | **Stage 09 — second verification round on the six reports the owner named (still NOT locked, NOT merged).** General Ledger, Cash & Bank, Receivables ageing, Payables ageing, COGS reversal after a Sales Return, and COGS after a Sale Correction / Void, each on a real on-disk database built so that **every ageing bucket is genuinely populated** — the earlier scenario put everything in "Current" and so could not test ageing at all. **One defect found and fixed:** ageing applied *every* credit oldest-debt-first, which is right for a receipt or payment (they name no invoice) but wrong for a return, correction or void, which all name the document they belong to. The party balance was right and the ageing was not — a **voided** invoice still sat in the 1–30 bucket (3,480 instead of 2,220) while an untouched April invoice looked part-paid (2,740 instead of 4,000). `party_documents` now returns a `charge_key` per row, resolving `SALES_RETURN` / `PURCHASE_RETURN` to their parent document, and `_age_party` credits the named document while keeping oldest-first strictly for money that identifies nothing; excess spills to the oldest-first pool so **the buckets still add back to the party balance**. Stage 09 code only — **no locked stage touched, §33 not applicable**. COGS proven to reverse at **cost** and never at selling price (returning 4 of 10 at cost 50.00 reverses exactly 200.00, not 360.00), a correction leaves exactly the corrected quantity charged, and a void returns COGS and Inventory to their pre-sale figures to the cent. +5 tests; **675 pass**. Two display gaps recorded as limitations: the ageing reports show no per-bucket totals row, and GL descriptions cite an internal movement id. See §14D.5a / §14D.5b. |
| 2026-09-17 | 5.1 | **Stage 09 — Accounting Reports & Financial Statements implemented (READY FOR OWNER REVIEW; NOT locked, NOT merged).** Six statements over the existing double-entry ledger — Trial Balance, Profit & Loss, Balance Sheet, General Ledger, Cash & Bank and Receivables/Payables with ageing — plus the **COGS accounting integration** Stage 08 left open. The baseline was reproduced first: the ledger balanced but Inventory read 1,000 against stock genuinely worth 375, overstated by exactly the 625 of cost nothing ever posted. `CogsPostingService` charges `Dr COGS / Cr Inventory` **from the Stage 08 movement cost**, never recomputed and never from the selling price; each entry is dated by the movement's own date and every report syncs before reading, so no locked Stage 05/07/08 code had to change and the §33 procedure was not needed. **Exactly-once is a unique index** (migration 0011, schema v11) on `(source_type='COGS', source_id=<movement id>)`, and a test asserts the database itself refuses a duplicate; returns, corrections and voids reverse correctly because each posts its own costed movement. Equity carries the period result so **A = L + E** holds without a year close (out of scope). Two UI defects found by reading the screens: the status line guessed at formatting and printed "Balanced: **0.00**" instead of "Yes" — `D()` returns zero for unparseable text rather than raising — and Qt ate the `&` in "Profit & Loss" as a mnemonic. **The owner's scenario reconciles on a real on-disk database**: net sales 1,000 − COGS 625 = gross 375, − expenses 100 = **net profit 275**; trial balance Dr 2,725 == Cr 2,725; balance sheet 1,275 == 1,275; GL == TB on every account; receivable and payable == the party ledgers; COGS journal == Stage 08; and **GL Inventory 375 == Stage 08 valuation 375** where it had been 1,000. +26 tests. See §14D. |
| 2026-09-17 | 5.0 | **🔒 Stage 08 — Costing & Inventory Valuation LOCKED (owner-approved).** Manually accepted on the Stage 08 Windows test build; locked at `b0fcd2a`, the same commit that was tested — **644 tests pass**, schema **v10**, 58 test files. Frozen contracts are in §8 and the lock record with the accepted state is §14C.10. The frozen set: **weighted average per (item, warehouse)** as the one costing method; cost captured when a movement happens and never re-derived, because a purchase correction rewrites its line in place; the single choke point at `InventoryRepository.add_movement`, so no locked service was modified to obtain costing; the per-movement valuation rules (purchase at the price paid, sale at the current average, reversals at the original cost, purchase returns at what was paid, sale returns at the cost they left at, transfer in at the exact value that left); **COGS selected by `reference_type`** so a corrected invoice is not counted twice; gross profit as net sales − COGS with net sales read from the locked Sales Reporting engine; money-precision `total_cost` so every subtotal adds up; migration 0010 with its idempotent backfill and replay boundary; and the three A4 EN/Dari report contracts including Dari pinned to bundled Vazirmatn, verified on windows-latest before each build. Also repairs three change-log rows that had been appended with a literal `\\n` and rendered as one run-on line. PR #4 still not merged; Stage 09 not started. |
| 2026-09-15 | 4.3 | **Stage 08 — Gross Profit item count removed + Windows font verification (still NOT locked, NOT merged).** The Gross Profit sheet counted its own calculation steps as stock ("5 item(s)" / "۵ قلم"); net sales and COGS are not items, so the count is omitted from that report entirely while Inventory Valuation and COGS keep theirs. The Windows build workflow now runs the Dari font tests **on windows-latest before freezing the exe**: the silent Segoe UI / Tahoma substitution this guards against cannot occur on the Linux dev machine, where those faces do not exist, so it is verified on the platform where it can actually fail and a regression fails the build instead of shipping. +7 tests; **644 pass**. See §14C.9. |
| 2026-09-15 | 4.2 | **Stage 08 — three printed-report defects fixed (still NOT locked, NOT merged).** Owner-reported, each reproduced before being touched. **(1) Business identity:** first-run setup stores the business name as a *setting* while the Company screen writes the `companies` row, and the shared `_company_info` read only the row — so a customer who never opened that screen saw the PRODUCT name *"Zenith Business"* on their own report. It now falls back through the setup name, with the product name as the last resort it was meant to be; address, phone, email and **tax id** print when configured. Shared with the locked Stage 05/06/07 reports, and reported as a confirmed bug fix against those stages' own stated contract rather than a behaviour change. **(2) Item count:** a two-item valuation said "4 item(s)" because the totals had been folded in as table rows; Stage 08 now has its own print document where the table holds items and the totals are a block beneath it — the locked Stage 06 document is untouched. **(3) Dari font:** the shared stack lists system faces after Vazirmatn, so on Windows Qt could substitute Segoe UI or Tahoma for Persian text; this never reproduced on Linux, where those faces do not exist, which is why it reached the owner. Dari is now pinned to the bundled **Vazirmatn** with no fallback across title, headers, table, totals and footer, in the stylesheet and on the widget font. **English is unchanged** and RTL is unaffected. +13 tests; **637 pass**. See §14C.9. |
| 2026-09-15 | 4.1 | **Stage 08 — Costing & Inventory Valuation implemented (READY FOR OWNER REVIEW; NOT locked, NOT merged).** The constitution's weighted-average costing requirement (§4.7 / Spec §11), unbuilt until now. Migration **0010** (schema v10) adds `unit_cost` / `total_cost` to `inventory_movements` and **back-fills an existing database** through the same engine, so the ledger row that says how much stock moved now also says what it was worth — one source of truth, not a second one. The engine lives at the single choke point every posting path already funnels through (`InventoryRepository.add_movement`), so **no locked Stage 05/06/07 service changed**: purchases cost at the price paid, sales at the current average (that is COGS), reversals at the cost the original went at, purchase returns at what was paid, sale returns at the cost they left at, and a transfer in at the EXACT value that left — so a transfer never changes what the company is worth. Cost is captured when a movement happens because it **cannot** be re-derived later: a purchase correction rewrites its line in place, so the original price is genuinely gone. Three reports (Inventory Valuation, COGS, Gross Profit = net sales − COGS) in EN/Dari on the existing A4 sheet; net sales comes from the locked Sales Reporting engine rather than a second definition. **Two engine bugs the tests caught:** COGS double-counted a corrected invoice (selecting by `movement_type` instead of `reference_type`) — on real data that moved COGS from 976.67 to 426.67 and gross profit from −376.67 to +173.33 — and the backfill averaged a movement against itself. The owner's scenario reconciles on a real on-disk database at every step across purchases, sale, sales return, purchase return, sale correction, purchase correction, adjustment and transfer: **qty 20, average 110, value 2,200; sell 5 → net sales 750, COGS 550, gross profit 200, remaining 15 @ 1,650.** +24 tests. Also corrects the §7 status row, which still showed Stage 07 as awaiting review after it was locked. No P&L or balance sheet (out of scope). See §14C. |
| 2026-09-11 | 4.0 | **🔒 Stage 07 — Purchases Parity / Purchase & Supplier Management LOCKED (owner-approved).** Manually accepted on the Stage 07 Windows test build (`5a8ea99`); locked at `c10dfd4`, **600 tests pass**, schema **v9**, 56 test files. Frozen contracts are in §8 and the lock record with the accepted state is §14B.12. The frozen set: `PurchaseDocumentService.net_view` as the single "what is this bill worth now" read that the list, the reopened bill, the print, the supplier balance and the reports all consume; `correct_purchase` amending the ORIGINAL bill in place with surviving line ids and a difference-only journal, `void_purchase` blocked while a return exists, and a return never rewriting the bill; the Cash / Credit / **Partial** payment model with a later payment going only through the Supplier Payment module; the refusal to post an unpaid bill to an unregistered supplier; migration 0009; **Suppliers as a view of the shared people** — no supplier table, no second form, no duplicated balance; `total − paid == balance` on both ledgers; the consistency chain Purchase List = Invoice View = Print = Return = Supplier Balance = Inventory = Stock Movement; and derived-at-render line totals and return notes. **One defect found during the lock run and fixed before freezing:** a row-action button's minimum width was computed by hand and landed a pixel short under a different font, which is enough for Qt to clip the label away — the empty-box failure originally reported. Width now comes from the button's own polished size hint, the action column from the assembled widget's hint plus the table's per-cell overhead, and the fit re-runs on `showEvent` because rows are built before the page has geometry. Verified on the real main window in EN and Dari across Suppliers, Persons and Items. PR #4 still not merged; Stage 08 not started. |
| 2026-09-06 | 3.2 | **Stage 07 — final approval preparation (still NOT locked, NOT merged).** Documentation and regression cover only; **no behaviour changed**. The party-ledger totals fix is now recorded as **§33 amendment 01** to LOCKED Stage 05 (§13K.2) in the five-part form the procedure requires — change, necessity, affected components, migration risk, alternatives — with the owner's approval to keep it (*"Keep the confirmed customer_totals fix. Do NOT revert it."*) and the note that it is the only change to locked Stage 05 behaviour since the lock. New `tests/test_locked_stage05_ledger_totals.py` (**17 tests**) proves the identity itself — `total − paid == balance` — rather than remembered example numbers, for **both** ledgers across an empty account, credit documents, money settled on the document, separate Receipt/Payment documents, partial returns, full returns, a mixed history, a dual-role party whose two sides must not borrow from each other, the reported 1,000/−400/200 case, and the figures the Suppliers screen actually renders. The English ledger **Description** text is left as it is by owner decision and documented as a future localization item (§14B.11): it is stored at posting time, is cosmetic, and its eventual fix touches locked Stage 04/05 posting. **600 tests pass.** No other Stage 05 or Stage 06 change. |
| 2026-09-05 | 3.1 | **Stage 07 — dedicated Suppliers screen (still NOT locked, NOT merged).** The §14B.9 deviation is closed the way the owner directed: Persons stays the shared master data structure internally, and the UI gains a real **Suppliers** screen. `SuppliersPage` subclasses `PersonsPage` as pure configuration — `PersonsPage` was refactored into overridable hooks so this is a second *presentation*, not a second page, a second table or a second supplier record. It shows Supplier Code, Name, Business Name, Phone, Current Balance, Total Purchases, Total Paid, Remaining Payable, Status and View Account, with Search, New Supplier (the same person form, Supplier pre-ticked), Edit and Open Supplier Ledger — every figure read from `party_ledger.supplier_ledger(...)`, the same call the ledger screen makes, so no balance is duplicated. Wiring it up exposed a **confirmed reconciliation bug**: `supplier_totals` and `customer_totals` counted documents gross of returns and ignored the amount paid on the document itself, so a supplier read Purchases 1,000 − Paid 200 against a Payable of 400. Both now derive so **total − paid == balance** always holds — reported under §33 because it corrects a figure shown by the Stage 05-locked customer ledger summary. Two shared-table rendering defects fixed, each reproduced by measuring the live widget: a row-action button was 42px tall in a 26px cell (a stylesheet `min-height` overrides `setFixedHeight`, so the height now comes from the sheet), and `RowActions` applied an unscoped `background: transparent` that also stripped its children's fill, leaving white text on a white row — the reason **View Account rendered as an empty box**. **583 tests pass** (+2). EN and Dari verified inside the real main window on an on-disk database, so RTL is genuinely exercised; the Suppliers list and the ledger behind View Account show the same 1,100 / 400 / 700. Stages 05 and 06 behaviour otherwise unchanged. See §14B.10. |
| 2026-09-04 | 3.0 | **Stage 07 — Purchases Parity implemented (READY FOR OWNER REVIEW; NOT locked, NOT merged).** Purchases now carry the contracts the sales side earned across three owner rounds. Seven gaps recorded in §14B.0 were each reproduced on a real database first, then fixed: a **credit purchase from an unregistered supplier** was accepted and posted an anonymous payable no ledger could show (now refused; a fully paid cash purchase from an unregistered supplier stays allowed); the **Purchase List** read 1000 while the payable read 600 after a 400 return (now Billed / Returned / Net Total / Paid / Remaining, all `Decimal`-summed); the **printed bill ignored returns** (now nets quantities, and says so when the whole bill went back); a bill could **not be reopened, corrected or voided** (`correct_purchase` amends the SAME bill in place with surviving line ids, compensating movements, a difference-only journal and an audited diff; `void_purchase` reverses stock/ledger/payable and is blocked while a return exists); purchase returns saved **no readable note**; the purchase invoice had **no payment selector** (Cash / Credit / **Partial** per §14B.7, Paid never negative or above the total, Remaining live); and there was **no `purchases.correct` permission**. Migration **0009** (schema v9) adds that permission with grants, `purchases.corrected_from_id` and a returns index. Reopening a bill mirrors the invoice — net position, read-only **Returned Items**, Previous Balance excluding the bill, the recorded payment type — and saving folds the returned quantities back so history is preserved. Two labelling defects found in screenshot review: the purchase chip showed the payable under a "Supplier Ref." label (now **Supplier Balance**) and the printed bill said "Bill To / Customer Code" for a supplier (additive `InvoiceData.party_kind` → **Bill From / Supplier**; the sales default is unchanged). The Persons list gained a ledger-derived **Balance** column. A later **Supplier Payment** leaves the bill untouched — no duplicate entry. **568 tests pass** (+30); the mandatory workflow (buy 1000 credit → return 4 → correct to 8 → pay 200) reconciles across Purchase List, invoice view, print, purchase return, supplier balance, inventory and stock movement, with one bill, its original number, the return intact and the ledger balanced. Stages 05 and 06 unchanged. See §14B. |
| 2026-09-04 | 2.9 | **Stage 05 — Receipts, Payments & Expenses (+ Sales Reporting) declared LOCKED (owner-approved); Stage 07 scope agreed.** Formalises the lock that the Stage 06 brief had already asserted in practice. Documentation only — **no Stage 05 behaviour changed**. The locked state is Stage 05 **as it stands today**, including the corrections the owner requested during the Stage 06 verification rounds (in-place `correct_sale`, the derived `net_view`, the explicit Cash/Credit selector), which **supersede** the corresponding descriptions in §13M and §13O; those sections are retained as the historical build record, not as the contract. Frozen in §8: migrations 0005–0007; the atomic Receipt / Payment / Expense posting with its fixed ledger directions and ledger-derived, non-editable balances; walk-in snapshot with no anonymous receivable; `void_sale`; **in-place `correct_sale`**; a return never rewriting the sale, with `net_view` as the single current-position read; the explicit Cash/Credit payment choice; the Sales Reporting engine (Gross/Paid/Credit/Returns/Net, partial-payment split, later receipts excluded, corrections counted once); party ledgers; the money entry/list screens and A4/A5 vouchers with the Sales Report at A4 only; and 12 service-enforced permissions with full audit. Known limitations carried into the lock: POSTED-only documents (no DRAFT), GL in document currency, English seeded account names, and the RTL `SearchSelector` phone-bidi cosmetic issue. **Stage 07 agreed as Purchases Parity / Purchase & Supplier Management** (§14B) — planning only, no implementation; Accounting Reports and Costing explicitly excluded. PR #4 still not merged. |
| 2026-09-04 | 2.8 | **Stage 06 — Inventory & Stock Management declared LOCKED (owner-approved).** Owner accepted Stage 06 after manual acceptance testing of the Windows test build plus three verification rounds (§14A.1 returns visible on the original sale, §14A.2 the full return, §14A.3 reopening a sale on its current state). Accepted commit `a4017ec`; **538 tests pass**; schema **v8**; final Windows build published from that commit. Stage 06 public contracts frozen in §8: stock as a single signed movement ledger with no stored stock figure and nine movement types; migration 0008 (`inventory_movements.notes` + 3 indexes); permanent Opening/Current separation; the `InventoryReadRepository` / `InventoryService` / `InventoryReportService` reads; mandatory adjustment reason, transfer conservation and over-transfer block, sale validation against current warehouse stock; and the sales-integration contracts — `net_view` as the one "what is this invoice worth now" answer that the Sales List, the reopened invoice, the print, the customer balance and the reports all read, in-place `correct_sale`, `returned_items`, `balance_before_sale`, the readable return note and `InvoiceData.note_key`. A5 is never offered for inventory reports. **PR #4 deliberately NOT merged.** Stage 07 not started. Stage 05 still carries no formal lock record — recorded as an open item in §7. |
| 2026-09-04 | 2.7 | **Owner verification round 3 — reopening a sale shows its CURRENT state (Stage 06 still READY FOR OWNER REVIEW; not locked, not merged).** The Sales List, print and reports already showed the net result after a return, but **reopening the saved sale still listed the returned item as an active payable line at the original Grand Total** — the invoice screen was the last surface reading the raw stored lines. It now loads from the same `net_view` as everything else: a partly returned line loads at its net quantity, a fully returned line is not an active line at all, and Grand Total is the net total (Rice 1980 + Sugar 1750 = 3730 with Rice fully returned reopens as Sugar alone at **1750**). The returned goods show read-only under **Returned Items / اقلام برگشتی** with item, qty, amount and return document; the panel is absent when there are no returns. **History is never rewritten**: returned quantities are folded back in on save, so correcting Sugar 1 → 2 stores Sugar 2 **and** Rice 1 (gross 5480, net 3500, receivable 3500, return still valid, one invoice, original number). Two related fixes in the same screen — **Previous Balance** double-counted the invoice being corrected (it showed the full receivable, which already contains this invoice, then added its remaining again); it is now the balance *before* this invoice via the new `balance_before_sale`, and the header chip is relabelled **Customer Balance / بیلانس مشتری** so one label never means two numbers. **Amount Paid** was re-derived from the reduced total on reopen, silently claiming back cash the customer still holds; a reopened invoice now shows what was actually paid, and Remaining goes negative (refund owed) exactly as the Sales List and receivable do. The save message no longer claims "new invoice". New reads: `SalesReturnRepository.returned_lines_for_sale`, `SalesDocumentService.returned_items` / `balance_before_sale`, `net_view["net_remaining"]`. No migration; inventory posting, returns, accounting and numbering untouched. Verified on a real on-disk DB in EN + Dari. **538 tests pass** (+15 in `tests/test_invoice_view_after_return.py`). See §14A.3. |
| 2026-08-31 | 2.6 | **Owner verification round 2 — the FULL return (Stage 06 still READY FOR OWNER REVIEW; not locked, not merged).** Sold Rice 5 × 100 = 500 twice and returned **all five** on each, posting one through the real **English** Return screen and one through the real **Dari** screen on the same database. Verified: warehouse stock 0 → **10**; Sales List Returned **500.00** / Net **0.00** / Remaining **0.00** on both rows; customer receivable **0.00**; **no second SALE invoice** (2 sold, 2 listed, one SALE movement each); the note visible in the Returns list in the language it was posted in ("Rice — Qty 5 returned." / "برنج به تعداد 5 دانه برگشت شد."); Sales Report 1000 / 1000 / **0**; nothing further returnable and a further return refused; ledger balanced. **Defect found and fixed:** a fully-returned invoice printed as a **blank form** — the netted item table is legitimately empty, so the A4 sheet showed an empty table and 0.00 totals with no explanation. Added an optional document-level note to the printed invoice (`InvoiceData.note_key`, additive with an empty default, rendered above the standard terms): "All items on this invoice were returned. Nothing remains payable." / "تمام اقلام این بل برگشت داده شده است. مبلغی قابل پرداخت باقی نمانده." Stored as an i18n **key** so it follows the preview's EN/Dari toggle rather than freezing the language at build time. Partially-returned and untouched invoices carry no note. No migration; no accounting/inventory/numbering change. **523 tests pass** (+12). See §14A.2. |
| 2026-08-31 | 2.5 | **Owner verification round — a sales return must update the ORIGINAL sale visibly (Stage 06 still READY FOR OWNER REVIEW; not locked, not merged).** Verified the owner's example (Rice 5 × 100 = 500, return 1) on a real on-disk database through the real screens: stock 5 → **6**; still **one** invoice `SALE-000001` (POSTED, never rewritten); Sales List Invoiced 500 / Returned **100** / Net **400**; invoice line sold 5 / returned **1** / net **4** = 400; printed invoice **Rice 4 → 400**; Sales Report Gross 500 / Returns **100** / Net **400**; customer receivable **400**; movements gain one `SALE_RETURN +1` with no second `SALE`. No migration; no accounting/numbering/inventory-posting change. Three gaps the verification exposed were fixed: (1) the Sales List **Remaining** column still showed the invoiced 500 after a return — `list()` now derives `net_remaining` = net total − paid (correctly negative = refund owed on a paid invoice, matching the receivable); (2) the human-readable note was stored but shown nowhere — the Sales Return list gained a **Note** column (stretch) beside the source invoice; (3) the **Dari note used the English item name** — it now uses the item's Dari (alternate) name: "برنج به تعداد 1 دانه برگشت شد." This behaviour had **no regression tests**; added 16 in `tests/test_return_reflects_on_invoice.py`. **511 tests pass** (+16). Windows test build **renamed Stage 05 → Stage 06**: the workflow reads a single `env.STAGE`, publishes tag `stage06-test-build` + `ZenithBusiness-Stage06-TestBuild-win64.zip`, and retires the old `stage05-test-build` release; launcher/README/seed headers updated. See §14A.1. |
| 2026-08-24 | 2.4 | **Stage 06 — Inventory & Stock Management implemented (READY FOR OWNER REVIEW; not locked, not merged).** Stock stays a single signed movement ledger — every figure on every screen is the `Decimal` sum of `inventory_movements`, so nothing can disagree. Migration **0008** (schema v8, forward/idempotent): `inventory_movements.notes` + three reporting indexes; no new permission. New `InventoryReadRepository` and Stage 06 service reads — `movement_history` (date/item/warehouse/type/in/out/**source document number**/user/note), `stock_overview` (opening vs current, unit, warehouses, minimum, low flag), `stock_by_warehouse`, `low_stock`. `adjust` now **requires a reason**, stores it on the movement and cannot remove more than a warehouse holds; `transfer`/`record_opening` carry notes. New `InventoryReportService`: Current Stock, Opening vs Current, Stock by Warehouse, Item Movement (running balance), Low Stock. **Integration fix to locked Stage 05** (the one exception, required by the mandatory workflow): `correct_sale` deleted+reinserted lines, so a return's `sale_line_id` (ON DELETE RESTRICT) forced a blanket block on correcting a returned invoice; correction now **updates surviving lines in place**, keeping their ids, and refuses only removing a returned item or correcting below what came back. New UI under Item Reports — Inventory, Stock Adjustment, Warehouse Transfer, Stock Movement history, Inventory Reports with **A4-only** print on the customer's business identity — EN + Dari RTL; the product list gained Unit / Opening / Current / Warehouse / Stock Status. **495 tests pass** (+28). The mandatory workflow (opening 100 → +20 → −10 → +2 → correct to 5 → +3 → transfer 10) was run on a real on-disk DB through the real screens and reconciled across Product List, Inventory, Stock Movement, Sales, Sales Return and all five reports, with the ledger balanced. Two self-found UI defects fixed (clipped Low-Stock chip; printed report headers in the wrong language). See §14A. |
| 2026-08-21 | 2.3 | **Stage 05 final — Sales Reporting system + Sales-Return lookup fix + correction audit (Stage 05 still READY FOR OWNER REVIEW; not locked, not merged).** Additive; **no** accounting/inventory/ledger/numbering/auth/RBAC/licensing change and **no** migration (schema stays **v7**); reads only the authoritative `sales`/`sales_returns` tables. **P1** — the Sales Return page now loads a persisted invoice by a **unique partial number** (e.g. `2` → `SALE-000002`), flags an ambiguous fragment, and still rejects a nonexistent one (was: exact-match only → "not found"). **P2/P3** — confirmed `correct_sale` (void-and-replace) does **not** duplicate the invoice or double-count (VOID original excluded, replacement counts once); the `sales.correct` audit note now carries a **human-readable line diff** ("Rice qty 5 → 3; Sugar removed") plus old→new totals and reason. **P6** — new **Sales Reporting** engine (`repositories/reports.py` + `services/sales_reports.py`): **Gross/Paid/Credit/Returns/Net** for Today/Week/Month/Year/**Custom** + daily/monthly/yearly breakdowns and per-invoice detail; **partial payments split** paid vs credit, **later receipts excluded**, **corrected invoices counted once**, **Gross/Returns distinguishable** (Net = Gross − Returns); filters for date range/warehouse/customer/payment-status/registered-walk-in; `Decimal` sums. New **Sales Report screen** (`ui/documents/sales_report_page.py`) with presets, custom range, filters, five summary tiles and Transactions/Daily/Monthly views under **Account Reports** (EN + Dari RTL), and a **printable report** (`ui/print/sales_report_document.py` + preview) using the **customer's** business identity (logo/name/address/phone), never the developer identity. Per owner decision the Sales Report prints **A4 only** (a nine-column report is unreadable on A5) — the report preview exposes A4 exclusively (EN + Dari); A5 stays available for invoices/receipts/vouchers. **431 tests pass** (+34). Real on-disk E2E reconciles by hand (Gross 3000 / Paid 2000 / Credit 1000 / Returns 300 / Net 2700; stock 481/490; ledger balanced). Self-inspected EN/Dari report + A4 EN/Dari print + return-lookup screenshots. See §13O. |
| 2026-08-19 | 2.2 | **Owner review round 2 — Sales Invoice restructure + correction + account settings + responsive (Stage 05 still READY FOR OWNER REVIEW; not locked, not merged).** All additive (no LOCKED public contract broken; touches locked Stage 01/03/04 UI with owner authorization). Migration **0007** (schema v7, forward/idempotent): `sales.corrected_from_id` link column + `sales.correct` permission (Admin/Manager/Accountant). **Sales Invoice restructured** to the owner's reference layout — compact customer+invoice header, **dominant Expanding items table** (5 rows at 1024×768/1366×768, ~15 at 1080p, internal scroll for many lines), single entry strip with a **per-line Unit selector** + obvious **Add / Edit Line / Delete Line** (full item/qty/unit/price/discount edit before posting), and a two-row totals/payment/balance strip showing **Previous + Updated customer balance**. **Walk-in** is now a clearly-labelled bordered panel (name/phone/address). **Safe posted-invoice correction** (`SalesDocumentService.correct_sale`): atomic void-of-original + linked replacement invoice, audited old→new, **blocks when a dependent return exists** (directs to Return/Void). **Self-service Account Settings** (`UserService.change_own_password` / `change_own_username`): current-password verified, policy-enforced, hashed, id-preserving, audited; new `AccountSettingsPage` under Tools. **Contextual ledger** access — "View Account" from the Customers list and the Receipts/Payments lists opens that party's ledger directly (`ManagementPage.on_view`, `MoneyListPage.set_view_account_handler`, `PartyLedgerPage.show_party`). **Responsive** fixes: dominant table via Expanding grid card + tightened header/entry/totals so Save/Print/Close stay reachable at 1024×768/1280×720/1366×768/1080p; list stretch column has a legible minimum. **377 tests pass** (+9 in `tests/test_round2.py`). 13-step round-2 on-disk acceptance (correction reconciles stock+ledger+balance, dependency block, password/username change, restart persistence, integrity/fk clean). Self-inspected EN/Dari screenshots incl. 1024×768; fixed the items-table compression found in review. See §13M. |
| 2026-08-18 | 2.1 | **Owner manual-test hardening pass (Stage 05 still READY FOR OWNER REVIEW; not locked, not merged).** Fixed six owner-reported defects, all ADDITIVELY (no LOCKED public contract broken; the pass does touch locked Stage 01/04 UI/print files with owner authorization). Migration **0006** (schema v6, forward/idempotent): nullable `sales.walkin_name/walkin_phone/walkin_address` snapshot columns + new `parties.ledger` permission (existing `sales.void`/`purchases.void` extended to Manager/Accountant). (1) Sales Invoice refined — clearer Customer→info→items→payment→totals→save/print flow, **Registered/Walk-in** customer toggle, inline Qty/Price/Discount line editing + double-click item replace + delete. (2) **Walk-in/general customer** — name/phone/address snapshotted onto the sale (prints on the invoice) with NO permanent party record; walk-in credit rejected (no anonymous receivable). (3) Pre-post line edit/delete never moves stock; **safe posted-sale Void** (`SalesDocumentService.void_sale`) reverses inventory (ADJUSTMENT_IN)+ledger (reversing JV)+customer balance and stamps VOID, keeping the original document + returns-block guard. (4) **Customer/Supplier account ledger** — new `PartyLedgerRepository`/`PartyLedgerService` + `PartyLedgerPage` (Account Reports): running balance + Total Sales/Received/Receivable (or Purchases/Paid/Payable), derived from the authoritative ledger; dual customer+supplier identity is one party. (5) **Responsive** — reusable `vscroll` scroll-body + pinned action bar on the Stage 05 money entry pages so Save/Print/Close never fall off small windows; widened list actions column. (6) **Company logo on printed bills** — `CompanyInfo.logo_path` rendered in the invoice + voucher print headers with aspect-preserve + graceful letter-mark fallback; persists across restart. **368 tests pass** (+18). 20-step on-disk acceptance (walk-in, void reversal, ledgers, restart, re-open+print, integrity/fk clean). Self-inspected EN/Dari screenshots (sales EN/Dari/walk-in/small-window, customer+supplier ledger, sales-list Void, A4/A5 EN + A4 Dari invoices with logo); 2 self-found UI defects fixed (totals-band scroll regression; list actions clipping + stale filter label). See §13L. |
| 2026-08-17 | 2.0 | **Stage 05 — Receipts, Payments & Expenses implemented (READY FOR OWNER REVIEW; not locked, not merged).** Built additively on locked Stage 04. Migration 0005 (schema v5, forward/idempotent): `accounts.is_fund`, additive party/method/posting columns on `receipts`/`payments`/`expenses`, `expense_categories.account_id`; seeded funds (Cash/Bank/Petty Cash), expense accounts + categories, RCP/PAY/EXP sequences, 10 permissions + grants. New `money_s5` repos and `ReceiptService`/`PaymentService`/`ExpenseService` — atomic post (header + metadata + balanced ledger + party balance + numbering + audit) reusing the LOCKED double-entry ledger + party-balance derivation; FY enforcement, RBAC, Decimal-safe strict validation; balances derived (never editable). Reusable keyboard-first `MoneyEntryPage` + `MoneyListPage` on the locked design system, wired into Receipts & Payments; A4/A5 EN/Dari `VoucherPrintDocument` (receipt/payment/expense) reusing the locked print language + preview. **350 tests pass** (+37). 17-step on-disk acceptance (ledger balanced, integrity ok, restart, backup/restore). Self-inspected EN/Dari screenshots + vouchers; 2 self-found UI defects fixed. Records the confirmed future Opening-Stock inventory requirement (§13K.1). No Stage 01–04 locked contract changed. See §13K. |
| 2026-08-16 | 1.9 | **Stage 04 — Sales, Purchases & Returns declared LOCKED (owner-approved).** Owner accepted the final UI/UX, responsive behavior, EN/Dari RTL, document workflows, print preview and all Stage 04 functionality after two design-consistency/polish passes (LabeledField metadata + shared tokens; fixed a 1366×768 invoice-grid collapse via a grid min-height + a single compact totals strip; compacted the Return source row). Stage 04 public contracts (§8, §13J) frozen. **313 tests pass.** Stages 01–04 are now all locked baselines; future stages must preserve backward compatibility and must not modify Stage 04 without explicit owner authorization. Accepted known limitation: RTL phone-number bidi reordering inside the LOCKED Stage 01 `SearchSelector` dropdown (cosmetic; persistent data unaffected). No business logic / DB schema / migrations / RBAC changed during the polish passes. Stage 05 NOT STARTED. See §13J.1. |
| 2026-08-14 | 1.8 | **Stage 04 — Sales, Purchases & Returns implemented (READY FOR OWNER REVIEW; not locked, not merged).** Fresh branch from locked `main` `184ae4a`; 277-test gate re-verified first. Migration 0004 (schema v4, forward/idempotent): sales/purchase return tables, additive `sales.party_id`/`purchases.party_id`/`purchases.supplier_reference`, SRET/PRET numbering, 4 permissions + role grants. New `documents_s4` repos and `SalesDocumentService`/`PurchaseDocumentService` (atomic post across header+lines+inventory+balanced ledger+party balance+numbering+audit; **financial-year enforcement now wired**; unified `parties` via additive party links; over-return/stock guards). Real keyboard-first entry, list and from-original return screens wired into Buy & Sell; **live dashboard** (real today totals, recent sales, low stock; no mock data). Per-document print via `print_builder` reusing the locked A4/A5 engine + preview extended additively with an optional `title_key`. **311 tests pass** (+34). 22-step on-disk acceptance (ledger balanced, health ok, backup/restore) + self-inspected EN/Dari screenshots & prints. No Stage 01/02/03 locked contract changed. See §13J. |
| 2026-08-11 | 0.1 | Initial constitution captured from Master Spec v1.0 at Stage 00. No production code or schema created. Awaiting Prompt 01 — Project Foundation. |
| 2026-08-11 | 0.2 | Stage 01 (Project Foundation) implemented on feature branch: project structure, config, identity, logging, exceptions/global handler, SQLite infrastructure (connection + transactions + health, FK on, WAL), i18n/RTL-LTR, centralized UI design system, top-nav shell + branded home + status bar, security readiness (PBKDF2 passwords, licensing boundary), 60 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.3 | Stage 01B (UI/UX refinement) on the same feature branch: three-tier top chrome (navy HeaderBar + white PrimaryNav + contextual ContextBar), redesigned composed home (hero + readiness + reserved quick-access), expanded semantic design system (colors, typography hierarchy, control dims, FieldWidth XS–XL, reusable components), form + table + dialog + empty-state standards, RTL/LTR visual pass. Backend foundation unchanged. 70 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.4 | Stage 01C (premium UI redesign) on the same feature branch: denser professional layout tokens, grid-based business-form architecture, full **Sales Invoice visual prototype** as the reference design (header + dominant line grid + summary/operational + action bar with shortcut hints), StatTile/LabeledField/apply_shadow/escape_amp components, upgraded list/management screen, home depth refinement, multi-resolution (1366/1600/1920) + Dari-RTL verification. Backend unchanged. 72 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.5 | Stage 01D (rapid invoice entry UX) on the same feature branch: reusable provider-driven `SearchSelector` autocomplete architecture; keyboard-first Sales Invoice (item search → populate → qty → price → discount → next line); customer autocomplete filling balance/credit/phone; redesigned ERP/POS invoice workspace with always-visible payment area and permission-gated cost note; platform-style action icons; mock providers in `ui/mock/` (clearly non-production); Dari-RTL + 1366/1600 verification (no horizontal scroll at 1366). Backend unchanged. 80 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.6 | Stage 01E (premium color system + printed invoice) on the same feature branch: intentional semantic color tokens (accent, workspace gradient, financial/status roles) applied by meaning (strong filled Grand Total, cash/credit/stock colors, active-row marker, destructive Delete); richer Sales Invoice character (accent cards, colored indicators); and a real customer-facing **A4 printed Sales Invoice** (EN LTR + Dari RTL) driven by the same demo transaction, opened via Save & Print → in-app print preview. Backend unchanged. 84 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.7 | Stage 01F (one-screen workspace + dashboard + print reflow) on the same feature branch: Sales Invoice fits one screen at 1366×768 (non-scrolling) with fields bound to the shared transaction (screen == print, date fixed); Home replaced by a compact business **dashboard** (KPIs, quick actions, recent transactions, low stock); new **paginated print engine** supporting **A4 and A5**, content reflow (compact short invoices, multi-page long invoices with repeated headers + page numbers + totals on the last page) and **amount-in-words** (English + Dari); print preview gains an A4/A5 toggle. Backend unchanged. 88 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.8 | Stage 01G (final visual-quality & print-composition pass) on the same feature branch: printed invoice redesigned as a real document (identity block, boxed identity panel, accent Bill To, gridless item table, coherent financial summary, redesigned signatures); **A4 and A5 given genuinely different compositions**; totals collision/overflow fixed (stacked Grand Total + widened numeric columns, verified to ~13M); short invoices balanced and multi-page distribution evened out with widow/orphan control (22 items → 11+11); print preview rebuilt into a real workspace (paper, language, zoom Fit Width/Page, print); operational info compacted to a contextual strip; dashboard KPIs gain accent borders. Backend unchanged. 88 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.9 | Stage 01 refinements (header hierarchy + global typography) on the same feature branch: bundled **Vazirmatn (OFL)** Persian/Dari + Latin font with a centralized loader (`core/fonts.py`) and a single `Typography.FAMILY` token driving the whole app **and** print — Dari now renders as a polished, native UI/document; and the Sales Invoice **header hierarchy** (Customer promoted/prominent; Warehouse/Salesperson/Currency/Rate compacted and quieted) via a shared `LabeledField(compact=True)` variant, consistent in EN + Dari with one-screen 1366×768 preserved. Backend unchanged. 90 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-12 | 0.9 | Print-only legibility pass: Dari/English secondary print text darkened to a stronger secondary ink at Medium weight with tiny size nudges; amount-in-words de-italicized. Vazirmatn, A4/A5 layouts and pagination unchanged; verified single-page with no wrapping/clipping/collision. 90 passing tests. |
| 2026-08-12 | 1.0 | **Stage 01 — Project Foundation declared LOCKED (owner-approved).** Public contracts frozen and recorded in §8 (core, database infrastructure, security, UI design system, search-selector architecture, print engine, and locked principles). No business tables. Stage 02 — Database is now the next authorized step. |
| 2026-08-14 | 1.7 | **Stage 03 — LOCKED (owner-approved) and MERGED into `main`.** Owner approved the Final Acceptance Test (PASS WITH FIXES; accepted ending commit `12670e7`, 277 tests, `integrity_check=ok`, `foreign_key_check=0`, schema v3). Stage 03 public contracts frozen in §8 (migration 0003 additive schema, unified `parties`, `financial_years`, additive company/item/unit/warehouse fields, Company/FinancialYear/Warehouse/Unit/Category/Item/Party/Role services, extended User + last-admin protection, strict numeric write-path safety, Item/Party search providers, 14 RBAC permissions, master-data UI, logo & parent-category). Stage 01/02 lock records unchanged. Stage 04 NOT STARTED. |
| 2026-08-14 | 1.6 | **Stage 03 — Final Owner Acceptance Test PASSED WITH FIXES (READY FOR OWNER FINAL REVIEW; not locked, not merged).** On-disk acceptance gate: migrations/idempotency/failure isolation, company/FY/warehouse/unit/category/item/person/user/role CRUD + validation, RBAC matrix + last-admin protection via direct service calls, audit (no secrets), rollback, restart persistence, backup/restore with Stage 03 data, integrity_check=ok / foreign_key_check=0. Fixed 2 defects (non-finite/oversized numeric input -> ValidationError; company default-warehouse validation). Completed logo picker + parent-category UI. Tests: 277 pass (+16). See §13I.1. |
| 2026-08-14 | 1.5 | **Stage 03 — Master Data & Business Setup implemented (READY FOR OWNER REVIEW; not locked, not merged).** Fresh branch from locked main `b6e633d`; 212-test gate passed first. Owner-approved additive unified `parties` model (Option A) — no locked contract touched. Migration 0003 (schema v3, forward/idempotent): parties + financial_years tables, additive columns (company/items/units/warehouses), 14 permissions, indexes. New repos/services for Company, Financial Year, Warehouse, Unit, Category, Item, Party, Role, extended User (last-admin protection); reusable Item/Party search providers; bilingual EN/Dari management UI (Items, Persons, Warehouses, Categories, Units, Company, Financial Years, Users, Roles) on the locked shell. **261 tests pass** (+49). On-disk acceptance workflow + integrity all pass. See §13I. |
| 2026-08-14 | 1.4 | **Stage 02 — LOCKED (owner-approved) and MERGED into `main`.** Owner reviewed the Final Acceptance Test (PASS WITH FIXES; acceptance ending commit `eda3d84`, 212 tests, `integrity_check=ok`, `foreign_key_check=0`, schema v2) and approved LOCK + MERGE. Stage 02 public contracts frozen in §8 (database/migrations, Decimal/strict-numeric safety, repository boundary, service/transaction boundaries, authentication, RBAC, double-entry financial safety + `FinancialService`, inventory movement-ledger, atomic document posting, audit, backup/restore, startup/login gate, Stage 02 UI). Stage 01 records unchanged. Stage 03 NOT STARTED. |
| 2026-08-13 | 1.3 | **Stage 02 — Final Owner Acceptance Test PASSED WITH FIXES (awaiting owner LOCK/MERGE; not locked, not merged).** Full production-readiness gate on a fresh on-disk DB: admin→master data→purchase→sale→transfer→second sale, with close/reopen between steps and direct persisted-data verification. One defect found & root-caused: malformed numeric input (e.g. price `"12x3"`) was silently coerced to 0.00 on the write path — fixed by strict `money.parse_decimal` + `document_math.parse_money_input` on all service write inputs (lines, amount_paid, journal amounts, inventory quantities); malformed input now rejected, `D()` stays lenient for display only. Verified: exact Decimal totals, all journals balance, inventory==SUM(signed movements), oversell/invalid-input rollback with unconsumed numbers, auth+lockout, RBAC via direct service calls, FK RESTRICT on referenced master data, backup/restore disaster recovery, `integrity_check=ok` + `foreign_key_check=0` after full workflow and after restore. **Tests: 212 pass** (+21). See §13H.10. |
| 2026-08-13 | 1.2 | **Stage 02 — Final technical audit & hardening (READY FOR OWNER FINAL REVIEW; not locked, not merged).** 7-pass production audit. Fixed at the service layer (no Stage 01 contract touched): unbalanced journals can no longer commit (added journal-balance guard + `FinancialService.post_entry`); sales can no longer oversell into negative stock (warehouse + stock enforcement, `InsufficientStockError`, explicit `allow_backorder`); negative price / negative discount / discount>line rejected via shared `compute_line`; stockable-item-without-warehouse rejected; added atomic `InventoryService.transfer`. Added reporting indexes (account ledger, journal-by-document, audit-by-entity) to migration 0001. Verified: Decimal exactness on edge values, journal balancing, inventory conservation, RBAC below UI, lockout, migration failure isolation, backup/restore roundtrip, `integrity_check=ok` + `foreign_key_check=0` after complex work and after restore. **Tests: 191 pass** (+47). See §13H.9. |
| 2026-08-13 | 1.1 | **Stage 02 — Production Database, Authentication & Login (READY FOR REVIEW; not locked, not merged).** Added Decimal-safe money + UTC clock; production schema (29 tables) with versioned atomic migrations + production-safe baseline seed (schema v2); repository + service layers (composition root `ApplicationContext`); RBAC with service-layer permission enforcement; PBKDF2 authentication with lockout + rehash; **Initial-Administrator setup + bilingual Login Page** (EN/Dari, RTL, Show/Hide) and a startup auth gate (no direct dashboard, no default admin); atomic sales/purchase posting (header+lines+signed inventory+balanced double-entry ledger+audit, rollback-safe) with transaction-safe document numbering; audit log; backup/restore foundation. Locked Stage 01 UI extended additively only (`MainWindow`/`HeaderBar` optional identity + logout). Full architecture in §13H. **144 tests pass** (90 Stage 01 + 54 new; one Stage 01 test repurposed for the migrated schema). Six required screenshots self-inspected. Not locked; Stage 03 not started. |

---

## 15. Module Completion Template (Spec §41)

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
