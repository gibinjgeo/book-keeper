"""
Sales and Purchase Invoice CRUD with double-entry ledger posting.
"""
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from backend.database import next_series_name
from backend import ledger


def _d(value) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------- Calculation helpers ----------

def calculate_invoice_totals(items: list[dict], discount_percent: float = 0.0) -> dict:
    net_total = Decimal("0")
    tax_total = Decimal("0")

    for item in items:
        qty = _d(item.get("quantity", 0))
        rate = _d(item.get("rate", 0))
        amount = _round2(qty * rate)
        item["amount"] = float(amount)

        tax_rate = _d(item.get("tax_rate", 0))
        tax_amount = _round2(amount * tax_rate / Decimal("100"))
        item["tax_amount"] = float(tax_amount)

        net_total += amount
        tax_total += tax_amount

    discount_pct = _d(discount_percent)
    discount_amount = _round2(net_total * discount_pct / Decimal("100"))
    grand_total = _round2(net_total + tax_total - discount_amount)
    return {
        "net_total": float(_round2(net_total)),
        "tax_total": float(_round2(tax_total)),
        "discount_amount": float(discount_amount),
        "grand_total": float(grand_total),
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


def update_overdue_statuses(conn: sqlite3.Connection) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        """UPDATE sales_invoice SET status = 'Overdue'
           WHERE status = 'Submitted' AND due_date < ? AND outstanding_amount > 0""",
        (today,),
    )
    conn.execute(
        """UPDATE purchase_invoice SET status = 'Overdue'
           WHERE status = 'Submitted' AND due_date < ? AND outstanding_amount > 0""",
        (today,),
    )
    conn.commit()


def create_sales_invoice(conn: sqlite3.Connection, data: dict, items: list[dict]) -> str:
    name = next_series_name(conn, data.get("number_series", "SINV-"))
    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))

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

    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))

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
    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))

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

    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))

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
    from decimal import Decimal, ROUND_HALF_UP
    table = "sales_invoice" if invoice_type == "SalesInvoice" else "purchase_invoice"
    row = conn.execute(
        f"SELECT outstanding_amount, status FROM {table} WHERE name = ?", (invoice_name,)
    ).fetchone()
    if not row:
        return

    new_outstanding = max(Decimal("0"), Decimal(str(row["outstanding_amount"])) - Decimal(str(payment_amount)))
    new_outstanding = float(new_outstanding.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if new_outstanding == 0:
        new_status = "Paid"
    elif new_outstanding < float(row["outstanding_amount"]):
        new_status = "Partially Paid"
    else:
        new_status = row["status"]
    conn.execute(
        f"UPDATE {table} SET outstanding_amount = ?, status = ? WHERE name = ?",
        (new_outstanding, new_status, invoice_name),
    )
    conn.commit()


def create_credit_note(conn: sqlite3.Connection, original_invoice_name: str) -> str:
    """Create a credit note (return) against a submitted sales invoice."""
    inv = get_sales_invoice(conn, original_invoice_name)
    if not inv:
        raise ValueError(f"Invoice {original_invoice_name} not found.")
    if inv["status"] not in ("Submitted", "Paid", "Partially Paid", "Overdue"):
        raise ValueError("Can only create credit note against a submitted invoice.")

    items = get_sales_invoice_items(conn, original_invoice_name)
    name = next_series_name(conn, inv.get("number_series", "SINV-"))
    totals = calculate_invoice_totals([dict(i) for i in items])

    conn.execute(
        """INSERT INTO sales_invoice
           (name, party, date, due_date, status, account, net_total,
            tax_total, discount_amount, grand_total, outstanding_amount,
            currency, exchange_rate, is_return, return_against,
            user_remark, number_series)
           VALUES (?, ?, date('now'), date('now'), 'Draft', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
        (
            name, inv["party"], inv["account"],
            totals["net_total"], totals["tax_total"], totals["discount_amount"],
            totals["grand_total"], totals["grand_total"],
            inv.get("currency", "USD"), float(inv.get("exchange_rate", 1)),
            original_invoice_name,
            f"Credit Note against {original_invoice_name}",
            inv.get("number_series", "SINV-"),
        ),
    )
    for item in items:
        conn.execute(
            """INSERT INTO sales_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, item["item"], item["description"], item["account"],
             item["quantity"], item["rate"], item["amount"],
             item["tax_rate"], item["tax_amount"], item["tax_account"]),
        )
    conn.commit()
    return name


def create_debit_note(conn: sqlite3.Connection, original_invoice_name: str) -> str:
    """Create a debit note (return) against a submitted purchase invoice."""
    inv = get_purchase_invoice(conn, original_invoice_name)
    if not inv:
        raise ValueError(f"Invoice {original_invoice_name} not found.")
    if inv["status"] not in ("Submitted", "Paid", "Partially Paid", "Overdue"):
        raise ValueError("Can only create debit note against a submitted invoice.")

    items = get_purchase_invoice_items(conn, original_invoice_name)
    name = next_series_name(conn, inv.get("number_series", "PINV-"))
    totals = calculate_invoice_totals([dict(i) for i in items])

    conn.execute(
        """INSERT INTO purchase_invoice
           (name, party, date, due_date, status, account, net_total,
            tax_total, discount_amount, grand_total, outstanding_amount,
            currency, exchange_rate, is_return, return_against,
            user_remark, number_series)
           VALUES (?, ?, date('now'), date('now'), 'Draft', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
        (
            name, inv["party"], inv["account"],
            totals["net_total"], totals["tax_total"], totals["discount_amount"],
            totals["grand_total"], totals["grand_total"],
            inv.get("currency", "USD"), float(inv.get("exchange_rate", 1)),
            original_invoice_name,
            f"Debit Note against {original_invoice_name}",
            inv.get("number_series", "PINV-"),
        ),
    )
    for item in items:
        conn.execute(
            """INSERT INTO purchase_invoice_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, item["item"], item["description"], item["account"],
             item["quantity"], item["rate"], item["amount"],
             item["tax_rate"], item["tax_amount"], item["tax_account"]),
        )
    conn.commit()
    return name
