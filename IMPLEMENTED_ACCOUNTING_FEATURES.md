# Implemented Accounting Features

## How to Run

```bash
streamlit run main.py
# Run tests:
.venv/bin/python -m pytest tests/ -v
```

---

## A. Core Setup
- **Company profile**: name, tax/VAT/GST number, phone, email, website, address, city, state, zip, country
- **Fiscal year start/end** (MM-DD format)
- **Default currency**
- **Document prefixes**: invoice, bill, quote, payment (configurable in Settings > Document Prefixes)
- **Local backup**: timestamped copy of DB file (Settings > Backup & Restore)
- **Download database**: raw file download button in Settings
- **Local restore**: restore from a listed backup file

## B. Contacts
- Customers, suppliers, both-role parties
- Email, phone, billing address (city, state, country, zip)
- **Shipping address** (separate fields)
- **Contact person** field
- **Tax ID / VAT number**
- **Opening balance**
- **Notes**
- **Active/inactive** flag
- CSV import (new contacts only, by name)
- CSV export

## C. Items
- Products and services
- Item categories (item_group)
- **Sale price** (`rate`)
- **Purchase price** (`purchase_rate`)
- Tax rate (via linked tax)
- Income account / expense account
- **Stock quantity** field (manual update)
- **Active/inactive** flag
- CSV import/export

## D. Sales
- **Quotes/Estimates**: create, send, convert to invoice, cancel
- **Sales invoices** with line items
- **Convert quote to invoice** (one-click)
- **Invoice statuses**: Draft → Submitted → Partially Paid / Paid / Overdue → Cancelled
- **Overdue auto-detection**: runs on every page load, marks invoices past due_date
- **Customer payments** with invoice linking
- **Credit notes** (return invoices, `is_return=1`)
- **Discounts** (percent-based, at invoice level)
- **Tax calculation** per line item
- CSV export for invoices

## E. Purchases
- **Supplier bills** with line items
- **Bill statuses**: Draft → Submitted → Partially Paid / Paid / Overdue → Cancelled
- **Supplier payments** with bill linking
- **Debit notes** (return bills)
- **Discounts** per invoice
- **Tax calculation** per line item
- CSV export

## F. Banking
- **Bank accounts** and **Cash accounts** with opening balance
- **Linked GL account** (for ledger posting)
- **Deposits** with optional ledger posting
- **Withdrawals** with optional ledger posting
- **Transfers** between accounts (posts both sides)
- **Reconciled/unreconciled** flag per transaction
- **Reconciliation view**: opening, reconciled, unreconciled, current balance
- CSV export of bank transactions

## G. Accounting Engine
- **Chart of Accounts**: Asset, Liability, Equity, Income, Expense
- **Double-entry journal entries** with debit=credit validation
- **Automatic ledger posting** for: sales invoices, purchase invoices, payments, journal entries, bank transactions
- **Opening balances** (table structure; populated via Journal Entry with type "Opening Entry")
- **Trial balance** with balanced check
- Cancel reversal: cancelled entries marked `is_cancelled=1`, excluded from all reports

## H. Tax
- Tax rates table (name, rate%, linked GL account)
- Per-line-item tax calculation
- **Tax Summary report**: collected vs paid by rate, net payable/refundable
- Tax collected from sales invoices
- Tax paid on purchase invoices

## I. Reports (14 total)
| Report | Description |
|--------|-------------|
| General Ledger | All ledger entries with running balance, filterable by date/account/party/type |
| Trial Balance | Debit/credit totals by account with balance check |
| Balance Sheet | Assets, Liabilities, Equity as of date |
| Profit & Loss | Income vs expenses for a period |
| Accounts Receivable | Outstanding sales invoices |
| Accounts Payable | Outstanding purchase invoices |
| AR Aging | Aging buckets: Current, 1-30, 31-60, 61-90, 90+ days |
| AP Aging | Same for payables |
| Tax Summary | Tax collected vs paid by rate, net payable |
| Sales by Customer | Sales totals per customer |
| Purchases by Supplier | Purchase totals per supplier |
| Item Sales Report | Qty sold, net amount, tax per item |
| Cash Flow Summary | Operating inflows/outflows from payments + bank |
| Bank Account Summary | Balance summary across all bank/cash accounts |

