"""
Item (Product/Service) CRUD and Tax management.
"""
import sqlite3


def get_all_items(conn: sqlite3.Connection, for_purpose: str | None = None) -> list[dict]:
    query = "SELECT * FROM item"
    params: list = []
    if for_purpose and for_purpose != "All":
        query += " WHERE for_purpose = ? OR for_purpose = 'Both'"
        params.append(for_purpose)
    query += " ORDER BY name"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_item(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM item WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def create_item(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """INSERT INTO item
           (name, item_code, item_group, for_purpose, item_type, unit,
            rate, description, income_account, expense_account, tax,
            track_item, barcode)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data.get("item_code", ""),
            data.get("item_group"),
            data.get("for_purpose", "Both"),
            data.get("item_type", "Product"),
            data.get("unit", "Unit"),
            float(data.get("rate", 0)),
            data.get("description", ""),
            data.get("income_account"),
            data.get("expense_account"),
            data.get("tax"),
            1 if data.get("track_item") else 0,
            data.get("barcode", ""),
        ),
    )
    conn.commit()


def update_item(conn: sqlite3.Connection, original_name: str, data: dict) -> None:
    conn.execute(
        """UPDATE item SET
           name = ?, item_code = ?, item_group = ?, for_purpose = ?,
           item_type = ?, unit = ?, rate = ?, description = ?,
           income_account = ?, expense_account = ?, tax = ?,
           track_item = ?, barcode = ?
           WHERE name = ?""",
        (
            data["name"],
            data.get("item_code", ""),
            data.get("item_group"),
            data.get("for_purpose", "Both"),
            data.get("item_type", "Product"),
            data.get("unit", "Unit"),
            float(data.get("rate", 0)),
            data.get("description", ""),
            data.get("income_account"),
            data.get("expense_account"),
            data.get("tax"),
            1 if data.get("track_item") else 0,
            data.get("barcode", ""),
            original_name,
        ),
    )
    conn.commit()


def delete_item(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    used = conn.execute(
        """SELECT COUNT(*) as cnt FROM sales_invoice_item WHERE item = ?
           UNION ALL SELECT COUNT(*) FROM purchase_invoice_item WHERE item = ?""",
        (name, name),
    ).fetchall()
    if any(r["cnt"] > 0 for r in used):
        return False, "Item is used in invoices and cannot be deleted."
    conn.execute("DELETE FROM item WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def get_item_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM item ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def get_item_groups(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM item_group ORDER BY name").fetchall()
    return [r["name"] for r in rows]


# ---------- Tax management ----------

def get_all_taxes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM tax ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_tax(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute("SELECT * FROM tax WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def create_tax(conn: sqlite3.Connection, name: str, rate: float, account: str) -> None:
    conn.execute(
        "INSERT INTO tax (name, rate, account) VALUES (?, ?, ?)",
        (name, rate, account),
    )
    conn.commit()


def update_tax(conn: sqlite3.Connection, original_name: str, name: str, rate: float, account: str) -> None:
    conn.execute(
        "UPDATE tax SET name = ?, rate = ?, account = ? WHERE name = ?",
        (name, rate, account, original_name),
    )
    conn.commit()


def delete_tax(conn: sqlite3.Connection, name: str) -> tuple[bool, str]:
    used = conn.execute(
        "SELECT COUNT(*) as cnt FROM item WHERE tax = ?", (name,)
    ).fetchone()["cnt"]
    if used > 0:
        return False, "Tax is linked to items and cannot be deleted."
    conn.execute("DELETE FROM tax WHERE name = ?", (name,))
    conn.commit()
    return True, ""


def get_tax_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM tax ORDER BY name").fetchall()
    return [r["name"] for r in rows]
