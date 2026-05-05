"""
Banking: bank/cash account management and transaction recording.
"""
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from backend import ledger


def _d(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _r2(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------- Bank Accounts ----------

def get_all_bank_accounts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM bank_account ORDER BY account_type, name"
    ).fetchall()
    result = []
    for r in rows:
        ba = dict(r)
        ba["current_balance"] = _r2(_d(ba["opening_balance"]) + _d(_get_net_movements(conn, ba["name"])))
        result.append(ba)
    return result


def _get_net_movements(conn: sqlite3.Connection, bank_account: str) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN transaction_type='Deposit' THEN amount
                                    WHEN transaction_type='Transfer In' THEN amount
                                    ELSE -amount END), 0) as net
           FROM bank_transaction WHERE bank_account = ?""",
        (bank_account,),
    ).fetchone()
    return float(row["net"]) if row else 0.0


def get_bank_account(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM bank_account WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    ba = dict(row)
    ba["current_balance"] = _r2(_d(ba["opening_balance"]) + _d(_get_net_movements(conn, name)))
    return ba


def create_bank_account(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """INSERT INTO bank_account
           (name, account_type, account_number, bank_name, currency,
            opening_balance, is_active, gl_account)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("account_type", "Bank"),
            data.get("account_number", ""),
            data.get("bank_name", ""),
            data.get("currency", "USD"),
            float(data.get("opening_balance", 0)),
            1,
            data.get("gl_account"),
        ),
    )
    conn.commit()


def update_bank_account(conn: sqlite3.Connection, original_name: str, data: dict) -> None:
    conn.execute(
        """UPDATE bank_account SET
           name = ?, account_type = ?, account_number = ?, bank_name = ?,
           currency = ?, opening_balance = ?, is_active = ?, gl_account = ?
           WHERE name = ?""",
        (
            data["name"],
            data.get("account_type", "Bank"),
            data.get("account_number", ""),
            data.get("bank_name", ""),
            data.get("currency", "USD"),
            float(data.get("opening_balance", 0)),
            1 if data.get("is_active", True) else 0,
            data.get("gl_account"),
            original_name,
        ),
    )
    conn.commit()


def get_bank_account_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM bank_account WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


# ---------- Transactions ----------

def get_bank_transactions(
    conn: sqlite3.Connection,
    bank_account: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    reconciled: int | None = None,
) -> list[dict]:
    query = "SELECT * FROM bank_transaction WHERE 1=1"
    params: list = []
    if bank_account:
        query += " AND bank_account = ?"
        params.append(bank_account)
    if from_date:
        query += " AND date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND date <= ?"
        params.append(to_date)
    if reconciled is not None:
        query += " AND reconciled = ?"
        params.append(reconciled)
    query += " ORDER BY date DESC, id DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def record_deposit(
    conn: sqlite3.Connection,
    bank_account: str,
    date: str,
    amount: float,
    description: str = "",
    reference: str = "",
    category: str = "",
    post_ledger: bool = True,
) -> int:
    cursor = conn.execute(
        """INSERT INTO bank_transaction
           (bank_account, date, transaction_type, amount, description, reference, category)
           VALUES (?, ?, 'Deposit', ?, ?, ?, ?)""",
        (bank_account, date, amount, description, reference, category),
    )
    txn_id = cursor.lastrowid

    if post_ledger:
        ba = get_bank_account(conn, bank_account)
        if ba and ba.get("gl_account"):
            ledger.post_ledger_entry(
                conn, date, ba["gl_account"], amount, 0,
                "BankDeposit", f"BT-{txn_id}",
            )

    conn.commit()
    return txn_id


def record_withdrawal(
    conn: sqlite3.Connection,
    bank_account: str,
    date: str,
    amount: float,
    description: str = "",
    reference: str = "",
    category: str = "",
    post_ledger: bool = True,
) -> int:
    cursor = conn.execute(
        """INSERT INTO bank_transaction
           (bank_account, date, transaction_type, amount, description, reference, category)
           VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?)""",
        (bank_account, date, amount, description, reference, category),
    )
    txn_id = cursor.lastrowid

    if post_ledger:
        ba = get_bank_account(conn, bank_account)
        if ba and ba.get("gl_account"):
            ledger.post_ledger_entry(
                conn, date, ba["gl_account"], 0, amount,
                "BankWithdrawal", f"BT-{txn_id}",
            )

    conn.commit()
    return txn_id


def record_transfer(
    conn: sqlite3.Connection,
    from_account: str,
    to_account: str,
    date: str,
    amount: float,
    description: str = "",
    post_ledger: bool = True,
) -> tuple[int, int]:
    c1 = conn.execute(
        """INSERT INTO bank_transaction
           (bank_account, date, transaction_type, amount, description)
           VALUES (?, ?, 'Transfer Out', ?, ?)""",
        (from_account, date, amount, description),
    )
    from_id = c1.lastrowid

    c2 = conn.execute(
        """INSERT INTO bank_transaction
           (bank_account, date, transaction_type, amount, description)
           VALUES (?, ?, 'Transfer In', ?, ?)""",
        (to_account, date, amount, description),
    )
    to_id = c2.lastrowid

    if post_ledger:
        fa = get_bank_account(conn, from_account)
        ta = get_bank_account(conn, to_account)
        ref = f"Transfer-{from_id}"
        if fa and fa.get("gl_account"):
            ledger.post_ledger_entry(conn, date, fa["gl_account"], 0, amount, "BankTransfer", ref)
        if ta and ta.get("gl_account"):
            ledger.post_ledger_entry(conn, date, ta["gl_account"], amount, 0, "BankTransfer", ref)

    conn.commit()
    return from_id, to_id


def mark_reconciled(conn: sqlite3.Connection, txn_id: int, reconciled: bool = True) -> None:
    conn.execute(
        "UPDATE bank_transaction SET reconciled = ? WHERE id = ?",
        (1 if reconciled else 0, txn_id),
    )
    conn.commit()


def get_reconciliation_summary(conn: sqlite3.Connection, bank_account: str) -> dict:
    rows = conn.execute(
        """SELECT reconciled,
                  SUM(CASE WHEN transaction_type IN ('Deposit','Transfer In') THEN amount ELSE -amount END) as net
           FROM bank_transaction
           WHERE bank_account = ?
           GROUP BY reconciled""",
        (bank_account,),
    ).fetchall()
    reconciled = 0.0
    unreconciled = 0.0
    for r in rows:
        if r["reconciled"]:
            reconciled = float(r["net"] or 0)
        else:
            unreconciled = float(r["net"] or 0)
    ba = get_bank_account(conn, bank_account)
    opening = float(ba["opening_balance"]) if ba else 0.0
    return {
        "opening_balance": opening,
        "reconciled_movements": reconciled,
        "unreconciled_movements": unreconciled,
        "reconciled_balance": opening + reconciled,
        "current_balance": opening + reconciled + unreconciled,
    }