All reports have **CSV download** buttons.

## J. Dashboard
- Income this month
- Expenses this month
- Total receivable (all periods)
- Total payable (all periods)
- Overdue invoice count + amount
- Overdue bill count + amount
- Net profit this month
- Cash & bank balance
- Recent sales invoices (8)
- Recent payments (8)
- Top customers this month (5)
- Top expense suppliers this month (5)
- Quick action buttons: New Quote, New Sales Invoice, New Purchase Invoice, Receive Payment, View Reports

## K. Import / Export
- CSV export: parties, items, sales invoices, purchase invoices, payments, bank transactions, general ledger
- CSV import: parties (skip existing by name), items (skip existing by name)
- Full database download (binary file)
- Timestamped local backups

## L. Quality
- **Decimal arithmetic** throughout invoice calculations (never float)
- Double-entry balance validation before journal submission
- Invoice edit blocked after submission
- Cancellation reverses all ledger entries
- **26 automated tests** covering: money calculations, double-entry, invoice statuses, partial payments, overdue detection, credit notes, payments, quotes, banking, reports

---

## Files Changed / Created

### New Files
- `services/banking.py` — bank accounts & transactions
- `services/quotes.py` — quotes/estimates + convert to invoice
- `services/import_export.py` — CSV import/export + backup/restore
- `ui/banking_page.py` — banking UI
- `ui/quotes_page.py` — quotes UI
- `ui/import_export_page.py` — import/export UI
- `tests/__init__.py`
- `tests/test_accounting.py` — 26 tests

### Modified Files
- `backend/database.py` — new tables (quote, bank_account, bank_transaction, opening_balance), new columns on existing tables, `migrate_schema()`
- `backend/reports.py` — 9 new report functions (ar_aging, ap_aging, tax_summary, sales_by_customer, purchases_by_supplier, item_sales_report, cash_flow_summary, bank_account_summary, fixed accounts_payable)
- `services/invoices.py` — Decimal calculations, discount_percent, update_overdue_statuses, create_credit_note, create_debit_note, partial payment status
- `services/parties.py` — new fields (is_active, notes, opening_balance, contact_person, shipping address)
- `services/setup.py` — save_settings extended with all new company profile fields
- `ui/reports_page.py` — all 14 reports with CSV download
- `ui/settings_page.py` — full company profile, document prefixes, backup/restore
- `main.py` — new nav items (Quotes, Banking, Import/Export), enhanced dashboard

---

## Database Changes

### New Tables
- `quote` + `quote_item`
- `bank_account`
- `bank_transaction`
- `opening_balance`

### New Columns (via ALTER TABLE migration)
- `accounting_settings`: tax_number, phone, email, website, address, city, state, zip_code, invoice_prefix, bill_prefix, quote_prefix, payment_prefix, logo_path
- `party`: is_active, notes, opening_balance, contact_person, shipping_address, shipping_city, shipping_state, shipping_country, shipping_zip
- `item`: purchase_rate, stock_quantity, is_active

---

## Incomplete / Known Limitations

- **Recurring invoices**: not implemented (requires scheduler)
- **PDF/print export**: not implemented (would need reportlab/weasyprint)
- **File attachments**: not implemented
- **Stock quantity** is a manual field, not auto-decremented on invoice submission
- **Multi-currency exchange rate** ledger posting uses exchange_rate multiplier but no FX gain/loss account
- **Opening balance journal**: use Journal Entry with type "Opening Entry" to set opening balances
- **Tax groups**: not implemented; taxes are individual rates
- **Contact persons** as separate linked records: stored as a single text field
- Restore requires app restart to reload connection
