"""
Sales and Purchase Invoice CRUD with double-entry ledger posting.
Mirrors Invoice.ts, SalesInvoice.ts, PurchaseInvoice.ts business logic.
"""
import sqlite3
from datetime import datetime, timedelta

from backend.database import next_series_name
from backend import ledger


# ---------- Calculation helpers ----------

def calculate_invoice_totals(items: list[dict]) -> dict:
    net_total = 0.0
    tax_total = 0.0

    for item in items:
        qty = float(item.get("quantity", 0))
        rate = float(item.get("rate", 0))
        amount = round(qty * rate, 2)
        item["amount"] = amount

        tax_rate = float(item.get("tax_rate", 0))
        tax_amount = round(amount * tax_rate / 100, 2)
        item["tax_amount"] = tax_amount

        net_total += amount
        tax_total += tax_amount

    discount = 0.0
    grand_total = round(net_total + tax_total - discount, 2)
    return {
        "net_total": round(net_total, 2),
        "tax_total": round(tax_total, 2),
        "discount_amount": discount,
        "grand_total": grand_total,
    }


# ---------- Sales Invoice ----------

def get_all_sales_invoices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM sales_invoice ORDER BY date DESC, name DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_sales_invoice(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM sales_invoice WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        return None
    inv = dict(row)
    inv["items"] = get_sales_invoice_items(conn, name)
    return inv


def get_sales_invoice_items(conn: sqlite3.Connection, invoice_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM sales_invoice_item WHERE parent = ? ORDER BY id",
        (invoice_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_sales_invoice(conn: sqlite3.Connection, data: dict, items: list[dict]) -> str:
    name = next_series_name(conn, data.get("number_series", "SINV-"))
    totals = calculate_invoice_totals(items)

    conn.execute(
        """INSERT INTO sales_invoice
           (name, party, date, due_date, status, account, net_total,
            tax_total, discount_amount, grand_total, outstanding_amount,
            currency, exchange_rate, is_return, return_against,
            user_remark, number_series)
           VALUES (?, ?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            data.get("party"),
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("due_date"),
            data.get("account"),
            totals["net_total"],
            totals["tax_total"],
            totals["discount_amount"],
            totals["grand_total"],
            totals["grand_total"],
            data.get("currency", "USD"),
            float(data.get("exchange_rate", 1)),
            1 if data.get("is_return") else 0,
            data.get("return_against"),
            data.get("user_remark", ""),
            data.get("number_series", "SINV-"),
        ),
    )

    for item in items:
        conn.execute(
            """INSERT INTO sales_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                item.get("item"),
                item.get("description", ""),
                item.get("account"),
                float(item.get("quantity", 1)),
                float(item.get("rate", 0)),
                float(item.get("amount", 0)),
                float(item.get("tax_rate", 0)),
                float(item.get("tax_amount", 0)),
                item.get("tax_account"),
            ),
        )

    conn.commit()
    return name


def update_sales_invoice(
    conn: sqlite3.Connection, name: str, data: dict, items: list[dict]
) -> None:
    inv = get_sales_invoice(conn, name)
    if inv and inv["status"] != "Draft":
        raise ValueError("Only Draft invoices can be edited.")

    totals = calculate_invoice_totals(items)

    conn.execute(
        """UPDATE sales_invoice SET
           party = ?, date = ?, due_date = ?, account = ?,
           net_total = ?, tax_total = ?, discount_amount = ?,
           grand_total = ?, outstanding_amount = ?,
           currency = ?, exchange_rate = ?,
           user_remark = ?
           WHERE name = ?""",
        (
            data.get("party"),
            data.get("date"),
            data.get("due_date"),
            data.get("account"),
            totals["net_total"],
            totals["tax_total"],
            totals["discount_amount"],
            totals["grand_total"],
            totals["grand_total"],
            data.get("currency", "USD"),
            float(data.get("exchange_rate", 1)),
            data.get("user_remark", ""),
            name,
        ),
    )

    conn.execute("DELETE FROM sales_invoice_item WHERE parent = ?", (name,))
    for item in items:
        conn.execute(
            """INSERT INTO sales_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                item.get("item"),
                item.get("description", ""),
                item.get("account"),
                float(item.get("quantity", 1)),
                float(item.get("rate", 0)),
                float(item.get("amount", 0)),
                float(item.get("tax_rate", 0)),
                float(item.get("tax_amount", 0)),
                item.get("tax_account"),
            ),
        )

    conn.commit()


def submit_sales_invoice(conn: sqlite3.Connection, name: str) -> None:
    inv = get_sales_invoice(conn, name)
    if not inv:
        raise ValueError(f"Invoice {name} not found.")
    if inv["status"] != "Draft":
        raise ValueError("Only Draft invoices can be submitted.")
    if not inv.get("account"):
        raise ValueError("Receivable account is required before submitting.")

    items = get_sales_invoice_items(conn, name)
    ledger.post_sales_invoice(conn, inv, items)

    conn.execute(
        """UPDATE sales_invoice SET
           status = 'Submitted', submitted_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def cancel_sales_invoice(conn: sqlite3.Connection, name: str) -> None:
    inv = get_sales_invoice(conn, name)
    if not inv:
        raise ValueError(f"Invoice {name} not found.")
    if inv["status"] not in ("Submitted", "Overdue"):
        raise ValueError("Only Submitted invoices can be cancelled.")

    ledger.cancel_ledger_entries(conn, "SalesInvoice", name)
    conn.execute(
        """UPDATE sales_invoice SET
           status = 'Cancelled', outstanding_amount = 0,
           cancelled_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def delete_sales_invoice(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    inv = get_sales_invoice(conn, name)
    if not inv:
        return False, "Invoice not found."
    if inv["status"] != "Draft":
        return False, "Only Draft invoices can be deleted."
    conn.execute("DELETE FROM sales_invoice_item WHERE parent = ?", (name,))
    conn.execute("DELETE FROM sales_invoice WHERE name = ?", (name,))
    conn.commit()
    return True, ""


# ---------- Purchase Invoice ----------

def get_all_purchase_invoices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM purchase_invoice ORDER BY date DESC, name DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_purchase_invoice(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM purchase_invoice WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        return None
    inv = dict(row)
    inv["items"] = get_purchase_invoice_items(conn, name)
    return inv


def get_purchase_invoice_items(conn: sqlite3.Connection, invoice_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM purchase_invoice_item WHERE parent = ? ORDER BY id",
        (invoice_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_purchase_invoice(conn: sqlite3.Connection, data: dict, items: list[dict]) -> str:
    name = next_series_name(conn, data.get("number_series", "PINV-"))
    totals = calculate_invoice_totals(items)

    conn.execute(
        """INSERT INTO purchase_invoice
           (name, party, date, due_date, status, account, net_total,
            tax_total, discount_amount, grand_total, outstanding_amount,
            currency, exchange_rate, user_remark, number_series)
           VALUES (?, ?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            data.get("party"),
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("due_date"),
            data.get("account"),
            totals["net_total"],
            totals["tax_total"],
            totals["discount_amount"],
            totals["grand_total"],
            totals["grand_total"],
            data.get("currency", "USD"),
            float(data.get("exchange_rate", 1)),
            data.get("user_remark", ""),
            data.get("number_series", "PINV-"),
        ),
    )

    for item in items:
        conn.execute(
            """INSERT INTO purchase_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                item.get("item"),
                item.get("description", ""),
                item.get("account"),
                float(item.get("quantity", 1)),
                float(item.get("rate", 0)),
                float(item.get("amount", 0)),
                float(item.get("tax_rate", 0)),
                float(item.get("tax_amount", 0)),
                item.get("tax_account"),
            ),
        )

    conn.commit()
    return name


def update_purchase_invoice(
    conn: sqlite3.Connection, name: str, data: dict, items: list[dict]
) -> None:
    inv = get_purchase_invoice(conn, name)
    if inv and inv["status"] != "Draft":
        raise ValueError("Only Draft invoices can be edited.")

    totals = calculate_invoice_totals(items)

    conn.execute(
        """UPDATE purchase_invoice SET
           party = ?, date = ?, due_date = ?, account = ?,
           net_total = ?, tax_total = ?, discount_amount = ?,
           grand_total = ?, outstanding_amount = ?,
           currency = ?, exchange_rate = ?,
           user_remark = ?
           WHERE name = ?""",
        (
            data.get("party"),
            data.get("date"),
            data.get("due_date"),
            data.get("account"),
            totals["net_total"],
            totals["tax_total"],
            totals["discount_amount"],
            totals["grand_total"],
            totals["grand_total"],
            data.get("currency", "USD"),
            float(data.get("exchange_rate", 1)),
            data.get("user_remark", ""),
            name,
        ),
    )

    conn.execute("DELETE FROM purchase_invoice_item WHERE parent = ?", (name,))
    for item in items:
        conn.execute(
            """INSERT INTO purchase_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                item.get("item"),
                item.get("description", ""),
                item.get("account"),
                float(item.get("quantity", 1)),
                float(item.get("rate", 0)),
                float(item.get("amount", 0)),
                float(item.get("tax_rate", 0)),
                float(item.get("tax_amount", 0)),
                item.get("tax_account"),
            ),
        )

    conn.commit()


def submit_purchase_invoice(conn: sqlite3.Connection, name: str) -> None:
    inv = get_purchase_invoice(conn, name)
    if not inv:
        raise ValueError(f"Invoice {name} not found.")
    if inv["status"] != "Draft":
        raise ValueError("Only Draft invoices can be submitted.")
    if not inv.get("account"):
        raise ValueError("Payable account is required before submitting.")

    items = get_purchase_invoice_items(conn, name)
    ledger.post_purchase_invoice(conn, inv, items)

    conn.execute(
        """UPDATE purchase_invoice SET
           status = 'Submitted', submitted_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def cancel_purchase_invoice(conn: sqlite3.Connection, name: str) -> None:
    inv = get_purchase_invoice(conn, name)
    if not inv:
        raise ValueError(f"Invoice {name} not found.")
    if inv["status"] not in ("Submitted", "Overdue"):
        raise ValueError("Only Submitted invoices can be cancelled.")

    ledger.cancel_ledger_entries(conn, "PurchaseInvoice", name)
    conn.execute(
        """UPDATE purchase_invoice SET
           status = 'Cancelled', outstanding_amount = 0,
           cancelled_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def delete_purchase_invoice(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    inv = get_purchase_invoice(conn, name)
    if not inv:
        return False, "Invoice not found."
    if inv["status"] != "Draft":
        return False, "Only Draft invoices can be deleted."
    conn.execute("DELETE FROM purchase_invoice_item WHERE parent = ?", (name,))
    conn.execute("DELETE FROM purchase_invoice WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def apply_payment_to_invoice(
    conn: sqlite3.Connection,
    invoice_type: str,
    invoice_name: str,
    payment_amount: float,
) -> None:
    table = "sales_invoice" if invoice_type == "SalesInvoice" else "purchase_invoice"
    row = conn.execute(
        f"SELECT outstanding_amount FROM {table} WHERE name = ?", (invoice_name,)
    ).fetchone()
    if not row:
        return

    new_outstanding = max(0.0, float(row["outstanding_amount"]) - payment_amount)
    new_status = "Paid" if new_outstanding == 0 else "Submitted"
    conn.execute(
        f"UPDATE {table} SET outstanding_amount = ?, status = ? WHERE name = ?",
        (new_outstanding, new_status, invoice_name),
    )
    conn.commit()
