# Book Keeper

A free, open-source double-entry bookkeeping application built with **Streamlit + SQLite** — fully offline, no cloud services required.

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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run main.py
```

The app opens at **http://localhost:8501** in your browser.

### 3. First-run setup

On first launch, fill in your company name, country, and currency. The app will automatically load the **Standard Chart of Accounts** with 75 pre-built accounts.

## Project Structure

```
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
└── data/
    ├── standard_coa.json     # Standard Chart of Accounts fixture
    └── country_info.json     # Country information
```

## Requirements

- Python 3.10+
- streamlit >= 1.32.0
- pandas >= 2.0.0

---

Inspired by [Frappe Books](https://frappe.io/books)
