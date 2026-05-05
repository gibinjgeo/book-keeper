"""
Quotes/Estimates CRUD with convert-to-invoice workflow.
"""
import sqlite3
from datetime import datetime

from backend.database import next_series_name
from services.invoices import calculate_invoice_totals


def get_all_quotes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM quote ORDER BY date DESC, name DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_quote(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM quote WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    q = dict(row)
    q["items"] = get_quote_items(conn, name)
    return q


def get_quote_items(conn: sqlite3.Connection, quote_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM quote_item WHERE parent = ? ORDER BY id", (quote_name,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_quote(conn: sqlite3.Connection, data: dict, items: list[dict]) -> str:
    name = next_series_name(conn, data.get("number_series", "QTE-"))
    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))

    conn.execute(
        """INSERT INTO quote
           (name, party, date, expiry_date, status, net_total, tax_total,
            discount_amount, grand_total, currency, user_remark, number_series)
           VALUES (?, ?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            data.get("party"),
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("expiry_date"),
            totals["net_total"],
            totals["tax_total"],
            totals["discount_amount"],
            totals["grand_total"],
            data.get("currency", "USD"),
            data.get("user_remark", ""),
            data.get("number_series", "QTE-"),
        ),
    )
    _insert_quote_items(conn, name, items)
    conn.commit()
    return name


def _insert_quote_items(conn: sqlite3.Connection, quote_name: str, items: list[dict]) -> None:
    for item in items:
        conn.execute(
            """INSERT INTO quote_item
               (parent, item, description, account, quantity, rate,
                amount, tax_rate, tax_amount, tax_account)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                quote_name,
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


def update_quote(conn: sqlite3.Connection, name: str, data: dict, items: list[dict]) -> None:
    q = get_quote(conn, name)
    if q and q["status"] not in ("Draft",):
        raise ValueError("Only Draft quotes can be edited.")

    totals = calculate_invoice_totals(items, data.get("discount_percent", 0.0))
    conn.execute(
        """UPDATE quote SET
           party = ?, date = ?, expiry_date = ?, net_total = ?, tax_total = ?,
           discount_amount = ?, grand_total = ?, currency = ?, user_remark = ?
           WHERE name = ?""",
        (
            data.get("party"),
            data.get("date"),
            data.get("expiry_date"),
            totals["net_total"], totals["tax_total"],
            totals["discount_amount"], totals["grand_total"],
            data.get("currency", "USD"),
            data.get("user_remark", ""),
            name,
        ),
    )
    conn.execute("DELETE FROM quote_item WHERE parent = ?", (name,))
    _insert_quote_items(conn, name, items)
    conn.commit()


def send_quote(conn: sqlite3.Connection, name: str) -> None:
    q = get_quote(conn, name)
    if not q:
        raise ValueError(f"Quote {name} not found.")
    if q["status"] != "Draft":
        raise ValueError("Only Draft quotes can be sent.")
    conn.execute("UPDATE quote SET status = 'Sent' WHERE name = ?", (name,))
    conn.commit()


def convert_to_invoice(conn: sqlite3.Connection, quote_name: str, receivable_account: str) -> str:
    """Convert an accepted quote to a sales invoice."""
    from services.invoices import create_sales_invoice
    q = get_quote(conn, quote_name)
    if not q:
        raise ValueError(f"Quote {quote_name} not found.")
    if q["status"] in ("Converted", "Cancelled"):
        raise ValueError("Quote is already converted or cancelled.")

    items = get_quote_items(conn, quote_name)
    inv_name = create_sales_invoice(
        conn,
        {
            "party": q["party"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "due_date": q.get("expiry_date"),
            "account": receivable_account,
            "currency": q.get("currency", "USD"),
            "user_remark": f"From Quote {quote_name}",
            "number_series": "SINV-",
        },
        [dict(i) for i in items],
    )
    conn.execute(
        "UPDATE quote SET status = 'Converted', converted_to = ? WHERE name = ?",
        (inv_name, quote_name),
    )
    conn.commit()
    return inv_name


def cancel_quote(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "UPDATE quote SET status = 'Cancelled' WHERE name = ? AND status != 'Converted'",
        (name,),
    )
    conn.commit()


def delete_quote(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    q = get_quote(conn, name)
    if not q:
        return False, "Quote not found."
    if q["status"] == "Converted":
        return False, "Cannot delete a converted quote."
    conn.execute("DELETE FROM quote_item WHERE parent = ?", (name,))
    conn.execute("DELETE FROM quote WHERE name = ?", (name,))
    conn.commit()
    return True, ""
