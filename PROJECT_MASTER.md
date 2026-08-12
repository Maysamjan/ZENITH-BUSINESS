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
| PROJECT_MASTER.md Version | 0.7 |
| Current Stage | **01 — FOUNDATION + 01B–01F PREMIUM UI (implemented; READY FOR OWNER REVIEW)** |
| Database Schema Version | none (infrastructure only; **no tables created**) |
| Last Updated | 2026-08-11 |

**Stage gate:** Stage 00 (constitution) is the approved baseline on `main`.
Stage 01 (foundation) is implemented on a feature branch and is **awaiting owner
review**. It is **not** LOCKED — only the owner may declare it LOCKED after
review. No business modules and no database tables were created (Prompt 01 §31).
Next authorized step after approval is **PROMPT 02 — DATABASE**.

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
| 01 | Project Foundation (+01B–01F premium UI) | 🔶 Implemented — **ready for owner review** (not LOCKED) |
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

## 14. Change Log

| Date | PROJECT_MASTER version | Change |
|------|------------------------|--------|
| 2026-08-11 | 0.1 | Initial constitution captured from Master Spec v1.0 at Stage 00. No production code or schema created. Awaiting Prompt 01 — Project Foundation. |
| 2026-08-11 | 0.2 | Stage 01 (Project Foundation) implemented on feature branch: project structure, config, identity, logging, exceptions/global handler, SQLite infrastructure (connection + transactions + health, FK on, WAL), i18n/RTL-LTR, centralized UI design system, top-nav shell + branded home + status bar, security readiness (PBKDF2 passwords, licensing boundary), 60 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.3 | Stage 01B (UI/UX refinement) on the same feature branch: three-tier top chrome (navy HeaderBar + white PrimaryNav + contextual ContextBar), redesigned composed home (hero + readiness + reserved quick-access), expanded semantic design system (colors, typography hierarchy, control dims, FieldWidth XS–XL, reusable components), form + table + dialog + empty-state standards, RTL/LTR visual pass. Backend foundation unchanged. 70 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.4 | Stage 01C (premium UI redesign) on the same feature branch: denser professional layout tokens, grid-based business-form architecture, full **Sales Invoice visual prototype** as the reference design (header + dominant line grid + summary/operational + action bar with shortcut hints), StatTile/LabeledField/apply_shadow/escape_amp components, upgraded list/management screen, home depth refinement, multi-resolution (1366/1600/1920) + Dari-RTL verification. Backend unchanged. 72 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.5 | Stage 01D (rapid invoice entry UX) on the same feature branch: reusable provider-driven `SearchSelector` autocomplete architecture; keyboard-first Sales Invoice (item search → populate → qty → price → discount → next line); customer autocomplete filling balance/credit/phone; redesigned ERP/POS invoice workspace with always-visible payment area and permission-gated cost note; platform-style action icons; mock providers in `ui/mock/` (clearly non-production); Dari-RTL + 1366/1600 verification (no horizontal scroll at 1366). Backend unchanged. 80 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.6 | Stage 01E (premium color system + printed invoice) on the same feature branch: intentional semantic color tokens (accent, workspace gradient, financial/status roles) applied by meaning (strong filled Grand Total, cash/credit/stock colors, active-row marker, destructive Delete); richer Sales Invoice character (accent cards, colored indicators); and a real customer-facing **A4 printed Sales Invoice** (EN LTR + Dari RTL) driven by the same demo transaction, opened via Save & Print → in-app print preview. Backend unchanged. 84 passing tests. **No business tables.** Ready for owner review; not LOCKED. |
| 2026-08-11 | 0.7 | Stage 01F (one-screen workspace + dashboard + print reflow) on the same feature branch: Sales Invoice fits one screen at 1366×768 (non-scrolling) with fields bound to the shared transaction (screen == print, date fixed); Home replaced by a compact business **dashboard** (KPIs, quick actions, recent transactions, low stock); new **paginated print engine** supporting **A4 and A5**, content reflow (compact short invoices, multi-page long invoices with repeated headers + page numbers + totals on the last page) and **amount-in-words** (English + Dari); print preview gains an A4/A5 toggle. Backend unchanged. 88 passing tests. **No business tables.** Ready for owner review; not LOCKED. |

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
