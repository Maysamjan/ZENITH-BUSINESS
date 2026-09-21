# Zenith Business — Stage 10 Owner Test Build

This is a **self-contained Windows test build** of Zenith Business, including the
locked **Stages 01–09** and the completed **Stage 10 (Single-PC Security, Backup
& Licensing)**. It ships with a **fresh test database already loaded with sample
data** so you can run the full acceptance test without typing any setup.

> **New in this build:** the things that make the program safe to hand to a real
> customer — a protected owner login with a recovery code, an audit log you can
> read, a backup you can trust and a restore that cannot lose your data, a
> database health check, and offline machine-bound licensing with a Demo period.
>
> **Start with section 3 — it is the Stage 10 checklist.**

Nothing is installed on your PC. Everything lives inside this one folder. You do
**not** need Python or an internet connection to run it.

---

## 1. How to run it

1. **Unzip** this package anywhere (e.g. your Desktop). Keep all the files
   together in the same folder.
2. Double-click **`Run-ZenithBusiness.bat`**.
3. **The first screen is now ACTIVATION, not login.** Licensing is checked
   *before* anyone can sign in, so an unlicensed computer never reaches the
   login form or the program behind it. The screen shows this computer's
   **Machine ID** and offers **Generate Activation Request** and **Import
   License**.
4. Once a valid licence is imported, the same window moves straight on to the
   login screen. Sign in as the owner/administrator:

   | Field    | Value        |
   |----------|--------------|
   | Username | `admin`      |
   | Password | `Admin@123`  |

> **This build has no vendor key embedded yet**, so it stops at the Activation
> screen and reads *Unlicensed build*. That is section 3A below working as
> intended, and it is the one part you can test today. To unlock the rest, run
> `python tools/zenith_license_tool.py generate` on your own PC and send the
> `PUBLIC KEY:` line to your developer — the next build will accept the licences
> you sign.

> Windows SmartScreen may show a "Windows protected your PC" notice the first
> time (the test build is not code-signed). Click **More info → Run anyway**.

To start the test over from clean sample data at any time, double-click
**`Reset-Test-Data.bat`**.

---

## 2. What the sample data already contains

| Master data | Details |
|-------------|---------|
| Company     | Zenith Trading Co. |
| Financial year | FY 2026 (active) |
| Warehouse   | Main Store (with stock on hand) |
| Items       | Rice, Sugar, Cooking Oil, Black Tea (stocked) |
| Customers   | **Kabul General Store** (owes money), Herat Traders (clean) |
| Suppliers   | **National Foods** (we owe money), Kabul Wholesale Co. |
| Funds       | Cash and Bank (both already carry a balance) |

Already-posted documents (so lists and printing work immediately):

- 1 **Receipt** (Cash), 1 **Payment** (Bank), 1 **Expense** (Cash).
- **Kabul General Store** is left with an **open receivable of 49,200 AFN** so you
  can post a partial receipt against it.
- **National Foods** is left with an **open payable of 430,000 AFN** so you can
  post a partial payment against it.
- Cash fund balance: **22,000 AFN** · Bank fund balance: **−100,000 AFN**.

---

## 3. Stage 10 checklist — what to test in this build

Everything below is new. It lives under the **Tools** menu: **Backup & Restore**,
**Audit Log** and **License**.

### A. Activation comes before login

1. On a fresh install the first screen is **Activate Zenith Business**. There is
   no way past it to the login form — that is the point.
2. It names *why*: not activated yet, licence for another computer, licence
   altered, demo finished. Each has its own wording.
3. **Generate Activation Request** writes a `.zreq` carrying this computer's
   hashed traits, your business name and nothing else — no password, no key, no
   raw hardware serial.
4. **Import License** with the `.zlic` you receive. The window moves straight on
   to login.
5. Close and reopen the program: it is still activated, and the licence is
   re-checked every single start.

### B. Login protection

1. Sign in with the correct password — it works, as before.
2. Sign out, then type the **wrong password five times**. The account locks for
   **15 minutes** and counts the time down on screen ("Try again in 12m 34s").
   Further attempts during the lock do **not** restart the timer.
3. After the wait, you get a **fresh five attempts** — one further mistake must
   not lock you straight out again.
4. **Forgot your password?** on the login screen resets it with a recovery code.
   Issue one first from **Tools → Account Settings → Recovery Code**; it is
   shown once and cannot be shown again, only replaced.
5. **Tools → Account Settings → Change Password.** It asks for your current
   password first. Change it, sign out, and confirm the **old password no longer
   works** and the new one does.

### C. Backup

**Tools → Backup & Restore → Create Backup.**
A new timestamped file appears in the list and the status line says it was
**created and verified**. Use **Check a Backup File** on it — it must report a
valid backup. Try it on any other file on your PC (a photo, a Word document) —
it must be **refused**, naming the reason.

**Check Database** confirms the live database is healthy.

Two things to check about the password:

