"""
Seed script — populates the Book Keeper database with realistic fake data.

Run from the project root:
    python test_data/seed.py

It is safe to run more than once; all inserts use INSERT OR IGNORE where possible.
The script will run company setup automatically if it hasn't been done yet.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import get_or_create_db
from services.setup import is_setup_done, complete_setup
from services.parties import create_party, get_party
from services.items import create_item, get_item
from services.invoices import (
    create_sales_invoice,
    submit_sales_invoice,
    create_purchase_invoice,
    submit_purchase_invoice,
)
from services.payments import create_payment, submit_payment
from services.journal import create_journal_entry, submit_journal_entry


# ── helpers ──────────────────────────────────────────────────────────────────

def find_account(conn, *keywords, account_type=None):
    """Return the first account name whose name contains all keywords (case-insensitive)."""
    rows = conn.execute("SELECT name, account_type FROM account WHERE is_group = 0").fetchall()
    kw = [k.lower() for k in keywords]
    for row in rows:
        name_lower = row["name"].lower()
        if all(k in name_lower for k in kw):
            if account_type is None or row["account_type"] == account_type:
                return row["name"]
    return None


def safe_create_party(conn, data):
    if not get_party(conn, data["name"]):
        create_party(conn, data)
        print(f"  + Party: {data['name']}")
    else:
        print(f"  ~ Party exists: {data['name']}")


def safe_create_item(conn, data):
    if not get_item(conn, data["name"]):
        create_item(conn, data)
        print(f"  + Item: {data['name']}")
    else:
        print(f"  ~ Item exists: {data['name']}")


# ── main seed ─────────────────────────────────────────────────────────────────

def seed(conn):

    # ── 1. Discover key accounts ──────────────────────────────────────────────
    print("\n[1/6] Discovering accounts...")

    debtors      = find_account(conn, "debtor")
    creditors    = find_account(conn, "creditor")
    cash         = find_account(conn, "cash")
    bank         = find_account(conn, "bank") or cash
    sales_acc    = find_account(conn, "service") or find_account(conn, "sales") or find_account(conn, "income")
    expense_acc  = find_account(conn, "administrative") or find_account(conn, "office") or find_account(conn, "expense")
    duties_acc   = find_account(conn, "duties") or find_account(conn, "tax")

    print(f"  Debtors   : {debtors}")
    print(f"  Creditors : {creditors}")
    print(f"  Cash      : {cash}")
    print(f"  Bank      : {bank}")
    print(f"  Sales     : {sales_acc}")
    print(f"  Expense   : {expense_acc}")
    print(f"  Duties    : {duties_acc}")

    if not all([debtors, creditors, cash, sales_acc, expense_acc]):
        print("\nERROR: Could not find required accounts. Make sure setup has been run.")
        sys.exit(1)

    # ── 2. Parties ────────────────────────────────────────────────────────────
    print("\n[2/6] Creating parties...")

    customers = [
        {"name": "Acme Corporation",    "role": "Customer", "email": "billing@acme.com",      "phone": "555-0101", "city": "New York",      "country": "United States"},
        {"name": "TechStart Solutions", "role": "Customer", "email": "ap@techstart.io",        "phone": "555-0102", "city": "San Francisco", "country": "United States"},
        {"name": "Green Valley Retail", "role": "Customer", "email": "finance@greenvalley.com","phone": "555-0103", "city": "Austin",        "country": "United States"},
    ]
    suppliers = [
        {"name": "Office Supplies Co.",     "role": "Supplier", "email": "invoices@officesupplies.com", "phone": "555-0201", "city": "Chicago",  "country": "United States"},
        {"name": "Cloud Infrastructure Ltd","role": "Supplier", "email": "billing@cloudinfra.net",      "phone": "555-0202", "city": "Seattle",  "country": "United States"},
        {"name": "Marketing Agency Pro",    "role": "Supplier", "email": "accounts@mapro.co",           "phone": "555-0203", "city": "New York", "country": "United States"},
    ]
    for p in customers + suppliers:
        safe_create_party(conn, p)

    # ── 3. Items ──────────────────────────────────────────────────────────────
    print("\n[3/6] Creating items...")

    tax_row = conn.execute("SELECT name, rate, account FROM tax LIMIT 1").fetchone()
    tax_name  = tax_row["name"]  if tax_row else None
    tax_rate  = tax_row["rate"]  if tax_row else 0.0
    tax_acc   = tax_row["account"] if tax_row else duties_acc

    items = [
        {
            "name": "Web Development Services",
            "item_type": "Service",
            "item_group": "Services",
            "for_purpose": "Sales",
            "unit": "Hour",
            "rate": 150.00,
            "description": "Custom web development and design",
            "income_account": sales_acc,
            "expense_account": expense_acc,
            "tax": tax_name,
        },
        {
            "name": "Laptop Pro 15",
            "item_type": "Product",
            "item_group": "Products",
            "for_purpose": "Both",
            "unit": "Unit",
            "rate": 1_200.00,
            "description": "High-performance business laptop",
            "income_account": sales_acc,
            "expense_account": expense_acc,
            "tax": tax_name,
        },
        {
            "name": "Monthly Support Package",
            "item_type": "Service",
            "item_group": "Services",
            "for_purpose": "Sales",
            "unit": "Month",
            "rate": 500.00,
            "description": "Ongoing technical support and maintenance",
            "income_account": sales_acc,
            "expense_account": expense_acc,
            "tax": None,
        },
        {
            "name": "Office Desk",
            "item_type": "Product",
            "item_group": "Products",
            "for_purpose": "Purchase",
            "unit": "Unit",
            "rate": 350.00,
            "description": "Ergonomic office desk",
            "income_account": sales_acc,
            "expense_account": expense_acc,
            "tax": tax_name,
        },
        {
            "name": "Cloud Hosting (Annual)",
            "item_type": "Service",
            "item_group": "Services",
            "for_purpose": "Purchase",
            "unit": "Year",
            "rate": 2_400.00,
            "description": "Annual cloud infrastructure subscription",
            "income_account": sales_acc,
            "expense_account": expense_acc,
            "tax": None,
        },
    ]
    for it in items:
        safe_create_item(conn, it)

    # helper to build an invoice line
    def line(item_name, qty, rate=None, override_tax_rate=None, override_tax_acc=None):
        it = conn.execute("SELECT * FROM item WHERE name = ?", (item_name,)).fetchone()
        r = float(rate if rate is not None else it["rate"])
        tr = override_tax_rate if override_tax_rate is not None else (tax_rate if it["tax"] else 0.0)
        ta = override_tax_acc if override_tax_acc is not None else (tax_acc if it["tax"] else None)
        amt = round(qty * r, 2)
        return {
            "item": item_name,
            "description": it["description"],
            "account": it["income_account"],
            "quantity": qty,
            "rate": r,
            "amount": amt,
            "tax_rate": tr,
            "tax_amount": round(amt * tr / 100, 2),
            "tax_account": ta,
        }

    def purchase_line(item_name, qty, rate=None):
        it = conn.execute("SELECT * FROM item WHERE name = ?", (item_name,)).fetchone()
        r = float(rate if rate is not None else it["rate"])
        tr = tax_rate if it["tax"] else 0.0
        ta = tax_acc  if it["tax"] else None
        amt = round(qty * r, 2)
        return {
            "item": item_name,
            "description": it["description"],
            "account": it["expense_account"],
            "quantity": qty,
            "rate": r,
            "amount": amt,
            "tax_rate": tr,
            "tax_amount": round(amt * tr / 100, 2),
            "tax_account": ta,
        }

    # ── 4. Sales Invoices ─────────────────────────────────────────────────────
    print("\n[4/6] Creating sales invoices...")

    sales = [
        # (party, date, due_date, items, submit?)
        ("Acme Corporation",    "2026-01-10", "2026-02-10",
         [line("Web Development Services", 20), line("Monthly Support Package", 1)], True),

        ("TechStart Solutions", "2026-02-05", "2026-03-05",
         [line("Laptop Pro 15", 3)], True),

        ("Green Valley Retail", "2026-03-15", "2026-04-15",
         [line("Web Development Services", 10), line("Laptop Pro 15", 1)], True),

        ("Acme Corporation",    "2026-04-01", "2026-05-01",
         [line("Monthly Support Package", 2)], True),

        # Draft — not yet submitted
        ("TechStart Solutions", "2026-04-20", "2026-05-20",
         [line("Web Development Services", 8)], False),
    ]

    sinv_names = []
    for party, date, due_date, inv_items, do_submit in sales:
        name = create_sales_invoice(
            conn,
            {"party": party, "date": date, "due_date": due_date,
             "account": debtors, "currency": "USD"},
            inv_items,
        )
        if do_submit:
            submit_sales_invoice(conn, name)
            print(f"  + Sales Invoice {name} [{party}] — Submitted")
        else:
            print(f"  + Sales Invoice {name} [{party}] — Draft")
        sinv_names.append((name, party, do_submit))

    # ── 5. Purchase Invoices ──────────────────────────────────────────────────
    print("\n[5/6] Creating purchase invoices...")

    purchases = [
        ("Office Supplies Co.",      "2026-01-20", "2026-02-20",
         [purchase_line("Office Desk", 4)], True),

        ("Cloud Infrastructure Ltd", "2026-02-01", "2026-03-01",
         [purchase_line("Cloud Hosting (Annual)", 1)], True),

        ("Marketing Agency Pro",     "2026-03-10", "2026-04-10",
         [purchase_line("Web Development Services", 5, rate=120.0)], True),

        # Draft
        ("Office Supplies Co.",      "2026-04-25", "2026-05-25",
         [purchase_line("Office Desk", 2)], False),
    ]

    pinv_names = []
    for party, date, due_date, inv_items, do_submit in purchases:
        name = create_purchase_invoice(
            conn,
            {"party": party, "date": date, "due_date": due_date,
             "account": creditors, "currency": "USD"},
            inv_items,
        )
        if do_submit:
            submit_purchase_invoice(conn, name)
            print(f"  + Purchase Invoice {name} [{party}] — Submitted")
        else:
            print(f"  + Purchase Invoice {name} [{party}] — Draft")
        pinv_names.append((name, party, do_submit))

    # ── 6. Payments ───────────────────────────────────────────────────────────
    print("\n[6/6] Creating payments...")

    submitted_sinv = [(n, p) for n, p, s in sinv_names if s]
    submitted_pinv = [(n, p) for n, p, s in pinv_names if s]

    # Two customer receipts
    for sinv_name, party in submitted_sinv[:2]:
        row = conn.execute(
            "SELECT outstanding_amount, date FROM sales_invoice WHERE name = ?", (sinv_name,)
        ).fetchone()
        pay_amount = float(row["outstanding_amount"])
        pay_name = create_payment(
            conn,
            {
                "party": party,
                "date": row["date"],
                "payment_type": "Receive",
                "payment_method": "Bank Transfer",
                "amount": pay_amount,
                "account": debtors,
                "payment_account": bank,
            },
            [{"reference_type": "SalesInvoice", "reference_name": sinv_name, "amount": pay_amount}],
        )
        submit_payment(conn, pay_name)
        print(f"  + Payment {pay_name} — received {pay_amount:.2f} from {party}")

    # One supplier payment
    if submitted_pinv:
        pinv_name, party = submitted_pinv[0]
        row = conn.execute(
            "SELECT outstanding_amount, date FROM purchase_invoice WHERE name = ?", (pinv_name,)
        ).fetchone()
        pay_amount = float(row["outstanding_amount"])
        pay_name = create_payment(
            conn,
            {
                "party": party,
                "date": row["date"],
                "payment_type": "Pay",
                "payment_method": "Bank Transfer",
                "amount": pay_amount,
                "account": creditors,
                "payment_account": bank,
            },
            [{"reference_type": "PurchaseInvoice", "reference_name": pinv_name, "amount": pay_amount}],
        )
        submit_payment(conn, pay_name)
        print(f"  + Payment {pay_name} — paid {pay_amount:.2f} to {party}")

    # ── Done ──────────────────────────────────────────────────────────────────
    print("\nSeed complete.")
    print("  Customers  : 3")
    print("  Suppliers  : 3")
    print("  Items      : 5")
    print("  Sales Inv  : 5  (4 submitted, 1 draft)")
    print("  Purch Inv  : 4  (3 submitted, 1 draft)")
    print("  Payments   : 3  (2 received, 1 paid)")


if __name__ == "__main__":
    conn, db_path = get_or_create_db("books")
    print(f"Database: {db_path}")

    if not is_setup_done(conn):
        print("Running first-time setup...")
        complete_setup(conn, "Demo Company Ltd.", "United States", "USD")
        print("Setup complete.")

    seed(conn)
