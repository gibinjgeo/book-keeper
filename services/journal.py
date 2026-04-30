"""
Journal Entry CRUD with double-entry validation and ledger posting.
Mirrors JournalEntry.ts business logic.
"""
import sqlite3
from datetime import datetime

from backend.database import next_series_name
from backend import ledger


ENTRY_TYPES = [
    "Journal Entry",
    "Bank Entry",
    "Cash Entry",
    "Credit Card Entry",
    "Debit Note",
    "Credit Note",
    "Contra Entry",
    "Opening Entry",
    "Depreciation Entry",
    "Write Off Entry",
]


def get_all_journal_entries(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM journal_entry ORDER BY date DESC, name DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_journal_entry(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM journal_entry WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        return None
    je = dict(row)
    je["accounts"] = get_journal_entry_accounts(conn, name)
    return je


def get_journal_entry_accounts(conn: sqlite3.Connection, je_name: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM journal_entry_account WHERE parent = ? ORDER BY id",
        (je_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def validate_journal_entry(accounts: list[dict]) -> tuple[bool, str]:
    total_debit = sum(float(a.get("debit", 0)) for a in accounts)
    total_credit = sum(float(a.get("credit", 0)) for a in accounts)
    if abs(total_debit - total_credit) > 0.01:
        return (
            False,
            f"Debits ({total_debit:.2f}) must equal Credits ({total_credit:.2f})",
        )
    if total_debit == 0:
        return False, "Journal entry must have at least one debit and one credit."
    for row in accounts:
        if not row.get("account"):
            return False, "All rows must have an account selected."
        d = float(row.get("debit", 0))
        c = float(row.get("credit", 0))
        if d < 0 or c < 0:
            return False, "Debit and Credit values cannot be negative."
        if d > 0 and c > 0:
            return False, "A row cannot have both Debit and Credit values."
    return True, ""


def create_journal_entry(conn: sqlite3.Connection, data: dict, accounts: list[dict]) -> str:
    valid, msg = validate_journal_entry(accounts)
    if not valid:
        raise ValueError(msg)

    name = next_series_name(conn, data.get("number_series", "JV-"))
    total_debit = sum(float(a.get("debit", 0)) for a in accounts)
    total_credit = sum(float(a.get("credit", 0)) for a in accounts)

    conn.execute(
        """INSERT INTO journal_entry
           (name, date, entry_type, total_debit, total_credit,
            user_remark, reference_number, reference_date,
            status, number_series)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Draft', ?)""",
        (
            name,
            data.get("date", datetime.now().strftime("%Y-%m-%d")),
            data.get("entry_type", "Journal Entry"),
            total_debit,
            total_credit,
            data.get("user_remark", ""),
            data.get("reference_number", ""),
            data.get("reference_date"),
            data.get("number_series", "JV-"),
        ),
    )

    for row in accounts:
        conn.execute(
            """INSERT INTO journal_entry_account
               (parent, account, debit, credit, party,
                reference_type, reference_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                row.get("account"),
                float(row.get("debit", 0)),
                float(row.get("credit", 0)),
                row.get("party", ""),
                row.get("reference_type", ""),
                row.get("reference_name", ""),
            ),
        )

    conn.commit()
    return name


def update_journal_entry(
    conn: sqlite3.Connection, name: str, data: dict, accounts: list[dict]
) -> None:
    je = get_journal_entry(conn, name)
    if je and je["status"] != "Draft":
        raise ValueError("Only Draft journal entries can be edited.")

    valid, msg = validate_journal_entry(accounts)
    if not valid:
        raise ValueError(msg)

    total_debit = sum(float(a.get("debit", 0)) for a in accounts)
    total_credit = sum(float(a.get("credit", 0)) for a in accounts)

    conn.execute(
        """UPDATE journal_entry SET
           date = ?, entry_type = ?, total_debit = ?, total_credit = ?,
           user_remark = ?, reference_number = ?, reference_date = ?
           WHERE name = ?""",
        (
            data.get("date"),
            data.get("entry_type", "Journal Entry"),
            total_debit,
            total_credit,
            data.get("user_remark", ""),
            data.get("reference_number", ""),
            data.get("reference_date"),
            name,
        ),
    )

    conn.execute("DELETE FROM journal_entry_account WHERE parent = ?", (name,))
    for row in accounts:
        conn.execute(
            """INSERT INTO journal_entry_account
               (parent, account, debit, credit, party,
                reference_type, reference_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                row.get("account"),
                float(row.get("debit", 0)),
                float(row.get("credit", 0)),
                row.get("party", ""),
                row.get("reference_type", ""),
                row.get("reference_name", ""),
            ),
        )

    conn.commit()


def submit_journal_entry(conn: sqlite3.Connection, name: str) -> None:
    je = get_journal_entry(conn, name)
    if not je:
        raise ValueError(f"Journal Entry {name} not found.")
    if je["status"] != "Draft":
        raise ValueError("Only Draft journal entries can be submitted.")

    accounts = get_journal_entry_accounts(conn, name)
    valid, msg = validate_journal_entry(accounts)
    if not valid:
        raise ValueError(msg)

    ledger.post_journal_entry(conn, je, accounts)
    conn.execute(
        """UPDATE journal_entry SET
           status = 'Submitted', submitted_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def cancel_journal_entry(conn: sqlite3.Connection, name: str) -> None:
    je = get_journal_entry(conn, name)
    if not je:
        raise ValueError(f"Journal Entry {name} not found.")
    if je["status"] != "Submitted":
        raise ValueError("Only Submitted journal entries can be cancelled.")

    ledger.cancel_ledger_entries(conn, "JournalEntry", name)
    conn.execute(
        """UPDATE journal_entry SET
           status = 'Cancelled', cancelled_at = datetime('now')
           WHERE name = ?""",
        (name,),
    )
    conn.commit()


def delete_journal_entry(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    je = get_journal_entry(conn, name)
    if not je:
        return False, "Journal Entry not found."
    if je["status"] != "Draft":
        return False, "Only Draft journal entries can be deleted."
    conn.execute("DELETE FROM journal_entry_account WHERE parent = ?", (name,))
    conn.execute("DELETE FROM journal_entry WHERE name = ?", (name,))
    conn.commit()
    return True, ""