* The backup is locked with **your owner password**, and the program now refuses
  to make one with anything else. If you type something that is not your current
  password, no file is written at all — a backup nobody can open is worse than
  no backup.
* A backup opens with the password that was active **when it was made**. If you
  change your password afterwards, older backups still need the old one.
* Try it with a Persian keyboard layout active: the characters you actually type
  are the characters used, so the English password's *key positions* will not
  open it. Checking and restoring behave identically — that inconsistency is
  fixed.

### D. Restore — the important one

**Restore from File…**

1. Pick a **file that is not a backup**. It must be refused *before anything
   happens*, and your data must be untouched.
2. Pick a **real backup**. It warns you that all current data will be replaced,
   then asks for your **owner password**. Cancel once — nothing should change.
3. Do it again and confirm. Afterwards:
   * the data is what was in the backup;
   * a **safety copy of your previous data** was written into the backup list
     (named `zenith-before-restore-….zbak`) — you can restore that to undo. It
     is **encrypted** with your owner password now, so it is not a readable copy
     of your books sitting in a folder;
   * restart the application when it tells you to.

> Your current data is copied to safety **before** anything is replaced, and the
> replacement happens in one step. If it fails part way through — the disk fills
> up, the PC loses power — you keep the database you had.

### E. Audit log

**Tools → Audit Log.** It must show what you just did: the successful login, the
**failed** logins from step A, the password change, the backup, the restore, and
the licence actions from step E — each with date/time, action, entity, reference
and details. It is **read-only**: there is no way to edit or delete an entry.

### F. Licensing and the demo period

**Tools → License** shows the same state the activation screen shows — product,
licence type, status, Machine ID, licence details, expiry.

**A demo is now a real signed licence**, not something the program grants itself.
There is no free period for an installation that has never been activated: it
stops at the activation screen until a `.zlic` arrives.

1. Import a **DEMO** licence: the screen shows *Demo*, the real expiry date and
   the days remaining. The program works normally.
2. Import a **FULL** licence: *Activated*, and the word DEMO disappears from
   every screen — activation screen, login footer, status bar and License page.
   Restart and confirm it is still FULL.
3. **When a demo runs out** the program stops at the activation screen on the
   next start. If it is already open when the time passes, it returns to the
   activation screen by itself — leaving it running does not extend anything.
4. **Move the Windows clock backwards.** The demo must not gain time. The
   program remembers the latest date it has ever seen and will not believe an
   earlier one; it says so on the activation screen when it notices.
5. Things that must be **refused**, each leaving your existing licence and your
   data untouched:
   * a `.zlic` edited in Notepad (any change at all);
   * a `.zlic` issued for a different computer;
   * a `.zlic` whose date has passed;
   * copying this whole folder to a second PC — it must **not** be activated
     there.

> If licensing ever fails, **your business data is never touched**. Nothing is
> deleted, encrypted or rewritten. The worst that happens is the program asks
> you to activate, and your database file stays exactly where it is.

---

## 4. Earlier stages — the 8 acceptance scenarios

Navigation lives on the **top menu bar**. Switch language any time from the
**EN / دری** toggle at the top-right (Dari flips the whole screen to
right-to-left).

1. **Credit Sale → Customer Receivable**
   *Buy & Sell → Sales Invoice* (or the **New Sale** shortcut on the dashboard).
   Choose customer **Herat Traders**, add an item
   (e.g. Rice), set quantity/price, leave amount paid = 0, **Save**. Open
   *Account Reports* (or reopen the customer) and confirm the receivable
   increased by the invoice total.

2. **Partial Customer Receipt → Remaining Receivable**
   *Receipts & Payments → Receive Payment.* Search **Kabul General Store** — the
   screen shows the **Previous balance (49,200)**. Enter an amount (e.g. 20,000),
   pick the **Cash** account, **Save**. The **Remaining** updates live (→ 29,200)
   and the customer’s receivable falls by exactly what you received. *(You cannot
   type the balance by hand — it is derived from the receipt.)*

3. **Credit Purchase → Supplier Payable**
   *Buy & Sell → Purchase Invoice* (or the **New Purchase** dashboard shortcut).
   Choose supplier **Kabul Wholesale Co.**, add an
   item, quantity/price, amount paid = 0, **Save.** Confirm the supplier payable
   increased by the purchase total.

4. **Partial Supplier Payment → Remaining Payable**
   *Receipts & Payments → Make Payment.* Search **National Foods** — the screen
   shows **Previous Payable (430,000)**. Enter an amount (e.g. 50,000), pick the
   **Bank** account, **Save.** **Remaining Payable** updates live (→ 380,000).

5. **Cash Expense**
   *Receipts & Payments → New Expense.* Pick a category (e.g. **Rent** or
   **Electricity**), enter a payee and amount, choose the **Cash** account,
   **Save.**

