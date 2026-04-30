"""
Double-entry ledger posting logic.
Mirrors LedgerPosting.ts and AccountingLedgerEntry from the original project.
"""
import sqlite3
from datetime import datetime
from decimal import Decimal


def post_ledger_entry(
    conn: sqlite3.Connection,
    date: str,
    account: str,
    debit: float,
    credit: float,
    transaction_type: str,
    transaction_name: str,
    party: str = "",
) -> None:
    conn.execute(
        """INSERT INTO accounting_ledger_entry
           (date, account, debit, credit, transaction_type, transaction_name, party)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (date, account, debit, credit, transaction_type, transaction_name, party),
    )


def cancel_ledger_entries(
    conn: sqlite3.Connection,
    transaction_type: str,
    transaction_name: str,
) -> None:
    conn.execute(
        """UPDATE accounting_ledger_entry
           SET is_cancelled = 1
           WHERE transaction_type = ? AND transaction_name = ? AND is_cancelled = 0""",
        (transaction_type, transaction_name),
    )


def post_sales_invoice(conn: sqlite3.Connection, invoice: dict, items: list) -> None:
    date = invoice["date"] or datetime.now().strftime("%Y-%m-%d")
    name = invoice["name"]
    party = invoice.get("party", "")
    grand_total = float(invoice.get("grand_total", 0))
    exchange_rate = float(invoice.get("exchange_rate", 1))
    is_return = bool(invoice.get("is_return", 0))

    if is_return:
        post_ledger_entry(conn, date, invoice["account"], 0, grand_total,
                          "SalesInvoice", name, party)
    else:
        post_ledger_entry(conn, date, invoice["account"], grand_total, 0,
                          "SalesInvoice", name, party)

    for item in items:
        amt = float(item.get("amount", 0)) * exchange_rate
        acc = item.get("account", "")
        if not acc:
            continue
        if is_return:
            post_ledger_entry(conn, date, acc, amt, 0, "SalesInvoice", name, party)
        else:
            post_ledger_entry(conn, date, acc, 0, amt, "SalesInvoice", name, party)

        if float(item.get("tax_amount", 0)) > 0 and item.get("tax_account"):
            tax_amt = float(item["tax_amount"]) * exchange_rate
            if is_return:
                post_ledger_entry(conn, date, item["tax_account"], tax_amt, 0,
                                  "SalesInvoice", name, party)
            else:
                post_ledger_entry(conn, date, item["tax_account"], 0, tax_amt,
                                  "SalesInvoice", name, party)


def post_purchase_invoice(conn: sqlite3.Connection, invoice: dict, items: list) -> None:
    date = invoice["date"] or datetime.now().strftime("%Y-%m-%d")
    name = invoice["name"]
    party = invoice.get("party", "")
    grand_total = float(invoice.get("grand_total", 0))
    exchange_rate = float(invoice.get("exchange_rate", 1))
    is_return = bool(invoice.get("is_return", 0))

    if is_return:
        post_ledger_entry(conn, date, invoice["account"], grand_total, 0,
                          "PurchaseInvoice", name, party)
    else:
        post_ledger_entry(conn, date, invoice["account"], 0, grand_total,
                          "PurchaseInvoice", name, party)

    for item in items:
        amt = float(item.get("amount", 0)) * exchange_rate
        acc = item.get("account", "")
        if not acc:
            continue
        if is_return:
            post_ledger_entry(conn, date, acc, 0, amt, "PurchaseInvoice", name, party)
        else:
            post_ledger_entry(conn, date, acc, amt, 0, "PurchaseInvoice", name, party)

        if float(item.get("tax_amount", 0)) > 0 and item.get("tax_account"):
            tax_amt = float(item["tax_amount"]) * exchange_rate
            if is_return:
                post_ledger_entry(conn, date, item["tax_account"], 0, tax_amt,
                                  "PurchaseInvoice", name, party)
            else:
                post_ledger_entry(conn, date, item["tax_account"], tax_amt, 0,
                                  "PurchaseInvoice", name, party)


def post_payment(conn: sqlite3.Connection, payment: dict) -> None:
    date = payment["date"] or datetime.now().strftime("%Y-%m-%d")
    name = payment["name"]
    party = payment.get("party", "")
    amount = float(payment.get("amount", 0))
    payment_type = payment.get("payment_type", "Receive")
    from_account = payment.get("account", "")
    to_account = payment.get("payment_account", "")

    if payment_type == "Receive":
        post_ledger_entry(conn, date, to_account, amount, 0, "Payment", name, party)
        post_ledger_entry(conn, date, from_account, 0, amount, "Payment", name, party)
    else:
        post_ledger_entry(conn, date, from_account, amount, 0, "Payment", name, party)
        post_ledger_entry(conn, date, to_account, 0, amount, "Payment", name, party)


def post_journal_entry(conn: sqlite3.Connection, je: dict, accounts: list) -> None:
    date = je["date"] or datetime.now().strftime("%Y-%m-%d")
    name = je["name"]

    for row in accounts:
        debit = float(row.get("debit", 0))
        credit = float(row.get("credit", 0))
        account = row.get("account", "")
        party = row.get("party", "")
        if not account:
            continue
        if debit > 0:
            post_ledger_entry(conn, date, account, debit, 0, "JournalEntry", name, party)
        if credit > 0:
            post_ledger_entry(conn, date, account, 0, credit, "JournalEntry", name, party)


def get_account_balance(
    conn: sqlite3.Connection,
    account: str,
    as_of_date: str | None = None,
) -> dict:
    query = """
        SELECT
            COALESCE(SUM(debit), 0) as total_debit,
            COALESCE(SUM(credit), 0) as total_credit
        FROM accounting_ledger_entry
        WHERE account = ? AND is_cancelled = 0
    """
    params: list = [account]
    if as_of_date:
        query += " AND date <= ?"
        params.append(as_of_date)

    row = conn.execute(query, params).fetchone()
    total_debit = row["total_debit"] if row else 0
    total_credit = row["total_credit"] if row else 0
    return {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balance": total_debit - total_credit,
    }
