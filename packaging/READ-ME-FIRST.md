# Zenith Business — Stage 09 Owner Test Build

This is a **self-contained Windows test build** of Zenith Business, including the
locked **Stages 01–08** and the completed **Stage 09 (Accounting Reports &
Financial Statements)**. It ships with a **fresh test database already loaded
with sample data** so you can run the full acceptance test without typing any
setup.

> **New in this build:** your books now produce real **financial statements** —
> Trial Balance, Profit & Loss, Balance Sheet, General Ledger, Cash & Bank, and
> Receivables / Payables with ageing — all in English and Dari, printable on A4.
> The **cost of goods sold is now posted to the accounts**, so Inventory in the
> ledger finally matches the stock you actually hold.
>
> **Start with section 3 — it is the Stage 09 checklist.**

Nothing is installed on your PC. Everything lives inside this one folder. You do
**not** need Python or an internet connection to run it.

---

## 1. How to run it

1. **Unzip** this package anywhere (e.g. your Desktop). Keep all the files
   together in the same folder.
2. Double-click **`Run-ZenithBusiness.bat`**.
3. At the login screen, sign in as the owner/administrator:

   | Field    | Value        |
   |----------|--------------|
   | Username | `admin`      |
   | Password | `Admin@123`  |

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

## 3. Stage 09 checklist — what to test in this build

Everything below is new. Find it under **Account Reports → Financial
Statements**. Pick a **Period** (financial year, this year, this month, or your
own From/To dates) at the top of the screen.

**A. The headline test — do the books add up?**
Post a purchase, a sale and an expense, then open the reports:

| Report | What must be true |
|---|---|
| **Trial Balance** | **Total debit = Total credit**, and the footer says *Balanced: Yes* |
| **Profit & Loss** | Net sales − cost of goods sold = **Gross profit**; − expenses = **Net profit** |
| **Balance Sheet** | **Total assets = Total liabilities + equity**, footer says *Balanced: Yes* |

Worked example you can reproduce: buy 8 bags @ 125, sell 5 @ 200, pay 100 rent.
Net sales **1,000**, cost of goods sold **625**, gross profit **375**, expenses
**100**, **net profit 275**.

**B. Cost of goods sold now reaches the accounts.**
On the **Trial Balance**, account **5000 Cost of Goods Sold** must show the cost
of what you sold — not zero. And **1200 Inventory** must equal the value on
*Item Reports → Costing & Valuation → Inventory Valuation*. Those two numbers
were previously different; they must now be identical.

**C. General Ledger.**
Pick an **Account** and a date range. Every line shows date, reference,
description, debit, credit and a **running balance**. The closing balance must
equal that account's closing on the Trial Balance.

**D. Cash & Bank.**
Opening, money in, money out and closing for each cash/bank fund. The closing
must match the same account on the Trial Balance.

**E. Receivables and Payables, with ageing.**
Each customer's outstanding balance split into **Current / 1–30 / 31–60 / 61–90 /
90+ days**. Two things to check: the buckets add up to the balance, and the total
matches the customer's own ledger (*Account Reports → Customer Ledger*). Same for
suppliers.

**F. Returns and corrections keep the books straight.**
Return part of a sale, then correct a saved sale. After each, re-open the Trial
Balance and Balance Sheet — both must still balance, and cost of goods sold must
still match the costing report.

**G. Print, in both languages.**
Each report has **Print** (A4). Check a Trial Balance, a Profit & Loss and a
Balance Sheet in **English and دری** — the sheet must carry your own business
name and be in the same language as the screen.

> **Not in this build, by design:** there is no **period close or year close**
> yet. Because of that, the profit for the period is shown inside Equity on the
> balance sheet as "Result for the period" rather than moved into retained
> earnings. Seeded account names are still English.

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
