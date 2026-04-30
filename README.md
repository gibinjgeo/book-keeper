# Frappe Books — Python Edition

A pure Python port of [Frappe Books](https://frappe.io/books), converted from Electron + Vue 3 + TypeScript to **Streamlit + SQLite**.

## What This Is

Frappe Books is a free, open-source double-entry bookkeeping application. This Python edition preserves the full accounting engine and workflows using only local, offline storage — no Node.js, no Electron, no cloud services required.

## Features

| Feature | Status |
|---|---|
| Company setup with Standard Chart of Accounts | ✅ |
| Chart of Accounts (hierarchical, 75 accounts) | ✅ |
| Parties (Customers & Suppliers) | ✅ |
| Items (Products & Services) with Tax rates | ✅ |
| Sales Invoices (Draft → Submit → Cancel) | ✅ |
| Purchase Invoices (Draft → Submit → Cancel) | ✅ |
| Payments (Receive / Pay) with invoice allocation | ✅ |
| Journal Entries with debit/credit validation | ✅ |
| General Ledger report with filters | ✅ |
| Trial Balance report | ✅ |
| Balance Sheet | ✅ |
| Profit & Loss Statement | ✅ |
| Accounts Receivable / Payable aging | ✅ |
| CSV export for all reports | ✅ |
| Local SQLite database (fully offline) | ✅ |

## Quick Start

### 1. Install dependencies

```bash
# Using a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or if you already have a venv with streamlit and pandas:

```bash
# Activate your existing environment, then:
cd python_app
streamlit run main.py
```

### 2. Run the app

```bash
cd python_app
streamlit run main.py
```

The app opens at **http://localhost:8501** in your browser.

### 3. First-run setup

On first launch, fill in your company name, country, and currency. The app will automatically load the **Standard Chart of Accounts** with 75 pre-built accounts.

## Project Structure

```
python_app/
├── main.py                   # Streamlit entry point
├── requirements.txt
├── backend/
│   ├── database.py           # SQLite schema & connection
│   ├── ledger.py             # Double-entry ledger posting
│   └── reports.py            # Financial report queries
├── services/
│   ├── setup.py              # Company setup & COA import
│   ├── accounts.py           # Chart of Accounts CRUD
│   ├── parties.py            # Customer/Supplier CRUD
│   ├── items.py              # Item & Tax CRUD
│   ├── invoices.py           # Sales/Purchase invoice logic
│   ├── payments.py           # Payment processing
│   └── journal.py            # Journal entry logic
├── ui/
│   ├── setup_page.py         # Setup wizard
│   ├── accounts_page.py      # Chart of Accounts UI
│   ├── parties_page.py       # Parties UI
│   ├── items_page.py         # Items & Taxes UI
│   ├── sales_page.py         # Sales Invoices UI
│   ├── purchases_page.py     # Purchase Invoices UI
│   ├── payments_page.py      # Payments UI
│   ├── journal_page.py       # Journal Entries UI
│   ├── reports_page.py       # Reports UI
│   └── settings_page.py      # Settings UI
├── data/
│   ├── standard_coa.json     # Standard Chart of Accounts fixture
│   └── country_info.json     # Country information
└── storage/
    └── books.db              # SQLite database (auto-created)
```

## What Was Discarded

| Original Feature | Reason Discarded |
|---|---|
| Electron main process | Replaced by Streamlit server |
| Vue 3 / TailwindCSS frontend | Replaced by Streamlit UI |
| Vite / TypeScript build chain | Python needs no compilation |
| Bree job scheduler | No background jobs needed locally |
| ERPNext sync integration | Cloud-only, cannot work offline |
| Electron auto-updater | Python app updates itself via pip |
| IPC (Inter-Process Communication) | Direct Python function calls instead |
| PDF print via Electron | Streamlit download buttons instead |
| Telemetry / mothership contact | Removed entirely |
| Loyalty Programs / Pricing Rules | Complex feature, retained schema only |
| POS (Point of Sale) module | Complex feature, can be added later |
| Inventory stock tracking | Complex feature, can be added later |
| Cloud authentication | Local operation, no auth required |

## Accounting Engine

The double-entry engine faithfully mirrors the original TypeScript logic:

- **Sales Invoice submit** → DR Debtors, CR Income (per item), CR Tax accounts
- **Purchase Invoice submit** → CR Payables, DR Expense (per item), DR Tax accounts
- **Payment (Receive)** → DR Cash/Bank, CR Debtors
- **Payment (Pay)** → DR Payables, CR Cash/Bank
- **Journal Entry** → Any custom DR/CR combination (validated balanced)
- **Cancel** → Marks ledger entries as `is_cancelled = 1` (preserves audit trail)

All amounts are stored as `REAL` (IEEE 754 double) in SQLite, consistent with the original `better-sqlite3` storage.

## Requirements

- Python 3.10+
- streamlit >= 1.32.0
- pandas >= 2.0.0
