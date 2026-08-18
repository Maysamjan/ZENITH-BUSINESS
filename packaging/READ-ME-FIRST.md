# Zenith Business — Stage 05 Owner Test Build (corrected)

This is a **self-contained Windows test build** of Zenith Business, including the
locked **Stages 01–04** and the completed **Stage 05 (Receipts · Payments ·
Expenses · Cash/Fund movements)**. It ships with a **fresh test database already
loaded with sample data** so you can run the full acceptance test without typing
any setup.

> **This build also contains the six manual-test fixes you reported.** A short
> checklist to verify them is in section 5 below; the original 8 acceptance
> scenarios remain in section 3.

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

## 3. The 8 acceptance scenarios — where to click

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

## 6. Where the test data is stored

For this portable build, all data stays inside this folder under **`appdata\`**
(the app is pointed there by `Run-ZenithBusiness.bat`):

- Database: `appdata\local\ZenithSoft\ZenithBusiness\data\zenith_business.db`
- Logs: `appdata\local\ZenithSoft\ZenithBusiness\logs\`
- Backups: `appdata\local\ZenithSoft\ZenithBusiness\backups\`

`appdata_seed\` holds the pristine copy used by **Reset-Test-Data.bat**. Deleting
the whole folder removes every trace of the test build from your PC.

> Note: this is a **test** build for acceptance only. Stage 05 is **not locked or
> merged** yet — it is waiting for your approval after you finish testing.