6. **Cash / Bank balance changes**
   Open the **Funds** menu. Confirm the Cash and Bank balances reflect every
   receipt (increases the fund), payment (decreases it) and expense (decreases
   it) you posted in the steps above.

7. **Receipt / Payment / Expense printing**
   Open **Receipts List**, **Payments List** and **Expenses List**. Each row has
   a **Print** action that opens a print preview of the voucher (Receipt /
   Payment Voucher / Expense Voucher) with company header, amount in words and
   signature lines. You can also **Save & Print** directly from any entry screen.
   Use the print preview’s paper-size and language to see A4/A5 and Dari/English.

8. **Dari / English switching**
   Use the **EN / دری** toggle (top-right). The entire application — menus,
   forms, lists and printed vouchers — switches language and, for Dari, flips to
   a genuine right-to-left layout.

---

## 5. Verify the six reported fixes

1. **Clearer Sales Invoice.** *Buy & Sell → Sales Invoice.* The screen now reads
   top-to-bottom: Customer → invoice info → item search → line items → payment →
   totals → Save/Print, with a **Registered / Walk-in** toggle at the top.

2. **Walk-in / general customer.** On the Sales Invoice press **Walk-in**, type a
   name (e.g. *Ahmad Khan*), phone optional, add an item, and **pay in full**
   (walk-in sales cannot be left on credit — for credit choose **Registered** and
   pick a customer). Save, then **Save & Print** — the printed invoice shows the
   name you typed. (A seeded walk-in sale, *SALE-000002 · Ahmad Khan*, is already
   in the Sales list.)

3. **Edit / replace / delete invoice lines before saving.** With lines added:
   double-click a **Qty / Price / Discount** cell to edit it (totals recompute
   instantly); double-click the **item name** to replace the whole line; select a
   row and press **Delete Line**. Nothing touches stock until you Save.
   *Correcting a saved sale:* open **Sales list**, press **Void** on a posted row —
   it reverses the stock, the customer balance and the accounting entry, keeps the
   original document, and marks it *Cancelled*.

4. **Customer / Supplier ledger.** *Account Reports → Customer Ledger* (or
   *Supplier Ledger*), choose a person, and see Total Sales / Received / Current
   Receivable (or Purchases / Paid / Payable) plus every transaction with a
   running balance. Try **Kabul General Store** and **National Foods**.

5. **Small-window layout.** Shrink the window (drag it small). On the Receipt and
   Sales screens the **Save / Print / Close** buttons stay pinned and reachable
   (the form scrolls); no action button is pushed off-screen.

6. **Company logo on printed bills.** A sample logo is already configured and
   appears on printed invoices/vouchers (try **Save & Print**). To change it:
   *Base Data → Company* → choose a PNG/JPG logo → Save; new printouts use it, and
   it survives an app restart. The logo keeps its aspect ratio and degrades to a
   letter-mark if the file is missing.

---

## 6. Owner review round 2 — what's new to verify

- **Redesigned Sales Invoice** (*Buy & Sell → Sales Invoice*): compact customer +
  invoice header, a **large items table** (5 rows visible at 1024×768, more on
  bigger screens, scrolls for 10+), a **Unit** selector on the entry row, obvious
  **Add / Edit Line / Delete Line**, and a totals strip showing **Previous** and
  **Updated** customer balance.
- **Edit / replace a line** before saving: pick a row → **Edit Line** (reloads it so
  you can change the item, unit, qty, price, discount) or double-click Qty/Price/
  Discount to edit in place; **Delete Line** removes it. Totals recalculate live.
- **Correct a posted invoice**: on **Sales list**, press **Correct** on a posted row
  → it opens as “Correcting invoice …”; change anything and Save. It safely voids the
  original and posts a linked replacement (stock, balance and accounting all
  reconcile). If the invoice already has a **Return**, Correct is blocked and points
  you to Return/Void.
- **View a customer/supplier account in context**: on **Base Data → Persons** press
  **View Account** on a row; or on **Receipts List / Payments List** press **View
  Account** — it opens that party's ledger directly.
- **Account Settings** (*Tools → My Account*): change your own **password**
  (current + new + confirm) and **username** (current password required).
- **Small screens**: resize the window down to 1024×768 — Save/Print/Close stay
  reachable and the items table stays usable.

---

## 7. Where the test data is stored

For this portable build, all data stays inside this folder under **`appdata\`**
(the app is pointed there by `Run-ZenithBusiness.bat`):

- Database: `appdata\local\ZenithSoft\ZenithBusiness\data\zenith_business.db`
- Logs: `appdata\local\ZenithSoft\ZenithBusiness\logs\`
- Backups: `appdata\local\ZenithSoft\ZenithBusiness\backups\`

`appdata_seed\` holds the pristine copy used by **Reset-Test-Data.bat**. Deleting
the whole folder removes every trace of the test build from your PC.

> Note: this is a **test** build for acceptance only. Stage 09 was approved and
> **locked on 2026-09-18** at commit `b8a2cfc`; it is **not merged** yet.
