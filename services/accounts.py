"""
Chart of Accounts CRUD and COA import from standard fixture.
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_standard_coa(conn: sqlite3.Connection) -> None:
    coa_path = DATA_DIR / "standard_coa.json"
    with open(coa_path) as f:
        coa = json.load(f)

    _process_coa_node(conn, coa, parent=None)
    conn.commit()


def _process_coa_node(conn: sqlite3.Connection, node: dict, parent: str | None) -> None:
    root_type_map = {
        "Application of Funds (Assets)": "Asset",
        "Source of Funds (Liabilities)": "Liability",
        "Equity": "Equity",
        "Income": "Income",
        "Expenses": "Expense",
    }

    for key, value in node.items():
        if key == "rootType":
            continue
        if not isinstance(value, dict):
            continue

        account_type = value.get("accountType", "")
        is_group = 1 if value.get("isGroup") else 0

        # Determine root type from top-level key or inherit
        if key in root_type_map:
            root_type = root_type_map[key]
        else:
            root_type = _infer_root_type(conn, parent) if parent else "Asset"

        if is_group == 0 and not any(
            isinstance(v, dict) and k != "accountType" and k != "isGroup"
            for k, v in value.items()
        ):
            is_group = 0
        else:
            has_children = any(
                isinstance(v, dict) and k not in ("accountType", "isGroup")
                for k, v in value.items()
            )
            if has_children:
                is_group = 1

        existing = conn.execute(
            "SELECT name FROM account WHERE name = ?", (key,)
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT OR IGNORE INTO account
                   (name, root_type, account_type, parent_account, is_group)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, root_type, account_type, parent, is_group),
            )

        _process_coa_node(conn, value, parent=key)


def _infer_root_type(conn: sqlite3.Connection, account_name: str) -> str:
    row = conn.execute(
        "SELECT root_type FROM account WHERE name = ?", (account_name,)
    ).fetchone()
    return row["root_type"] if row else "Asset"


def get_all_accounts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM account ORDER BY root_type, name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_leaf_accounts(conn: sqlite3.Connection, root_type: str | None = None) -> list[dict]:
    query = "SELECT * FROM account WHERE is_group = 0"
    params: list = []
    if root_type:
        query += " AND root_type = ?"
        params.append(root_type)
    query += " ORDER BY root_type, name"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_accounts_by_type(conn: sqlite3.Connection, account_type: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM account WHERE account_type = ? AND is_group = 0 ORDER BY name",
        (account_type,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_account(
    conn: sqlite3.Connection,
    name: str,
    root_type: str,
    account_type: str = "",
    parent_account: str | None = None,
    is_group: int = 0,
) -> None:
    conn.execute(
        """INSERT INTO account (name, root_type, account_type, parent_account, is_group)
           VALUES (?, ?, ?, ?, ?)""",
        (name, root_type, account_type, parent_account, is_group),
    )
    conn.commit()


def update_account(
    conn: sqlite3.Connection,
    original_name: str,
    name: str,
    root_type: str,
    account_type: str,
    parent_account: str | None,
    is_group: int,
) -> None:
    conn.execute(
        """UPDATE account
           SET name = ?, root_type = ?, account_type = ?, parent_account = ?, is_group = ?
           WHERE name = ?""",
        (name, root_type, account_type, parent_account, is_group, original_name),
    )
    conn.commit()


def delete_account(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    used_in_ledger = conn.execute(
        "SELECT COUNT(*) as cnt FROM accounting_ledger_entry WHERE account = ?", (name,)
    ).fetchone()["cnt"]
    if used_in_ledger > 0:
        return False, "Account has ledger entries and cannot be deleted."

    has_children = conn.execute(
        "SELECT COUNT(*) as cnt FROM account WHERE parent_account = ?", (name,)
    ).fetchone()["cnt"]
    if has_children > 0:
        return False, "Account has child accounts. Delete children first."

    conn.execute("DELETE FROM account WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def get_account_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM account WHERE is_group = 0 ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def get_receivable_accounts(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM account WHERE account_type = 'Receivable' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def get_payable_accounts(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM account WHERE account_type = 'Payable' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def get_cash_and_bank_accounts(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM account WHERE account_type IN ('Cash', 'Bank') ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]
