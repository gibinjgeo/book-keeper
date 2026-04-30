"""
Payment CRUD with double-entry ledger posting.
Mirrors Payment.ts and PaymentFor.ts business logic.
"""
import sqlite3
from datetime import datetime

from backend.database import next_series_name
from backend import ledger
from services.invoices import apply_payment_to_invoice


def get_all_payments(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM payment ORDER BY date DESC, name DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_payment(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM payment WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    pmt = dict(row)
    pmt["for_references"] = get_payment_references(conn, name)
    return pmt


def get_payment_references(conn: sqlite3.Connection, payment_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM payment_for WHERE parent = ? ORDER BY id",
        (payment_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_payment(conn: sqlite3.Connection, data: dict, references: list[dict]) -> str:
    name = next_series_name(conn, data.get("number_series", "PAY-"))

    conn.execute(
        """INSERT INTO payment
           (name, party, date, payment_type, payment_method,
            amount, account, payment_account, status, user_remark, number_series)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?)""",
        (
            name,
            data.get("party"),
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("payment_type", "Receive"),
            data.get("payment_method", "Cash"),
            float(data.get("amount", 0)),
            data.get("account"),
            data.get("payment_account"),
            data.get("user_remark", ""),
            data.get("number_series", "PAY-"),
        ),
    )

    for ref in references:
        conn.execute(
            """INSERT INTO payment_for (parent, reference_type, reference_name, amount)
               VALUES (?, ?, ?, ?)""",
            (
                name,
                ref.get("reference_type"),
                ref.get("reference_name"),
                float(ref.get("amount", 0)),
            ),
        )

    conn.commit()
    return name


def submit_payment(conn: sqlite3.Connection, name: str) -> None:
    pmt = get_payment(conn, name)
    if not pmt:
        raise ValueError(f"Payment {name} not found.")
    if pmt["status"] != "Draft":
        raise ValueError("Only Draft payments can be submitted.")
    if not pmt.get("account"):
        raise ValueError("From account is required.")
    if not pmt.get("payment_account"):
        raise ValueError("To account is required.")

    ledger.post_payment(conn, pmt)

    for ref in pmt.get("for_references", []):
        if ref.get("reference_type") and ref.get("reference_name"):
            apply_payment_to_invoice(
                conn,
                ref["reference_type"],
                ref["reference_name"],
                float(ref.get("amount", 0)),
            )

    conn.execute(
        """UPDATE payment SET
           status = 'Submitted', submitted_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def cancel_payment(conn: sqlite3.Connection, name: str) -> None:
    pmt = get_payment(conn, name)
    if not pmt:
        raise ValueError(f"Payment {name} not found.")
    if pmt["status"] != "Submitted":
        raise ValueError("Only Submitted payments can be cancelled.")

    ledger.cancel_ledger_entries(conn, "Payment", name)
    conn.execute(
        """UPDATE payment SET
           status = 'Cancelled', cancelled_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def delete_payment(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    pmt = get_payment(conn, name)
    if not pmt:
        return False, "Payment not found."
    if pmt["status"] != "Draft":
        return False, "Only Draft payments can be deleted."
    conn.execute("DELETE FROM payment_for WHERE parent = ?", (name,))
    conn.execute("DELETE FROM payment WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def get_outstanding_invoices(
    conn: sqlite3.Connection,
    party: str,
    payment_type: str,
) -> list[dict]:
    if payment_type == "Receive":
        rows = conn.execute(
            """SELECT name, date, grand_total, outstanding_amount, 'SalesInvoice' as ref_type
               FROM sales_invoice
               WHERE party = ? AND outstanding_amount > 0
               AND status IN ('Submitted', 'Overdue')
               ORDER BY date""",
            (party,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT name, date, grand_total, outstanding_amount, 'PurchaseInvoice' as ref_type
               FROM purchase_invoice
               WHERE party = ? AND outstanding_amount > 0
               AND status IN ('Submitted', 'Overdue')
               ORDER BY date""",
            (party,),
        ).fetchall()

    return [dict(r) for r in rows]
