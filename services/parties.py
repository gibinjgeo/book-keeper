"""
Party (Customer / Supplier) CRUD.
"""
import sqlite3


def get_all_parties(conn: sqlite3.Connection, role: str | None = None) -> list[dict]:
    query = "SELECT * FROM party"
    params: list = []
    if role and role != "All":
        query += " WHERE role = ? OR role = 'Both'"
        params.append(role)
    query += " ORDER BY name"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_party(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM party WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def create_party(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """INSERT INTO party
           (name, role, email, phone, address, city, state, country,
            zip_code, default_account, currency, tax_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("role", "Both"),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("city", ""),
            data.get("state", ""),
            data.get("country", ""),
            data.get("zip_code", ""),
            data.get("default_account"),
            data.get("currency", "USD"),
            data.get("tax_id", ""),
        ),
    )
    conn.commit()


def update_party(conn: sqlite3.Connection, original_name: str, data: dict) -> None:
    conn.execute(
        """UPDATE party SET
           name = ?, role = ?, email = ?, phone = ?, address = ?,
           city = ?, state = ?, country = ?, zip_code = ?,
           default_account = ?, currency = ?, tax_id = ?
           WHERE name = ?""",
        (
            data["name"],
            data.get("role", "Both"),
            data.get("email", ""),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("city", ""),
            data.get("state", ""),
            data.get("country", ""),
            data.get("zip_code", ""),
            data.get("default_account"),
            data.get("currency", "USD"),
            data.get("tax_id", ""),
            original_name,
        ),
    )
    conn.commit()


def delete_party(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    used_si = conn.execute(
        "SELECT COUNT(*) as cnt FROM sales_invoice WHERE party = ?", (name,)
    ).fetchone()["cnt"]
    used_pi = conn.execute(
        "SELECT COUNT(*) as cnt FROM purchase_invoice WHERE party = ?", (name,)
    ).fetchone()["cnt"]
    if used_si + used_pi > 0:
        return False, "Party has linked transactions and cannot be deleted."
    conn.execute("DELETE FROM party WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def get_party_names(conn: sqlite3.Connection, role: str | None = None) -> list[str]:
    query = "SELECT name FROM party"
    params: list = []
    if role and role != "All":
        query += " WHERE role = ? OR role = 'Both'"
        params.append(role)
    query += " ORDER BY name"
    rows = conn.execute(query, params).fetchall()
    return [r["name"] for r in rows]


def get_outstanding_balance(conn: sqlite3.Connection, party: str) -> dict:
    receivable = conn.execute(
        """SELECT COALESCE(SUM(outstanding_amount), 0) as total
           FROM sales_invoice WHERE party = ? AND status IN ('Submitted', 'Overdue')""",
        (party,),
    ).fetchone()["total"]

    payable = conn.execute(
        """SELECT COALESCE(SUM(outstanding_amount), 0) as total
           FROM purchase_invoice WHERE party = ? AND status IN ('Submitted', 'Overdue')""",
        (party,),
    ).fetchone()["total"]

    return {"receivable": receivable, "payable": payable}
