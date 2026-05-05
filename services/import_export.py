"""
CSV import/export and local backup/restore.
"""
import csv
import io
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.database import STORAGE_DIR


# ---------- Backup / Restore ----------

def backup_database(db_path: str) -> str:
    """Copy the database to a timestamped backup file. Returns backup path."""
    backup_dir = Path(db_path).parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{Path(db_path).stem}_{ts}.db"
    shutil.copy2(db_path, backup_path)
    return str(backup_path)


def list_backups(db_path: str) -> list[str]:
    backup_dir = Path(db_path).parent / "backups"
    if not backup_dir.exists():
        return []
    return sorted(
        [str(p) for p in backup_dir.glob("*.db")], reverse=True
    )


def restore_database(backup_path: str, db_path: str) -> None:
    """Restore database from a backup file (overwrites current DB)."""
    shutil.copy2(backup_path, db_path)


# ---------- CSV Export ----------

def export_parties_csv(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT name, role, email, phone, address, city, state, country,
                  zip_code, currency, tax_id, is_active, notes, opening_balance,
                  contact_person
           FROM party ORDER BY name"""
    ).fetchall()
    return _rows_to_csv(rows)


def export_items_csv(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT name, item_code, item_group, for_purpose, item_type, unit,
                  rate, purchase_rate, description, tax, is_active, stock_quantity
           FROM item ORDER BY name"""
    ).fetchall()
    return _rows_to_csv(rows)


def export_sales_invoices_csv(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT name, party, date, due_date, status, net_total, tax_total,
                  discount_amount, grand_total, outstanding_amount, currency, user_remark
           FROM sales_invoice ORDER BY date DESC"""
    ).fetchall()
    return _rows_to_csv(rows)


def export_purchase_invoices_csv(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT name, party, date, due_date, status, net_total, tax_total,
                  discount_amount, grand_total, outstanding_amount, currency, user_remark
           FROM purchase_invoice ORDER BY date DESC"""
    ).fetchall()
    return _rows_to_csv(rows)


def export_general_ledger_csv(
    conn: sqlite3.Connection,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    query = """SELECT date, account, party, debit, credit, transaction_type, transaction_name
               FROM accounting_ledger_entry WHERE is_cancelled = 0"""
    params: list = []
    if from_date:
        query += " AND date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND date <= ?"
        params.append(to_date)
    query += " ORDER BY date, id"
    rows = conn.execute(query, params).fetchall()
    return _rows_to_csv(rows)


def export_payments_csv(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT name, party, date, payment_type, payment_method, amount,
                  status, user_remark
           FROM payment ORDER BY date DESC"""
    ).fetchall()
    return _rows_to_csv(rows)


def export_bank_transactions_csv(conn: sqlite3.Connection, bank_account: str | None = None) -> str:
    query = """SELECT bt.id, bt.bank_account, bt.date, bt.transaction_type, bt.amount,
                      bt.description, bt.reference, bt.category, bt.reconciled
               FROM bank_transaction bt WHERE 1=1"""
    params: list = []
    if bank_account:
        query += " AND bt.bank_account = ?"
        params.append(bank_account)
    query += " ORDER BY bt.date DESC, bt.id DESC"
    rows = conn.execute(query, params).fetchall()
    return _rows_to_csv(rows)


def _rows_to_csv(rows) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows([dict(r) for r in rows])
    return output.getvalue()


# ---------- CSV Import ----------

def import_parties_csv(conn: sqlite3.Connection, csv_content: str) -> tuple[int, int, list[str]]:
    """Returns (inserted, skipped, errors)."""
    inserted = 0
    skipped = 0
    errors = []
    reader = csv.DictReader(io.StringIO(csv_content))
    required = {"name", "role"}
    for i, row in enumerate(reader, 2):
        if not required.issubset(set(row.keys())):
            errors.append(f"Row {i}: Missing required columns (name, role)")
            continue
        name = row.get("name", "").strip()
        if not name:
            errors.append(f"Row {i}: Empty name, skipped")
            skipped += 1
            continue
        existing = conn.execute("SELECT name FROM party WHERE name = ?", (name,)).fetchone()
        if existing:
            skipped += 1
            continue
        try:
            conn.execute(
                """INSERT INTO party
                   (name, role, email, phone, address, city, state, country,
                    zip_code, currency, tax_id, is_active, notes, opening_balance, contact_person)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    row.get("role", "Both"),
                    row.get("email", ""),
                    row.get("phone", ""),
                    row.get("address", ""),
                    row.get("city", ""),
                    row.get("state", ""),
                    row.get("country", ""),
                    row.get("zip_code", ""),
                    row.get("currency", "USD"),
                    row.get("tax_id", ""),
                    1 if str(row.get("is_active", "1")).strip() in ("1", "True", "true", "yes") else 0,
                    row.get("notes", ""),
                    float(row.get("opening_balance", 0) or 0),
                    row.get("contact_person", ""),
                ),
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i} ({name}): {e}")
    conn.commit()
    return inserted, skipped, errors


def import_items_csv(conn: sqlite3.Connection, csv_content: str) -> tuple[int, int, list[str]]:
    inserted = 0
    skipped = 0
    errors = []
    reader = csv.DictReader(io.StringIO(csv_content))
    for i, row in enumerate(reader, 2):
        name = row.get("name", "").strip()
        if not name:
            skipped += 1
            continue
        existing = conn.execute("SELECT name FROM item WHERE name = ?", (name,)).fetchone()
        if existing:
            skipped += 1
            continue
        try:
            conn.execute(
                """INSERT INTO item
                   (name, item_code, item_group, for_purpose, item_type, unit,
                    rate, purchase_rate, description, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    row.get("item_code", ""),
                    row.get("item_group"),
                    row.get("for_purpose", "Both"),
                    row.get("item_type", "Product"),
                    row.get("unit", "Unit"),
                    float(row.get("rate", 0) or 0),
                    float(row.get("purchase_rate", 0) or 0),
                    row.get("description", ""),
                    1 if str(row.get("is_active", "1")).strip() in ("1", "True", "true", "yes") else 0,
                ),
            )
            inserted += 1
        except Exception as e:
            errors.append(f"Row {i} ({name}): {e}")
    conn.commit()
    return inserted, skipped, errors
