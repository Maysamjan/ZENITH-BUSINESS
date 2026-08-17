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
| PROJECT_MASTER.md Version | 2.0 |
| Current Stage | **05 — RECEIPTS, PAYMENTS & EXPENSES — 🧪 READY FOR OWNER REVIEW (NOT locked, NOT merged)** |
| Database Schema Version | **5** (0001 initial_schema, 0002 baseline_seed, 0003 stage03_master_data, 0004 stage04_sales_purchases_returns, 0005 stage05_receipts_payments_expenses) |
| Last Updated | 2026-08-17 |

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
and party-balance derivation. Full architecture: §13K. **Stage 06 is NOT STARTED.**

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
| 05 | Receipts, Payments & Expenses | 🧪 **READY FOR OWNER REVIEW** (NOT locked, NOT merged) |
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

**Recommendation:** *STAGE 05 IS TECHNICALLY READY FOR OWNER REVIEW.* Not locked,
not merged, Stage 06 not started — owner decision only.

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

## 14. Change Log

| Date | PROJECT_MASTER version | Change |
|------|------------------------|--------|
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
